"""Tests for language identification, evidence bridge, staging replacement, and acceptance."""

from __future__ import annotations

import json
import sqlite3

import httpx
import pytest

from chart_observatory import final_pipeline as final
from chart_observatory.lyrics.evidence_bridge import (
    build_minimal_review_packet,
    load_verified_scientific_approvals,
)
from chart_observatory.lyrics.language_identification import identify_language
from chart_observatory.lyrics.recovery_web import CachedRecoveryHTTP


def test_language_identification_scripts_and_lexical():
    en = identify_language("I know you love me and you are my everything tonight yeah")
    assert en["language_code"] == "en"
    assert en["confidence"] > 0.5

    pt = identify_language("Eu não sei o que você faz comigo agora meu amor coração")
    assert pt["language_code"] == "pt"
    assert pt["confidence"] > 0.5

    es = identify_language("Yo no quiero nada más contigo cuando estás aquí mi amor")
    assert es["language_code"] == "es"
    assert es["confidence"] > 0.5

    ja = identify_language("君のことが好きだからずっとそばにいてほしい")
    assert ja["language_code"] == "ja"
    assert ja["confidence"] > 0.8

    ko = identify_language("너를 사랑해 영원히 함께 있어줘 내 마음")
    assert ko["language_code"] == "ko"
    assert ko["confidence"] > 0.8

    und = identify_language("la la")
    assert und["language_code"] == "und"


def test_staging_replacement_upgrades_better_evidence_and_preserves_ledger(tmp_path):
    path = tmp_path / "staging.sqlite"
    old_text = "short"
    old_sha = final.digest(old_text.encode())
    new_text = "Full verse one\nFull chorus with complete lyrics\nFull verse two\nOutro"
    new_sha = final.digest(new_text.encode())

    old_sr = json.dumps({"source": "UNKNOWN", "text_sha256": old_sha})
    new_sr = json.dumps({
        "source": "LRCLIB",
        "text_sha256": new_sha,
        "source_metadata": {
            "id": 12345,
            "observed_title": "Song",
            "observed_artist": "Artist",
            "url": "https://lrclib.net/api/get/12345",
            "lyric_representation": "plain",
            "duration_seconds": 210,
        },
    })
    payload = {"title": "Song", "artist": "Artist"}

    with sqlite3.connect(path) as source:
        source.executescript("""
            CREATE TABLE quota_lyric_staging_runs(id TEXT);
            CREATE TABLE quota_lyric_staging_blobs(sha256 TEXT,body TEXT);
            CREATE TABLE quota_lyric_staging_candidates(
                candidate_id TEXT,payload TEXT,text_sha256 TEXT,
                run_id TEXT,source_result TEXT,audit TEXT);
        """)
        source.execute("INSERT INTO quota_lyric_staging_runs VALUES ('run-old')")
        source.execute("INSERT INTO quota_lyric_staging_runs VALUES ('run-new')")
        source.execute("INSERT INTO quota_lyric_staging_blobs VALUES (?,?)", (old_sha, old_text))
        source.execute("INSERT INTO quota_lyric_staging_blobs VALUES (?,?)", (new_sha, new_text))
        source.execute(
            "INSERT INTO quota_lyric_staging_candidates VALUES (?,?,?,?,?,?)",
            ("rec:1", json.dumps(payload), old_sha, "run-old", old_sr, json.dumps({"text_quality_flags": ["very_short_text"]})),
        )
        source.execute(
            "INSERT INTO quota_lyric_staging_candidates VALUES (?,?,?,?,?,?)",
            ("rec:1", json.dumps(payload), new_sha, "run-new", new_sr, "{}"),
        )

    root = tmp_path / "catalog"
    with final.catalog(root) as db:
        final.add_song(db, "rec:1", payload)
        assert final.import_staging(db, path, "run-old", tmp_path) == 1
        # Now import run-new: should upgrade because new_score > old_score
        assert final.import_staging(db, path, "run-new", tmp_path) == 1
        cur = json.loads(db.execute("SELECT result FROM songs WHERE id='rec:1'").fetchone()[0])
        assert cur["text_sha256"] == new_sha
        ledger = db.execute("SELECT old_text_sha256, new_text_sha256, reason FROM replacement_ledger").fetchall()
        assert len(ledger) == 1
        assert ledger[0]["old_text_sha256"] == old_sha
        assert ledger[0]["new_text_sha256"] == new_sha
        assert ledger[0]["reason"] == "staging_evidence_improved"

        # Trying to re-import run-old (worse score) must NOT downgrade!
        assert final.import_staging(db, path, "run-old", tmp_path) == 0
        cur_after = json.loads(db.execute("SELECT result FROM songs WHERE id='rec:1'").fetchone()[0])
        assert cur_after["text_sha256"] == new_sha


