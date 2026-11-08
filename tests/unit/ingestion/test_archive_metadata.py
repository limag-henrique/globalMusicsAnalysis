import copy
import hashlib

import pytest

from chart_observatory.ingestion.archive_metadata import (
    apply_archive_repairs,
    archive_proof,
    kworb_display,
)

NATIVE = "A" * 22
KEY = "SPOTIFY:" + NATIVE


def html(title="Song", artist="Artist"):
    return (
        f"<title>{artist} - {title} - Spotify Chart History</title>"
        '<div class="subcontainer"><span class="pagetitle">Spotify Chart History</span>'
        f'\nTitle: {title}\n<br>Artist: <a href="../artist/{"B" * 22}.html">{artist}</a>'
        "<div>Recommendation: Ignore</div>"
        '<a href="../artist/CCCCCCCCCCCCCCCCCCCCCC.html">Other Artist</a></div>'
    )


def proof(tmp_path):
    raw = html().encode()
    p = tmp_path / "evidence.html"
    p.write_bytes(raw)
    url = f"https://kworb.net/spotify/track/{NATIVE}.html"
    return dict(
        native_id=NATIVE,
        source_url=url,
        response_url=url,
        http_status=200,
        evidence_file=str(p),
        evidence_sha256=hashlib.sha256(raw).hexdigest(),
    )


def test_parser_does_not_read_recommendations():
    # Only artist links before the next container belong to the chart header.
    assert kworb_display(html()) == dict(title="Song", artist="Artist")


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_id", "C" * 22),
        ("http_status", 403),
        ("response_url", "https://example.test/wrong"),
        ("source_url", "https://kworb.net/spotify/track/wrong.html"),
        ("evidence_sha256", "0" * 64),
    ],
)
def test_proof_must_bind_exact_native_url_and_hash(tmp_path, field, value):
    reference = proof(tmp_path)
    reference[field] = value
    with pytest.raises(ValueError):
        archive_proof(KEY, reference)


def test_inconsistent_page_title_is_rejected():
    with pytest.raises(ValueError):
        kworb_display(html().replace("Artist - Song - Spotify Chart History", "Wrong title"))


def test_only_metadata_changes_and_no_recording_validation_is_granted(tmp_path):
    row = dict(
        candidate_id=KEY,
        country_code="PK",
        year=2025,
        position=7,
        metric_value=123,
        title=None,
        artist=None,
        identity_status="metadata_missing",
        not_for_paid_submission=True,
    )
    original = copy.deepcopy(row)
    assert apply_archive_repairs([row], {KEY: proof(tmp_path)}) == 1
    assert row["title"] == "Song" and row["artist"] == "Artist"
    assert row["identity_status"] == "native_id_pending_recording_review"
    assert row["metadata_resolution"]["source_identity_status"] == "metadata_missing"
    assert row["original_display_metadata"] == dict(title=None, artist=None)
    assert not row["metadata_resolution"]["recording_and_text_validation"]
    for field in (
        "position",
        "metric_value",
        "candidate_id",
        "country_code",
        "year",
        "not_for_paid_submission",
    ):
        assert row[field] == original[field]
    assert apply_archive_repairs([row], {KEY: proof(tmp_path)}) == 0


def test_conflict_is_atomic_and_existing_complete_names_are_preserved(tmp_path):
    empty = dict(candidate_id=KEY, title=None, artist=None)
    conflict = dict(candidate_id=KEY, title="Another Song", artist=None)
    with pytest.raises(ValueError, match="conflicts"):
        apply_archive_repairs([empty, conflict], {KEY: proof(tmp_path)})
    assert empty["title"] is None
    complete = dict(candidate_id=KEY, title="Original", artist="Original Artist")
    assert apply_archive_repairs([complete], {KEY: proof(tmp_path)}) == 0
    assert complete["title"] == "Original"


def test_whitespace_is_missing_metadata(tmp_path):
    row = dict(candidate_id=KEY, title="  ", artist=None)
    assert apply_archive_repairs([row], {KEY: proof(tmp_path)}) == 1
    assert row["title"] == "Song"
