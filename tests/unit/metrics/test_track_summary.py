from datetime import date
from decimal import Decimal

from chart_observatory.metrics.models import MetricObservation
from chart_observatory.metrics.track_summary import summarize


def test_native_period_rank_and_unit_specific_metrics() -> None:
    rows = [
        MetricObservation(
            date(2026, 8, 1), date(2026, 8, 1), 5, "DAILY", "STREAMS", Decimal("1000"), True
        ),
        MetricObservation(
            date(2026, 8, 2), date(2026, 8, 2), 20, "DAILY", "STREAMS", Decimal("500"), True
        ),
        MetricObservation(
            date(2026, 8, 3), date(2026, 8, 3), 50, "DAILY", "VIEWS", Decimal("9000"), True
        ),
        MetricObservation(date(2026, 8, 3), date(2026, 8, 3), 99, "DAILY", "NONE", None, False),
    ]
    summary = summarize(rows)
    assert summary.appearances == 3
    assert summary.distinct_periods == 3
    assert summary.period_unit == "DAYS"
    assert summary.peak_rank == 5
    assert summary.mean_rank == Decimal("25")
    assert summary.median_rank == Decimal("20")
    assert (summary.top_10, summary.top_20, summary.top_50, summary.top_100) == (1, 2, 3, 3)
    assert summary.stream_sum == Decimal("1500")
    assert summary.view_sum == Decimal("9000")
    assert summary.unresolved_numerator == 1
    assert summary.unresolved_denominator == 4
    assert not hasattr(summary, "popularity_score")


def test_weekly_period_counts_once() -> None:
    summary = summarize(
        [MetricObservation(date(2026, 8, 28), date(2026, 9, 3), 1, "WEEKLY", "NONE", None, True)]
    )
    assert summary.appearances == 1
    assert summary.days_or_weeks_in_chart == 1
    assert summary.period_unit == "WEEKS"
