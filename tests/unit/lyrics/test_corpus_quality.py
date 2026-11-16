import hashlib

import pytest

from chart_observatory.automatic_preparation import assess as assess_vertex_readiness
from chart_observatory.lyrics.automated_validation import assess_lyric_identity_completeness
from chart_observatory.lyrics.corpus_quality import assess_acquired_lyric


@pytest.mark.parametrize(
    "body",
    [
        "A deliberately short but potentially complete lyric.",
        "[Verse 2]\nThe beginning may be missing, and this must remain a suspicion.",
        "هذا نص تجريبي طويل وليس أغنية منشورة\n" * 20,
        "反復するテスト用の文章です\n" * 30,
        "Synthetic refrain\nSynthetic refrain\n" * 20,
        "Only a portion of these lyrics is available. See full lyrics.",
    ],
)
def test_screening_never_certifies_completeness_or_removes_repetitions(body):
    digest = hashlib.sha256(body.encode()).hexdigest()
    result = assess_acquired_lyric(
        {"title": "test", "artist": "test"},
        {"source": "TEST", "text_sha256": digest},
        body,
        digest,
    )
    assert result["hash_verified"]
    assert result["characters"] == len(body)
    assert not result["identity_validated"]
    assert not result["completeness_validated"]
    assert not result["classification_ready"]
    if "portion" in body:
        assert result["quality_state"] == "source_declared_partial"


def test_missing_text_is_not_a_complete_instrumental():
    result = assess_acquired_lyric({}, {}, None, None)
    assert result["quality_state"] == "unavailable"
    assert not result["classification_ready"]


def test_corrupt_blob_is_flagged_independently_from_metadata():
    result = assess_acquired_lyric({}, {"source": "TEST"}, "corrupt", "a" * 64)
    assert "stored_text_hash_mismatch" in result["flags"]
    assert not result["hash_verified"]


def test_repeated_refrain_only_text_is_held_out_of_automatic_review():
    refrain = "\n".join(
        f"A distinctive refrain line number {number} keeps returning tonight."
        for number in range(1, 9)
    )
    body = "\n".join(["[Chorus]", refrain, refrain, refrain])
    digest = hashlib.sha256(body.encode()).hexdigest()
    result = assess_acquired_lyric(
        {"title": "Test", "artist": "Artist"},
        {"source": "TEST", "text_sha256": digest},
        body,
        digest,
    )
    assert "suspected_refrain_only" in result["flags"]
    assert result["quality_state"] == "suspected_partial"
    assert not result["classification_ready"]


def test_verses_with_a_repeated_chorus_are_not_called_refrain_only():
    verses = "\n".join(
        f"A different verse line number {number} moves the story along tonight."
        for number in range(1, 9)
    )
    refrain = "\n".join(
        f"A repeated chorus line number {number} calls us home tonight."
        for number in range(1, 5)
    )
    body = "\n".join(["[Verse 1]", verses, "[Chorus]", refrain, refrain])
    digest = hashlib.sha256(body.encode()).hexdigest()
    result = assess_acquired_lyric(
        {"title": "Test", "artist": "Artist"},
        {"source": "TEST", "text_sha256": digest},
        body,
        digest,
    )
    assert "suspected_refrain_only" not in result["flags"]


def test_chorus_first_text_is_flagged_as_a_possible_mid_song_excerpt():
    body = "[Chorus]\n" + "\n".join(
        f"We sing a distinct refrain line number {number} tonight."
        for number in range(1, 9)
    )
    digest = hashlib.sha256(body.encode()).hexdigest()
    result = assess_acquired_lyric(
        {"title": "Test", "artist": "Artist"},
        {"source": "TEST", "text_sha256": digest},
        body,
        digest,
    )
    assert "possible_missing_initial_section" in result["flags"]


def test_full_source_replay_does_not_clear_refrain_only_text_for_vertex():
    refrain = "\n".join(
        f"A distinctive refrain line number {number} keeps returning tonight."
        for number in range(1, 9)
    )
    body = "\n".join(["[Chorus]", refrain, refrain, refrain])
    digest = hashlib.sha256(body.encode()).hexdigest()
    payload = {"title": "Test", "artist": "Artist"}
    source_result = {
        "source": "LRCLIB",
        "text_sha256": digest,
        "source_metadata": {
            "id": 7,
            "observed_title": "Test",
            "observed_artist": "Artist",
            "lyric_representation": "plain",
            "duration_seconds": 210,
        },
    }
    audit = assess_acquired_lyric(payload, source_result, body, digest)
    chain = {
        "status": "source_chain_matched",
        "source_url": "https://lrclib.net/api/get/7",
        "extracted_text_sha256": digest,
        "exact_text_hash_match": True,
        "evidence_sha256": "e" * 64,
    }
    record = {
        "payload": payload,
        "source_result": source_result,
        "text_sha256": digest,
        "audit": {"text_quality_flags": audit["flags"]},
    }
    validation = assess_lyric_identity_completeness(record, body, chain)
    decision = {
        "validation": validation,
        "native_supported": True,
        "native_evidence": {"native_proof_present": True, "body_sha256": "f" * 64},
        "body_hash_verified": True,
        "audit": {"text_quality_flags": audit["flags"]},
        "provider_supported": True,
    }

    assert validation["identity"]["status"] == "passed"
    assert validation["completeness"]["status"] == "failed"
    assert not assess_vertex_readiness(decision)["eligible"]


@pytest.mark.parametrize(
    "flag", ["provider_declares_incomplete_lyrics", "lyrics_declared_incomplete"]
)
def test_provider_declared_partial_has_explicit_state(flag):
    body = "Synthetic body of a declared partial lyric, even when it looks plausible."
    digest = hashlib.sha256(body.encode()).hexdigest()
    result = assess_acquired_lyric(
        {"title": "Test", "artist": "Test"},
        {"source": "TEST", "text_sha256": digest, "text_quality_flags": [flag]},
        body,
        digest,
    )
    assert result["quality_state"] == "source_declared_partial"
    assert not result["completeness_validated"]
