"""Regression cases from independent TECH-01–TECH-06 review."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from chart_observatory.lyrics.quota_staging import blobs, candidates, metadata, runs
from chart_observatory.lyrics.recovery_pipeline import (
    _accept_candidate_replacement,
    _enrich_genius_metadata_from_evidence,
    apply_pg_v1_clean_fallback,
    reconcile_v4_staging_runs,
)
from chart_observatory.lyrics.source_chain import verify_source_chain
from chart_observatory.lyrics.text_quality import (
    prepare_lyric_derivative,
    recording_duration_mismatch,
)


@pytest.mark.parametrize("heading", ["[Couplet 2]", "[主歌二]", "[主歌 2]"])
def test_multilingual_second_section_is_not_complete(heading):
    result = prepare_lyric_derivative(heading + "\n" + "a lyric line\n" * 40, "GENIUS")
    assert "possible_missing_initial_section" in result.flags


def test_scraper_residue_is_flagged_without_rewriting_original():
    body = "A line\nYou might also like\n" + "more lyric\n" * 40
    result = prepare_lyric_derivative(body, "LRCLIB")
    assert "remaining_interface_residue" in result.flags
    assert result.text == body


def test_duplicate_halves_are_flagged_without_deleting_repeated_lyrics():
    half = "\n".join(f"lyric line {i}" for i in range(12))
    body = half + "\n" + half
    result = prepare_lyric_derivative(body, "GENIUS")
    assert "suspected_duplicated_container_halves" in result.flags
    assert result.text == body


def test_recording_duration_mismatch_flags_significant_discrepancy():
    assert recording_duration_mismatch(142200, 354.0) is True
    assert recording_duration_mismatch(284335, 284.0) is False


def test_name_only_fallback_cannot_query_database_or_replace_candidates():
    records = {"example": {"text_sha256": "unchanged"}}
    result = apply_pg_v1_clean_fallback(records, {}, None, [])
    assert result["pg_fallback_applied"] == 0
    assert records["example"]["text_sha256"] == "unchanged"


def test_verify_source_chain_accepts_recorded_redirect_and_reextracts_genius_credits(tmp_path):
    body = "\n".join(f"Clean lyric line {i} for redirect test" for i in range(1, 15))
    preloaded = {
        "currentPage": "songPage",
        "songPage": {"song": 4242},
        "entities": {
            "songs": {
                "4242": {
                    "id": 4242,
                    "title": "Redirect Song",
                    "url": "https://genius.com/Artist-redirect-song-lyrics",
                    "lyricsState": "complete",
                    "primaryArtist": 1,
                    "primaryArtists": [1],
                    "featuredArtists": [],
                }
            },
            "artists": {"1": {"id": 1, "name": "Artist"}},
        },
    }
    encoded_state = json.dumps(json.dumps(preloaded))
    html = (
        '<html><head><meta property="og:url" content="https://genius.com/Artist-redirect-song-lyrics">'
        "</head><body>"
        f"<script>window.__PRELOADED_STATE__ = JSON.parse('{encoded_state[1:-1]}');</script>"
        f'<div data-lyrics-container="true">{"<br/>".join(body.splitlines())}</div>'
        "</body></html>"
    )
    raw = html.encode("utf-8")
    raw_sha = hashlib.sha256(raw).hexdigest()
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "url": "https://genius.com/Artist-Redirect-Song-lyrics",
                "final_url": "https://genius.com/Artist-redirect-song-lyrics",
                "body": html,
                "body_sha256": raw_sha,
                "encoding": "utf-8",
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    result = {
        "source": "GENIUS",
        "source_metadata": {"url": "https://genius.com/Artist-redirect-song-lyrics"},
        "http_evidence": [
            {
                "url": "https://genius.com/Artist-Redirect-Song-lyrics",
                "status": 200,
                "cache_path": str(cache_path),
                "body_sha256": raw_sha,
            }
        ],
    }
    payload = {"title": "Redirect Song", "artist": "Artist"}
    check = verify_source_chain(payload, result, body, digest, tmp_path)
    assert check["status"] == "source_chain_match_metadata_pending"
    assert check["exact_text_hash_match"] is True
    assert check["reextracted_provider_credit_evidence"]["song_id"] == 4242
    assert _enrich_genius_metadata_from_evidence(payload, result, check) is True
    recheck = verify_source_chain(payload, result, body, digest, tmp_path)
    assert recheck["status"] == "source_chain_matched"


def test_store_exact_without_http_evidence_is_rejected_and_logged(tmp_path):
    body = "\n".join(f"Unique lyric line {i} without http evidence" for i in range(1, 15))
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    payload = {
        "recording_id": "SPOTIFY:t1",
        "title": "Song",
        "artist": "Artist",
        "chart_bindings": [],
    }
    old_rec = {
        "candidate_id": "SPOTIFY:t1",
        "payload": payload,
        "source_result": {},
        "audit": {},
        "text_sha256": None,
    }
    ledger = []
    res = _accept_candidate_replacement(
        "SPOTIFY:t1",
        payload,
        old_rec,
        {"source": "GENIUS", "text": body, "text_sha256": sha, "source_metadata": {}},
        {},
        tmp_path,
        method_label="store_exact:global-20261108:v4",
        ledger_rows=ledger,
    )
    assert res is None
    assert len(ledger) == 1
    assert ledger[0]["change_kind"] == "rejected_store_exact_candidate"


def test_reconcile_rejects_disputed_native_mismatch_and_shared_provider_id(tmp_path):
    meta_db = tmp_path / "data/raw/metadata_resolution/20261031/native-metadata.sqlite"
    meta_db.parent.mkdir(parents=True)
    with sqlite3.connect(meta_db) as db:
        db.execute("CREATE TABLE evidence(candidate_id TEXT PRIMARY KEY, proof TEXT NOT NULL)")
        for cid, title, artist, dur in [
            ("SPOTIFY:1", "Native Title", "Artist A", 200000),
            ("SPOTIFY:2", "Shared Song", "Artist B", 200000),
        ]:
            db.execute(
                "INSERT INTO evidence VALUES (?, ?)",
                (
                    cid,
                    json.dumps(
                        {
                            "status": 200,
                            "source_url": f"https://open.spotify.com/embed/track/{cid.removeprefix('SPOTIFY:')}",
                            "body_sha256": "a" * 64,
                            "retrieved_at": "2026-11-16T00:00:00+00:00",
                            "metadata": {
                                "uri": f"spotify:track:{cid.removeprefix('SPOTIFY:')}",
                                "title": title,
                                "artist": artist,
                                "duration_ms": dur,
                            },
                        }
                    ),
                ),
            )

    body = "\n".join(f"Clean lyric line {i} for lrclib" for i in range(1, 15))
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    url = "https://lrclib.net/api/search?q=test"
    raw = json.dumps(
        [
            {
                "id": 999,
                "trackName": "Frozen Title",
                "artistName": "Artist A",
                "plainLyrics": body,
                "duration": 200.0,
            }
        ]
    ).encode()
    raw_sha = hashlib.sha256(raw).hexdigest()
    cache_file = tmp_path / "lrc.json"
    cache_file.write_text(
        json.dumps({"url": url, "body": raw.decode(), "body_sha256": raw_sha}), encoding="utf-8"
    )

    def seed(path: Path, run_id: str, recs: list[dict], texts: dict[str, str]):
        eng = create_engine(f"sqlite:///{path}")
        with eng.begin() as conn:
            metadata.create_all(conn)
            conn.execute(
                runs.insert().values(
                    id=run_id, manifest={"phase": "test"}, created_at=datetime.now(UTC)
                )
            )
            for k, v in texts.items():
                conn.execute(blobs.insert().values(sha256=k, body=v, characters=len(v)))
            for r in recs:
                conn.execute(
                    candidates.insert().values(
                        run_id=run_id,
                        candidate_id=r["candidate_id"],
                        text_sha256=r["text_sha256"],
                        acquisition_status="pending",
                        payload=r["payload"],
                        source_result=r["source_result"],
                        audit=r["audit"],
                        classification_ready=False,
                        identity_validated=False,
                        completeness_validated=False,
                        rights_status="UNVERIFIED",
                    )
                )
        eng.dispose()

    p1 = {
        "recording_id": "SPOTIFY:1",
        "title": "Frozen Title",
        "artist": "Artist A",
        "chart_bindings": [],
    }
    p2 = {
        "recording_id": "SPOTIFY:2",
        "title": "Shared Song",
        "artist": "Artist B",
        "chart_bindings": [],
    }
    sr1 = {
        "source": "LRCLIB",
        "text_sha256": sha,
        "source_metadata": {
            "id": 999,
            "observed_title": "Frozen Title",
            "observed_artist": "Artist A",
            "duration_seconds": 200.0,
        },
        "http_evidence": [
            {"url": url, "status": 200, "cache_path": str(cache_file), "body_sha256": raw_sha}
        ],
    }
    r_miss = {
        "candidate_id": "SPOTIFY:1",
        "payload": p1,
        "source_result": {},
        "audit": {},
        "text_sha256": None,
    }
    r_hit = {
        "candidate_id": "SPOTIFY:1",
        "payload": p1,
        "source_result": sr1,
        "audit": {},
        "text_sha256": sha,
    }
    r_2 = {
        "candidate_id": "SPOTIFY:2",
        "payload": p2,
        "source_result": sr1,
        "audit": {},
        "text_sha256": sha,
    }

    seed(tmp_path / "f.sqlite", "rf", [r_miss, r_2], {sha: body})
    seed(tmp_path / "c.sqlite", "rc", [r_hit, r_2], {sha: body})
    seed(tmp_path / "a.sqlite", "ra", [r_miss, r_2], {sha: body})

    merged, _, report, ledger = reconcile_v4_staging_runs(
        tmp_path / "f.sqlite",
        "rf",
        tmp_path / "c.sqlite",
        "rc",
        tmp_path / "a.sqlite",
        "ra",
        tmp_path,
    )
    assert merged["SPOTIFY:1"]["text_sha256"] is None
    assert report["rejected_from_15da3853"] == 1
    assert any(row["change_kind"] == "rejected_disputed_cross_run_adoption" for row in ledger)


def test_checkpoint_rejects_modified_code_contract_or_upstream_hash(tmp_path):
    from scripts.run_lyrics_recovery_pipeline import _load_stage_checkpoint, _save_stage_checkpoint

    contract = {"versions": {"parser_version": "v1"}, "files": {"a.py": "hash1"}}
    ckpt = _save_stage_checkpoint(
        tmp_path, "stage2", {"SPOTIFY:1": {}}, {}, code_contract=contract, upstream_sha256="abc"
    )
    recs, _ = _load_stage_checkpoint(ckpt, code_contract=contract, expected_upstream_sha256="abc")
    assert "SPOTIFY:1" in recs

    with pytest.raises(ValueError, match="contract"):
        _load_stage_checkpoint(
            ckpt,
            code_contract={**contract, "files": {"a.py": "hash2"}},
            expected_upstream_sha256="abc",
        )
    with pytest.raises(ValueError, match="upstream"):
        _load_stage_checkpoint(ckpt, code_contract=contract, expected_upstream_sha256="def")
