"""Tests for language identification, evidence bridge, staging replacement, and acceptance."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from chart_observatory import final_pipeline as final
from chart_observatory.lyrics.evidence_bridge import (
    build_minimal_review_packet,
    classify_review_pathway,
    load_verified_scientific_approvals,
)
from chart_observatory.lyrics.language_identification import identify_language


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
    import pytest

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
