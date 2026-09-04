from pathlib import Path

from chart_observatory.adapters.files.manual import ManualChartImporter

FIXTURES = Path(__file__).parents[3] / "fixtures" / "manual"


def test_preview_is_read_only_and_preserves_unknown_columns() -> None:
    importer = ManualChartImporter.for_preview()
    preview = importer.preview(FIXTURES / "valid_daily.csv", "manual_generic_v1")
    assert preview.valid_rows == 3
    assert preview.errors == ()
    assert preview.rows[0].raw_fields["label_note"] == "keep-me"
    assert importer.persisted_count == 0


def test_invalid_and_duplicate_ranks_are_reported() -> None:
    importer = ManualChartImporter.for_preview()
    invalid = importer.preview(FIXTURES / "invalid_rank.csv", "manual_generic_v1")
    duplicate = importer.preview(FIXTURES / "duplicate.csv", "manual_generic_v1")
    assert invalid.valid_rows == 0
    assert any("positive" in error.message for error in invalid.errors)
    assert any("duplicate rank" in error.message for error in duplicate.errors)


def test_weekly_period_is_not_expanded_and_null_metric_is_preserved() -> None:
    importer = ManualChartImporter.for_preview(overrides={"native_frequency": "WEEKLY"})
    preview = importer.preview(FIXTURES / "weekly_missing_metric.csv", "manual_generic_v1")
    assert preview.valid_rows == 1
    assert preview.rows[0].period_start.isoformat() == "2026-08-28"
    assert preview.rows[0].period_end.isoformat() == "2026-09-03"
    assert preview.rows[0].metric_value is None
