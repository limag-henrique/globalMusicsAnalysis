import importlib.util
import json
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[3] / "scripts/autonomous_lyrics.py"
    spec = importlib.util.spec_from_file_location("targeted_scope_test", path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def test_targeted_filter_preserves_payloads_and_excludes_other_candidates(tmp_path):
    script = module()
    rows = [
        dict(
            recording_id="SPOTIFY:a",
            title="Song (Live)",
            chart_bindings=[dict(country_code="IL", year=2024, position=120)],
        ),
        dict(recording_id="SPOTIFY:b"),
    ]
    path = tmp_path / "ids.jsonl"
    path.write_text(json.dumps(dict(candidate_id="SPOTIFY:a")) + "\n", encoding="utf-8")
    selected, digest = script.filter_targeted_candidates(rows, path)
    assert selected == rows[:1]
    assert selected[0] is rows[0]
    assert len(digest) == 64


@pytest.mark.parametrize("content", ["", '{"candidate_id":"outside-selection"}\n'])
def test_empty_or_foreign_candidate_scope_rejected(tmp_path, content):
    script = module()
    path = tmp_path / "ids.jsonl"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="within current selection"):
        script.filter_targeted_candidates([dict(recording_id="SPOTIFY:a")], path)


def test_metadata_refresh_preserves_frozen_selection_bytes(tmp_path):
    script = module()
    path = tmp_path / "combined.jsonl"
    original = dict(
        candidate_id="SPOTIFY:a",
        country_code="BR",
        year=2025,
        position=1,
        metric_value=100,
        title="Original title",
        artist="Artist",
    )
    raw = (json.dumps(original) + "\n").encode()
    path.write_bytes(raw)
    script.preserve_selection_snapshot(
        path,
        [{**original, "title": "Native title", "metadata_resolution": {"duration_ms": 200000}}],
    )
    assert path.read_bytes() == raw
    with pytest.raises(ValueError, match="memberships or source metrics"):
        script.preserve_selection_snapshot(path, [{**original, "position": 2}])
    assert path.read_bytes() == raw


@pytest.mark.parametrize(
    "change",
    [
        dict(candidate_id="SPOTIFY:other"),
        dict(position=2),
        dict(country_code="AR"),
        dict(year=2026),
        dict(quota_main=200),
        dict(metric_value=99),
        dict(selection_status="PROVISIONAL_OBSERVED_PERIODS"),
    ],
)
def test_display_refresh_cannot_hide_changes_to_frozen_research(change):
    from chart_observatory.ingestion.quota_boundary import validate_display_only_refresh

    row = dict(
        candidate_id="SPOTIFY:a",
        country_code="BR",
        year=2025,
        position=1,
        quota_main=100,
        metric_value=100,
        selection_status="CALENDAR_ELIGIBLE",
    )
    with pytest.raises(ValueError, match="memberships or source metrics"):
        validate_display_only_refresh([{**row, **change}], [row])


def test_display_refresh_cannot_remove_or_duplicate_memberships():
    from chart_observatory.ingestion.quota_boundary import validate_display_only_refresh

    row = dict(candidate_id="SPOTIFY:a", country_code="BR", year=2025, position=1)
    for changed in ([], [row, row]):
        with pytest.raises(ValueError, match="memberships or source metrics"):
            validate_display_only_refresh(changed, [row])
