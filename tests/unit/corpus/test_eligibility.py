from datetime import date, timedelta

from chart_observatory.corpus.eligibility import (
    ChartCellInput,
    EligibilityRules,
    evaluate_cell,
    select_balanced_panel,
)


def test_eligibility_reports_coverage_gap_years_and_depth() -> None:
    start = date(2020, 1, 1)
    periods = tuple(start + timedelta(days=i) for i in range(365 * 3) if i != 100)
    result = evaluate_cell(
        ChartCellInput("MGD", "SPOTIFY", "BR", "TOP_200", "DAILY", periods, (200,)),
        EligibilityRules(minimum_coverage=0.9995, minimum_years=2, minimum_chart_depth=100),
    )
    assert result.coverage_ratio < 1.0
    assert result.longest_gap == 1
    assert "COVERAGE_BELOW_THRESHOLD" in result.reasons


def test_balanced_panel_uses_common_period_intersection() -> None:
    first_periods = tuple(date(2020, 1, 1) + timedelta(days=7 * i) for i in range(54))
    second_periods = tuple(date(2020, 1, 8) + timedelta(days=7 * i) for i in range(54))
    first = ChartCellInput("A", "SPOTIFY", "BR", "TOP_200", "WEEKLY", first_periods, (200,))
    second = ChartCellInput("A", "SPOTIFY", "US", "TOP_200", "WEEKLY", second_periods, (200,))
    rules = EligibilityRules(minimum_coverage=0.1, minimum_years=1, minimum_chart_depth=100)
    panel = select_balanced_panel(
        [evaluate_cell(first, rules), evaluate_cell(second, rules)], corpus_start=date(2020, 1, 8)
    )
    assert panel.common_periods[0] == date(2020, 1, 8)
