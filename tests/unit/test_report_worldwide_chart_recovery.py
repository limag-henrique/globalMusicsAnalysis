import hashlib
import json

from scripts.report_worldwide_chart_recovery import build


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _campaign(tmp_path, *, conflict=False, include_week=True):
    state = tmp_path / "state"
    capture = {
        "country_code": "KE",
        "observed_country_code": "KE",
        "period_end": "2026-01-08",
        "observed_period_end": "2026-01-08",
        "source_url": "https://charts.youtube.com/charts/TopSongs/ke/weekly/20260108",
        "rows": [
            {
                "rank": 1,
                "source_rank": 1,
                "title": "Native title",
                "artist": "Native artist",
                "metric_value": 123,
                "native_entity_evidence": True,
                "native_rank": 1,
                "native_metric_value": 123,
                "native_artist_ids": [{"id": "/g/artist", "name": "Native artist"}],
                "representative_video_id": "abcdefghijk",
                "representative_video_is_recording_id": False,
                "display_metadata_conflict": conflict,
            }
        ],
    }
    capture_hash = _write_json(state / "captures" / "ke.json", capture)
    checkpoint = {}
    if include_week:
        checkpoint = {
            "KE/2026-01-08": {
                "status": "captured_discovery",
                "capture": "captures/ke.json",
                "sha256": capture_hash,
            }
        }
    _write_json(state / "checkpoint.json", checkpoint)
    _write_json(
        state / "campaign.json",
        {
            "selection_sha256": "a" * 64,
            "tasks": [
                {
                    "country_code": "KE",
                    "year": 2026,
                    "quota": 1,
                    "expected_period_ends": ["2026-01-08"],
                }
            ],
            "other_source_tasks": [],
        },
    )
    return state, capture_hash


def test_complete_calendar_emits_traceable_provisional_rows_but_never_approves(tmp_path):
    state, capture_hash = _campaign(tmp_path)
    report = build(state, tmp_path / "report")
    row = json.loads((tmp_path / "report" / "provisional-display-candidates.jsonl").read_text())

    assert report["provisional_display_candidates"] == 1
    assert report["annual_positions_added"] == 0
    assert report["scientific_approval"] is False
    assert row["weekly_evidence"] == [
        {
            "week_end": "2026-01-08",
            "rank": 1,
            "weekly_views": 123,
            "capture_sha256": capture_hash,
        }
    ]
    assert row["representative_video_ids"] == ["abcdefghijk"]
    assert row["recording_identity_validated"] is False
    assert row["annual_rank_certified"] is False


def test_rendered_metadata_conflict_keeps_provisional_source_row_in_review(tmp_path):
    state, _ = _campaign(tmp_path, conflict=True)
    build(state, tmp_path / "report")
    row = json.loads((tmp_path / "report" / "provisional-display-candidates.jsonl").read_text())
    cell = json.loads((tmp_path / "report" / "annual-calendars.jsonl").read_text())

    assert cell["rendered_native_metadata_conflicts"] == 1
    assert "rendered_native_metadata_conflicts" in cell["blockers"]
    assert row["source_metadata_review_required"] is True
    assert row["annual_rank_certified"] is False


def test_incomplete_calendar_does_not_emit_annual_candidate(tmp_path):
    state, _ = _campaign(tmp_path, include_week=False)
    report = build(state, tmp_path / "report")

    assert report["complete_calendar_cells"] == 0
    assert report["provisional_display_candidates"] == 0
    assert report["annual_positions_added"] == 0