def test_same_hash_staging_replacement_prefers_native_duration_match(tmp_path):
    candidate_id = "SPOTIFY:123"
    track_id = candidate_id.removeprefix("SPOTIFY:")
    path = tmp_path / "staging.sqlite"
    text = "Full verse one\nFull chorus with complete lyrics\nFull verse two\nOutro"
    sha = final.digest(text.encode())
    payload = {"title": "Song", "artist": "Artist"}

    def source_result(record_id, duration):
        url = "https://lrclib.net/api/search?track_name=Song&artist_name=Artist"
        row = {
            "id": record_id,
            "trackName": "Song",
            "artistName": "Artist",
            "duration": duration,
            "plainLyrics": text,
            "instrumental": False,
        }
        with httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[row]))
        ) as client:
            http = CachedRecoveryHTTP(tmp_path / f"capture-{record_id}", client)
            http.get(url)
            events = list(http.trace)
        return {
            "source": "LRCLIB",
            "source_metadata": {
                "id": record_id,
                "url": f"https://lrclib.net/api/get/{record_id}",
                "observed_title": "Song",
                "observed_artist": "Artist",
                "requested_artist": "Artist",
                "lyric_representation": "plain",
                "duration_seconds": duration,
                "full_requested_artist_credit_matched": True,
            },
            "http_evidence": events,
            "text_sha256": sha,
            "characters": len(text),
            "text_quality_flags": [],
        }

    results = {"run-old": source_result(1, 80), "run-new": source_result(2, 372)}
    with sqlite3.connect(path) as source:
        source.executescript("""
            CREATE TABLE quota_lyric_staging_runs(id TEXT);
            CREATE TABLE quota_lyric_staging_blobs(sha256 TEXT,body TEXT);
            CREATE TABLE quota_lyric_staging_candidates(
                candidate_id TEXT,payload TEXT,text_sha256 TEXT,
                run_id TEXT,source_result TEXT,audit TEXT);
        """)
        for run_id, result in results.items():
            source.execute("INSERT INTO quota_lyric_staging_runs VALUES (?)", (run_id,))
            source.execute("INSERT OR IGNORE INTO quota_lyric_staging_blobs VALUES (?,?)", (sha, text))
            source.execute(
                "INSERT INTO quota_lyric_staging_candidates VALUES (?,?,?,?,?,?)",
                (candidate_id, json.dumps(payload), sha, run_id, json.dumps(result), "{}"),
            )

    native_db = tmp_path / "data/raw/metadata_resolution/current/native-metadata.sqlite"
    native_db.parent.mkdir(parents=True)
    proof = {
        "status": 200,
        "source_url": f"https://open.spotify.com/embed/track/{track_id}",
        "body_sha256": "a" * 64,
        "retrieved_at": "2026-11-18T00:00:00Z",
        "metadata": {
            "uri": f"spotify:track:{track_id}",
            "title": "Song",
            "artist": "Artist",
            "duration_ms": 371790,
        },
    }
    with sqlite3.connect(native_db) as evidence:
        evidence.execute("CREATE TABLE evidence(candidate_id TEXT,proof TEXT)")
        evidence.execute("INSERT INTO evidence VALUES (?,?)", (candidate_id, json.dumps(proof)))

    root = tmp_path / "catalog"
    with final.catalog(root) as db:
        final.add_song(db, candidate_id, payload)
        assert final.import_staging(db, path, "run-old", tmp_path) == 1
        assert final.import_staging(db, path, "run-new", tmp_path) == 1
        current = json.loads(
            db.execute("SELECT result FROM songs WHERE id=?", (candidate_id,)).fetchone()[0]
        )
        assert current["staging_reference"]["run_id"] == "run-new"
        ledger = db.execute(
            "SELECT old_text_sha256,new_text_sha256,reason FROM replacement_ledger"
        ).fetchone()
        assert ledger["old_text_sha256"] == sha
        assert ledger["new_text_sha256"] == sha
        assert ledger["reason"] == "staging_evidence_improved"
        assert final.import_staging(db, path, "run-old", tmp_path) == 0
        current_payload, current_result = db.execute(
            "SELECT payload,result FROM songs WHERE id=?", (candidate_id,)
        ).fetchone()
        assessment = final.validate_text(
            json.loads(current_payload), json.loads(current_result), tmp_path
        )
        assert assessment["identity"]["status"] == "passed"
        assert assessment["source_text_integrity"]["status"] == "passed"
        assert assessment["effective_proof"]["recording_transcription_proven"] is False
        assert assessment["scientific_approval_status"] == "not_approved"
        assert assessment["classification_eligibility"] == "blocked_pending_gates"


