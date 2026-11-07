import hashlib

import pytest

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
