from datetime import date

from chart_observatory.sources.chartmetric_backfill import (
    BackfillRequest,
    ChartmetricBackfillPlanner,
    _write_observations,
)


def test_backfill_planner_intersects_each_market_with_provider_dates() -> None:
    request = BackfillRequest(
        platform="spotify",
        countries=("BR", "US"),
        interval="daily",
        chart_type="plays",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 3),
        available_dates_by_country={
            "BR": (date(2025, 1, 1), date(2025, 1, 3)),
            "US": (date(2025, 1, 2),),
        },
    )

    tasks = ChartmetricBackfillPlanner().plan(request)

    assert [(task.country_code, task.period) for task in tasks] == [
        ("BR", date(2025, 1, 1)),
        ("BR", date(2025, 1, 3)),
        ("US", date(2025, 1, 2)),
    ]


def test_empty_provider_page_does_not_create_incompatible_parquet_schema(tmp_path) -> None:
    output = tmp_path / "empty.parquet"

    _write_observations(output, ())

    assert not output.exists()