@pytest.mark.parametrize("duration", [None, "372", True, 0, -1, float("nan"), float("inf")])
def test_native_duration_score_requires_valid_duration_and_matching_native_identity(duration):
    assert final._native_duration_match(371790, duration, True) == 0
    assert final._native_duration_match(371790, 372.0, False) == 0
    assert final._native_duration_match(371790, 372.0, True) == 1


def test_review_packet_does_not_fabricate_human_review():
    assessment = {
        "source_text_integrity": {"status": "passed", "raw_response_sha256": "a" * 64, "replayed_text_sha256": "b" * 64},
        "identity": {"status": "passed", "blocking_quality_flags": [], "provider_identity_reasons": [], "recording_version_binding": "duration_evidence_available"},
        "completeness": {"status": "passed", "blocking_quality_flags": []},
        "native_recording_alignment": {"native_proof_present": True},
        "language_identification": {"language_code": "en", "confidence": 0.9, "method": "language-id-v1-script-lexical"},
    }
    packet = build_minimal_review_packet(
        song_id="SPOTIFY:123",
        payload={"title": "Song", "artist": "Artist"},
        result={"source": "LRCLIB", "text_sha256": "b" * 64},
        text="Full lyrics here in english",
        assessment=assessment,
    )
    assert packet["pathway"] == "dependent_on_official_edition_transcription"
    assert packet["exact_form"]["template"]["actor"] is None
    assert packet["exact_form"]["template"]["at"] is None


def test_load_verified_scientific_approvals_missing_and_invalid(tmp_path):
    res = load_verified_scientific_approvals(None, tmp_path)
    assert res["audit_present"] is False
    assert len(res["approved_candidate_ids"]) == 0

    bad_dir = tmp_path / "bad_audit"
    bad_dir.mkdir()
    res_bad = load_verified_scientific_approvals(bad_dir, tmp_path)
    assert res_bad["audit_present"] is True
    assert res_bad["audit_valid"] is False
    assert res_bad["error"] is not None


def test_acquire_lyrics_enforces_150k_cap_programmatically(tmp_path):
    with final.catalog(tmp_path / "cat") as db:
        with pytest.raises(ValueError, match="150000"):
            final.acquire_lyrics(db, tmp_path / "cat", tmp_path, limit=150_001)


def test_validate_text_rejects_partial_lyrics_and_altered_evidence(tmp_path):
    text_file = tmp_path / "lyric.txt"
    partial_text = "[Chorus]\nOnly one short chorus"
    text_file.write_text(partial_text, encoding="utf-8")
    sha = final.digest(partial_text.encode())
    payload = {"title": "Song", "artist": "Artist"}
    result = {
        "source": "LRCLIB",
        "text_path": str(text_file),
        "text_sha256": sha,
        "source_metadata": {
            "id": 999,
            "observed_title": "Song",
            "observed_artist": "Artist",
            "url": "https://lrclib.net/api/get/999",
            "lyric_representation": "plain",
            "duration_seconds": 200,
        },
    }
    assessment = final.validate_text(payload, result, tmp_path)
    assert assessment["completeness"]["status"] != "passed"
    assert assessment["automated_overall"] != "passed"

    # Explicit partial/short flag produces 'failed'
    flagged_assessment = final.validate_text(
        payload, result, tmp_path, preloaded=(result, partial_text, {"text_quality_flags": ["very_short_text"]})
    )
    assert flagged_assessment["completeness"]["status"] == "failed"
    assert "very_short_text" in flagged_assessment["completeness"]["blocking_quality_flags"]

    # Altering the text file invalidates the stored hash
    text_file.write_text("tampered lyrics", encoding="utf-8")
    altered = final.validate_text(payload, result, tmp_path)
    assert altered["source_text_integrity"]["stored_hash_verified"] is False
    assert altered["completeness"]["status"] != "passed"
