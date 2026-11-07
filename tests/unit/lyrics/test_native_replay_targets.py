import hashlib
import json
from datetime import UTC, datetime

import pytest

from chart_observatory.lyrics.native_replay_targets import recent_native_targets


def evidence(tmp_path, *, native="one", timestamp="2026-10-31T20:00:00+00:00"):
    data = dict(
        status=200,
        source_url=f"https://open.spotify.com/embed/track/{native}",
        retrieved_at=timestamp,
        metadata=dict(uri=f"spotify:track:{native}", title="Song", artist="Artist"),
    )
    raw = json.dumps(data).encode()
    path = tmp_path / "proof.json"
    path.write_bytes(raw)
    return {
        "SPOTIFY:one": dict(
            evidence_file=str(path), evidence_sha256=hashlib.sha256(raw).hexdigest()
        )
    }, path


def test_recent_filter_is_scoped_and_has_no_implicit_full_selection(tmp_path):
    refs, _ = evidence(tmp_path)
    since = datetime(2026, 10, 31, 19, tzinfo=UTC)
    rows = recent_native_targets({"SPOTIFY:one"}, refs, since)
    assert [r["candidate_id"] for r in rows] == ["SPOTIFY:one"]
    assert recent_native_targets({"SPOTIFY:other"}, refs, since) == []
    assert recent_native_targets({"SPOTIFY:one"}, refs, datetime(2026, 11, 1, tzinfo=UTC)) == []


def test_changed_bytes_or_wrong_native_identity_are_rejected(tmp_path):
    refs, path = evidence(tmp_path)
    since = datetime(2026, 10, 31, tzinfo=UTC)
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        recent_native_targets({"SPOTIFY:one"}, refs, since)
    refs, _ = evidence(tmp_path, native="another")
    with pytest.raises(ValueError, match="another or unknown"):
        recent_native_targets({"SPOTIFY:one"}, refs, since)


def test_timezones_are_required_for_unambiguous_cutoffs(tmp_path):
    refs, _ = evidence(tmp_path, timestamp="2026-10-31T20:00:00")
    with pytest.raises(ValueError, match="observation"):
        recent_native_targets({"SPOTIFY:one"}, refs, datetime(2026, 10, 31, tzinfo=UTC))
    with pytest.raises(ValueError, match="cutoff"):
        recent_native_targets({"SPOTIFY:one"}, refs, datetime(2026, 10, 31))
