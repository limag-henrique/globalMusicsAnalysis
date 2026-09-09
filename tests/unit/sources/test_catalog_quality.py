from datetime import date
from pathlib import Path

import polars as pl

from chart_observatory.sources.catalog import catalog_quality_report


def _write_sources(root: Path) -> tuple[Path, ...]:
    mgd = root / "mgd.parquet"
    pl.DataFrame(
        {
            "provider": ["MGD", "MGD"],
            "origin_platform": ["SPOTIFY", "SPOTIFY"],
            "country_code": ["BR", "BR"],
            "chart_name": ["Top 200", "Top 200"],
            "period_start": [date(2020, 1, 1), date(2020, 1, 2)],
            "period_end": [date(2020, 1, 1), date(2020, 1, 2)],
            "rank": [1, 2],
            "track_title": ["A", "B"],
            "artist": ["Artist A", "Artist B"],
            "native_id": ["a", "b"],
            "metric_value": [100.0, None],
        }
    ).write_parquet(mgd)
    return (mgd,)


def test_catalog_quality_report_counts_rows_markets_dates_and_null_metrics(tmp_path: Path) -> None:
    report = catalog_quality_report(_write_sources(tmp_path))

    assert report.to_dicts() == [
        {
            "provider": "MGD",
            "origin_platform": "SPOTIFY",
            "item_kind": "TRACK",
            "chart_family": "TOP_200",
            "rows": 2,
            "markets": 1,
            "date_start": date(2020, 1, 1),
            "date_end": date(2020, 1, 2),
            "null_metric_rows": 1,
        }
    ]


def test_catalog_quality_report_does_not_create_zero_rows_for_missing_chartmetric(
    tmp_path: Path,
) -> None:
    report = catalog_quality_report(_write_sources(tmp_path))

    assert "CHARTMETRIC" not in report["provider"].to_list()
