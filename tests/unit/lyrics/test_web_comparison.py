import hashlib

import pytest

from chart_observatory.lyrics.web_comparison import compare_lrclib

TEXT = "\n".join(f"Original fixture verse {i}" for i in range(25))


def row(**extra):
    return dict(
        id=1, trackName="Song", artistName="Artist", duration=200, plainLyrics=TEXT, **extra
    )


@pytest.mark.parametrize(
    "source,status",
    [
        ("LRCLIB", "same_provider_text_matches"),
        ("GENIUS", "cross_provider_text_matches"),
    ],
)
def test_web_agreement_never_claims_recording_identity_or_completeness(source, status):
    payload = dict(title="Song", artist="Artist", metadata_resolution=dict(duration_ms=200500))
    check, candidate = compare_lrclib(
        payload, dict(source=source), TEXT, hashlib.sha256(TEXT.encode()).hexdigest(), [row()], []
    )
    assert check["status"] == status and candidate["text"] == TEXT
    assert not check["identity_validated"] and not check["completeness_validated"]
    assert not check["classification_ready"]


def test_missing_refrain_is_a_difference_instead_of_fuzzy_approval():
    remote = {**row(), "plainLyrics": TEXT + "\nRefrain\nRefrain"}
    check, _ = compare_lrclib(
        dict(title="Song", artist="Artist"),
        dict(source="GENIUS"),
        TEXT,
        hashlib.sha256(TEXT.encode()).hexdigest(),
        [remote],
        [],
    )
    assert check["status"] == "web_text_differs"


@pytest.mark.parametrize(
    "change", [dict(trackName="Song (Live)"), dict(artistName="Other"), dict(duration=240)]
)
def test_title_artist_and_recording_duration_cannot_be_substituted(change):
    payload = dict(title="Song", artist="Artist", metadata_resolution=dict(duration_ms=200500))
    check, candidate = compare_lrclib(
        payload, {}, TEXT, hashlib.sha256(TEXT.encode()).hexdigest(), [{**row(), **change}], []
    )
    assert check["status"] == "no_matching_web_text" and candidate is None


def test_two_valid_editions_are_not_resolved_by_selecting_longer_text():
    check, candidate = compare_lrclib(
        dict(title="Song", artist="Artist"),
        {},
        None,
        None,
        [row(), {**row(), "id": 2, "plainLyrics": TEXT + "\nAnother verse"}],
        [],
    )
    assert check["status"] == "ambiguous_web_editions" and candidate is None


def test_stored_corruption_is_not_hidden_by_matching_web_content():
    check, candidate = compare_lrclib(
        dict(title="Song", artist="Artist"), {}, TEXT, "0" * 64, [row()], []
    )
    assert check["status"] == "stored_hash_mismatch" and candidate is None
