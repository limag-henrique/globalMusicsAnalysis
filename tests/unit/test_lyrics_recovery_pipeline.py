"""Regression tests for lyrics recovery, reconciliation, change ledger, and dynamic inventory."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from chart_observatory.lyrics import recovery_pipeline as rp
from chart_observatory.lyrics.inventory_export import (
    candidate_technical_status,
    rebuild_inventory_outputs,
    write_queues_and_change_ledger,
)
from chart_observatory.lyrics.quota_staging import (
    blobs,
    candidates,
    metadata,
    persist_lyric_staging,
    runs,
)
from chart_observatory.lyrics.recovery_pipeline import (
    _accept_candidate_replacement,
    build_prioritized_queue,
    build_v5_records,
    reconcile_v4_staging_runs,
    replay_sqlite_staging_runs,
)
from chart_observatory.research_progress import _staging_candidate_total


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_payload(
    cid: str,
    title: str,
    artist: str,
    bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "document_id": f"chart:{cid}",
        "recording_id": cid,
        "track_id": None,
        "lyrics_hash": "",
        "title": title,
        "artist": artist,
        "cohort_version": "worldwide-annual-quotas-v1",
        "chart_bindings": bindings,
        "identity_status": "pending_recording_and_text_review",
        "not_for_paid_submission": True,
    }


def _seed_sqlite_run(
    sqlite_path: Path,
    run_id: str,
    created_at: str,
    records: list[dict[str, Any]],
    texts: dict[str, str],
) -> None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    eng = create_engine(f"sqlite:///{sqlite_path.resolve()}")
    try:
        with eng.begin() as conn:
            metadata.create_all(conn)
            conn.execute(
                runs.insert().values(
                    id=run_id,
                    manifest={
                        "selection_root": "v4",
                        "phase": "test",
                        "unique_candidates": len(records),
                    },
                    created_at=datetime.fromisoformat(created_at),
                )
            )
            for sha, body in texts.items():
                conn.execute(
                    blobs.insert()
                    .prefix_with("OR IGNORE")
                    .values(sha256=sha, body=body, characters=len(body))
                )
            for rec in records:
                conn.execute(
                    candidates.insert().values(
                        run_id=run_id,
                        candidate_id=rec["candidate_id"],
                        text_sha256=rec["text_sha256"],
                        acquisition_status=rec["acquisition_status"],
                        payload=rec["payload"],
                        source_result=rec["source_result"],
                        audit=rec["audit"],
                        classification_ready=False,
                        identity_validated=False,
                        completeness_validated=False,
                        rights_status="UNVERIFIED",
                    )
                )
    finally:
        eng.dispose()


def _write_cached_lrclib_response(
    cache_dir: Path, title: str, artist: str, lyric: str, rec_id: int
) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://lrclib.net/api/search?track_name={title}&artist_name={artist}"
    body_obj = [
        {
            "id": rec_id,
            "trackName": title,
            "artistName": artist,
            "plainLyrics": lyric,
            "instrumental": False,
        }
    ]
    raw = json.dumps(body_obj).encode("utf-8")
    body_sha = hashlib.sha256(raw).hexdigest()
    path = cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()}.json"
    path.write_text(
        json.dumps({"url": url, "body": raw.decode("utf-8"), "body_sha256": body_sha}),
        encoding="utf-8",
    )
    return {
        "source": "LRCLIB",
        "status": "candidate_pending_validation",
        "text_sha256": _sha256(lyric),
        "text_quality_flags": [],
        "source_metadata": {
            "id": rec_id,
            "observed_title": title,
            "observed_artist": artist,
            "requested_artist": artist,
            "full_requested_artist_credit_matched": True,
        },
        "http_evidence": [
            {"url": url, "status": 200, "cache_path": str(path), "body_sha256": body_sha}
        ],
    }


def test_reconcile_v4_runs_scores_evidence_rather_than_newest_wins(tmp_path: Path) -> None:
    p_a = _make_payload(
        "SPOTIFY:1", "Alpha", "Artist A", [{"country_code": "US", "year": 2024, "position": 1}]
    )
    p_b = _make_payload(
        "SPOTIFY:2", "Beta", "Artist B", [{"country_code": "BR", "year": 2024, "position": 2}]
    )
    p_c = _make_payload(
        "SPOTIFY:3", "Gamma", "Artist C", [{"country_code": "UG", "year": 2024, "position": 3}]
    )

    txt_clean = "\n".join(
        f"Verse {i} complete lyric line with distinct melody and words" for i in range(1, 13)
    )
    txt_letras = "Texto antigo em quarentena LETRAS"
    sha_clean = _sha256(txt_clean)
    sha_letras = _sha256(txt_letras)

    sr_clean_a = _write_cached_lrclib_response(
        tmp_path / "cache", "Alpha", "Artist A", txt_clean, 101
    )
    sr_clean_b = _write_cached_lrclib_response(
        tmp_path / "cache", "Beta", "Artist B", txt_clean, 102
    )
    sr_gamma_c = _write_cached_lrclib_response(
        tmp_path / "cache", "Gamma", "Artist C", txt_clean, 103
    )
    sr_letras = {
        "source": "LETRAS",
        "quarantined_source": True,
        "text_sha256": sha_letras,
        "text_quality_flags": [],
        "source_metadata": {"observed_title": "Gamma", "observed_artist": "Artist C"},
    }
    sr_miss: dict[str, Any] = {"status": "not_found_or_unverified"}

    f593_recs = [
        {
            "candidate_id": "SPOTIFY:1",
            "payload": p_a,
            "source_result": sr_miss,
            "audit": {},
            "acquisition_status": "not_found",
            "text_sha256": None,
        },
        {
            "candidate_id": "SPOTIFY:2",
            "payload": p_b,
            "source_result": sr_miss,
            "audit": {},
            "acquisition_status": "not_found",
            "text_sha256": None,
        },
        {
            "candidate_id": "SPOTIFY:3",
            "payload": p_c,
            "source_result": sr_letras,
            "audit": {"source_quarantined": True},
            "acquisition_status": "inherited",
            "text_sha256": sha_letras,
        },
    ]
    c15da_recs = [
        {
            "candidate_id": "SPOTIFY:1",
            "payload": p_a,
            "source_result": sr_clean_a,
            "audit": {"source_quarantined": False, "text_quality_flags": []},
            "acquisition_status": "candidate_pending_validation",
            "text_sha256": sha_clean,
        },
        {
            "candidate_id": "SPOTIFY:2",
            "payload": p_b,
            "source_result": sr_miss,
            "audit": {},
            "acquisition_status": "not_found",
            "text_sha256": None,
        },
        {
            "candidate_id": "SPOTIFY:3",
            "payload": p_c,
            "source_result": sr_gamma_c,
            "audit": {"source_quarantined": False, "text_quality_flags": []},
            "acquisition_status": "candidate_pending_validation",
            "text_sha256": sha_clean,
        },
    ]
    b85_recs = [
        {
            "candidate_id": "SPOTIFY:1",
            "payload": p_a,
            "source_result": sr_miss,
            "audit": {},
            "acquisition_status": "not_found",
            "text_sha256": None,
        },
        {
            "candidate_id": "SPOTIFY:2",
            "payload": p_b,
            "source_result": sr_clean_b,
            "audit": {"source_quarantined": False, "text_quality_flags": []},
            "acquisition_status": "candidate_pending_validation",
            "text_sha256": sha_clean,
        },
        {
            "candidate_id": "SPOTIFY:3",
            "payload": p_c,
            "source_result": sr_letras,
            "audit": {"source_quarantined": True, "text_quality_flags": []},
            "acquisition_status": "inherited",
            "text_sha256": sha_letras,
        },
    ]

    _seed_sqlite_run(
        tmp_path / "f593.sqlite",
        "run_f593",
        "2026-11-15T21:31:07+00:00",
        f593_recs,
        {sha_letras: txt_letras},
    )
    _seed_sqlite_run(
        tmp_path / "c15da.sqlite",
        "run_15da",
        "2026-11-15T22:08:42+00:00",
        c15da_recs,
        {sha_clean: txt_clean},
    )
    _seed_sqlite_run(
        tmp_path / "b85.sqlite",
        "run_b85c",
        "2026-11-15T22:38:32+00:00",
        b85_recs,
        {sha_clean: txt_clean, sha_letras: txt_letras},
    )

    merged, _, report, ledger = reconcile_v4_staging_runs(
        tmp_path / "f593.sqlite",
        "run_f593",
        tmp_path / "c15da.sqlite",
        "run_15da",
        tmp_path / "b85.sqlite",
        "run_b85c",
        tmp_path,
    )
    assert report["reconciled_v4_candidates_with_text"] == 3
    assert merged["SPOTIFY:1"]["text_sha256"] == sha_clean
    assert merged["SPOTIFY:1"]["source_result"]["reconciled_from_run_id"] == "run_15da"
    assert merged["SPOTIFY:3"]["text_sha256"] == sha_clean
    assert merged["SPOTIFY:3"]["source_result"]["alternate_run_text_sha256"] == sha_letras
    assert len(ledger) == 1
    assert ledger[0]["candidate_id"] == "SPOTIFY:1"


def test_prioritized_queue_puts_deficient_cells_and_multi_memberships_first() -> None:
    clean_sr = {"source": "GENIUS"}
    records: dict[str, dict[str, Any]] = {
        "SPOTIFY:ug1": {
            "candidate_id": "SPOTIFY:ug1",
            "payload": _make_payload(
                "SPOTIFY:ug1", "S1", "A1", [{"country_code": "UG", "year": 2025, "position": 10}]
            ),
            "audit": {},
            "text_sha256": None,
        },
        "SPOTIFY:us_multi": {
            "candidate_id": "SPOTIFY:us_multi",
            "payload": _make_payload(
                "SPOTIFY:us_multi",
                "S2",
                "A2",
                [{"country_code": "US", "year": y, "position": 5} for y in (2022, 2023, 2024)],
            ),
            "audit": {},
            "text_sha256": None,
        },
        "SPOTIFY:us_single": {
            "candidate_id": "SPOTIFY:us_single",
            "payload": _make_payload(
                "SPOTIFY:us_single",
                "S3",
                "A3",
                [{"country_code": "US", "year": 2024, "position": 2}],
            ),
            "audit": {},
            "text_sha256": None,
        },
        "SPOTIFY:ug_quar": {
            "candidate_id": "SPOTIFY:ug_quar",
            "payload": _make_payload(
                "SPOTIFY:ug_quar", "S4", "A4", [{"country_code": "UG", "year": 2025, "position": 1}]
            ),
            "audit": {"source_quarantined": True},
            "source_result": {"source": "LETRAS"},
            "text_sha256": "a" * 64,
        },
    }
    # Fill US 2022, 2023, 2024 so >=80% clean; only UG 2025 remains <80% deficient.
    for year in (2022, 2023, 2024):
        for i in range(1, 11):
            cid = f"SPOTIFY:ok_{year}_{i}"
            records[cid] = {
                "candidate_id": cid,
                "payload": _make_payload(
                    cid,
                    f"OK{i}",
                    f"Art{i}",
                    [{"country_code": "US", "year": year, "position": 20 + i}],
                ),
                "audit": {},
                "source_result": clean_sr,
                "text_sha256": "b" * 64,
            }
    queue = build_prioritized_queue(records, include_quarantined=True)
    ids = [p["recording_id"] for p in queue]
    assert ids[0] == "SPOTIFY:ug1"
    assert ids[1] == "SPOTIFY:ug_quar"
    assert ids[2] == "SPOTIFY:us_multi"
    assert ids[3] == "SPOTIFY:us_single"
    assert "SPOTIFY:ok_2024_1" not in ids


def test_accept_replacement_records_quarantined_change_ledger(tmp_path: Path) -> None:
    lyric_old = "Letra antiga incompleta LETRAS"
    lyric_new = "\n".join(
        f"Verse {i} complete lyric line with distinct melody and words" for i in range(1, 13)
    )
    payload = _make_payload(
        "SPOTIFY:q1", "Song Q", "Artist Q", [{"country_code": "BR", "year": 2022, "position": 1}]
    )
    old_rec = {
        "candidate_id": "SPOTIFY:q1",
        "payload": payload,
        "source_result": {
            "source": "LETRAS",
            "quarantined_source": True,
            "text_sha256": _sha256(lyric_old),
        },
        "audit": {"source_quarantined": True, "text_quality_flags": []},
        "acquisition_status": "inherited_v1",
        "text_sha256": _sha256(lyric_old),
    }
    fresh_sr = _write_cached_lrclib_response(
        tmp_path / "cache", "Song Q", "Artist Q", lyric_new, 777
    )
    fresh_sr["text"] = lyric_new
    texts: dict[str, str] = {}
    ledger: list[dict[str, Any]] = []

    replaced = _accept_candidate_replacement(
        "SPOTIFY:q1",
        payload,
        old_rec,
        fresh_sr,
        texts,
        tmp_path,
        method_label="http_cache_replay:v4",
        ledger_rows=ledger,
    )
    assert replaced is not None
    updated_rec, new_sha = replaced
    assert new_sha == _sha256(lyric_new)
    assert updated_rec["source_result"]["replaces_text_sha256"] == _sha256(lyric_old)
    assert len(ledger) == 1
    assert ledger[0]["change_kind"] == "v1_quarantined_replacement"
    assert ledger[0]["old_text_sha256"] == _sha256(lyric_old)
    assert ledger[0]["new_text_sha256"] == new_sha


def test_dynamic_inventory_html_and_v4_v5_separation(tmp_path: Path, monkeypatch: Any) -> None:
    v4_dir = tmp_path / "v4"
    v5_dir = tmp_path / "v5"
    v4_dir.mkdir()
    v5_dir.mkdir()

    countries = [
        {"country_code": "BR", "country_name": "Brazil", "quota_per_year_main": 100},
        {"country_code": "SI", "country_name": "Slovenia", "quota_per_year_main": 110},
    ]
    v4_members = [
        {
            "country_code": "BR",
            "year": 2018,
            "position": 1,
            "candidate_id": "SPOTIFY:x1",
            "platform": "SPOTIFY",
            "provider": "MGD",
            "title": "Song X",
            "artist": "Art X",
            "selection_status": "CALENDAR_ELIGIBLE",
            "quota_main": 100,
        }
    ]
    v5_members = [
        *v4_members,
        {
            "country_code": "SI",
            "year": 2018,
            "position": 1,
            "candidate_id": "IPF:2018:si1",
            "platform": "NATIONAL_PUBLIC_PERFORMANCE",
            "provider": "IPF",
            "title": "Song SI",
            "artist": "Art SI",
            "selection_status": "PROVISIONAL_SOURCE_PERIOD_BINDING_REVIEW_REQUIRED",
            "quota_main": 110,
        },
    ]
    for d, mems in ((v4_dir, v4_members), (v5_dir, v5_members)):
        (d / "countries.json").write_text(json.dumps(countries), encoding="utf-8")
        (d / "combined.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in mems), encoding="utf-8"
        )
        (d / "manifest.json").write_text(json.dumps({"memberships": len(mems)}), encoding="utf-8")

    monkeypatch.setattr(
        rp,
        "load_selection",
        lambda path: ({}, [], v5_members if Path(path).name == "v5" else v4_members, {}),
    )
    clean_body = "Clean text body line one\n" * 10
    clean_sha = _sha256(clean_body)
    v4_recs = {
        "SPOTIFY:x1": {
            "candidate_id": "SPOTIFY:x1",
            "payload": _make_payload(
                "SPOTIFY:x1",
                "Song X",
                "Art X",
                [{"country_code": "BR", "year": 2018, "position": 1, "quota_main": 100}],
            ),
            "source_result": {"source": "GENIUS"},
            "audit": {
                "source_quarantined": False,
                "text_quality_flags": [],
                "technical_verification": {"quality_state": "acquired_unverified"},
            },
            "acquisition_status": "candidate_pending_validation",
            "text_sha256": clean_sha,
        }
    }
    v5_recs, _, v5_only = build_v5_records(v5_dir, v4_recs, {clean_sha: clean_body})
    assert v5_only == {"IPF:2018:si1"}
    assert len(v5_recs) == 2

    out_dir = tmp_path / "out"
    res = rebuild_inventory_outputs(
        out_dir,
        v4_selection_dir=v4_dir,
        v5_selection_dir=v5_dir,
        v4_run_id="r4",
        v5_run_id="r5",
        snapshot_created_at="2026-11-15T21:00:00+00:00",
        v4_records_by_id=v4_recs,
        v5_records_by_id=v5_recs,
        cohort_metrics={"canonical_tracks": 159080, "lyric_documents": 159111},
    )
    assert res["v4_resumo"]["candidatos_unicos"] == 1
    assert res["v5_resumo"]["candidatos_unicos"] == 2
    html = (out_dir / "inventario.html").read_text(encoding="utf-8")
    assert "['Prontas Vertex',t.prontas_vertex]" in html
    assert "r.prontas_vertex??0" in html
    assert "r.pronta_vertex?'Pronta':'Bloqueada ('" in html
    assert "['Prontas Vertex',0]" not in html
    assert "r.status_letra,'Pendente'," not in html

    q_res = write_queues_and_change_ledger(
        out_dir, list(v4_recs.values()), [v5_recs["IPF:2018:si1"]], [], tmp_path / "rev"
    )
    assert q_res["pending_queue_summary"]["total_rows"] == 1
    assert candidate_technical_status(v4_recs["SPOTIFY:x1"]) == "acquired_unverified"
    assert _staging_candidate_total({"unique_candidates": 1, "candidate_count": 1}) == (
        1,
        "unique_candidates",
    )

    pg_sim = create_engine(f"sqlite:///{tmp_path / 'sim.sqlite'}")
    try:
        manifest = {
            "unique_candidates": 1,
            "candidate_count": 1,
            "status_contract": "research-staging-status-v2",
        }
        persisted = persist_lyric_staging(
            pg_sim, manifest, list(v4_recs.values()), {clean_sha: clean_body}
        )
        _seed_sqlite_run(
            tmp_path / "src_replay.sqlite",
            persisted["run_id"],
            "2026-11-15T21:00:00+00:00",
            list(v4_recs.values()),
            {clean_sha: clean_body},
        )
        replayed = replay_sqlite_staging_runs(
            [(tmp_path / "src_replay.sqlite", [persisted["run_id"]])], pg_sim
        )
        assert replayed[0]["inserted"] is False
    finally:
        pg_sim.dispose()
