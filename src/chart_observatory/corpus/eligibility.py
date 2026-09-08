from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median


@dataclass(frozen=True)
class EligibilityRules:
    minimum_coverage: float = 0.95
    minimum_years: int = 3
    minimum_chart_depth: int = 100
    minimum_source_quality: float = 0.0

    def __post_init__(self) -> None:
        if not 0 < self.minimum_coverage <= 1:
            raise ValueError("minimum_coverage must be in (0, 1]")
        if self.minimum_years < 1:
            raise ValueError("minimum_years must be positive")
        if self.minimum_chart_depth < 1:
            raise ValueError("minimum_chart_depth must be positive")


@dataclass(frozen=True)
class ChartCellInput:
    provider: str
    platform_code: str
    country_code: str
    chart_family: str
    frequency: str
    periods: tuple[date, ...]
    depths: tuple[int, ...]
    source_quality: float = 1.0


@dataclass(frozen=True)
class EligibilityResult:
    cell: ChartCellInput
    first_date: date | None
    last_date: date | None
    expected_periods: int
    observed_periods: int
    coverage_ratio: float
    longest_gap: int
    number_of_tracks: int
    median_chart_depth: float
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class BalancedPanel:
    cells: tuple[EligibilityResult, ...]
    common_periods: tuple[date, ...]


def _step(frequency: str) -> timedelta:
    if frequency.upper() in {"WEEKLY", "WEEK"}:
        return timedelta(days=7)
    return timedelta(days=1)


def _expected_periods(first: date, last: date, frequency: str) -> tuple[date, ...]:
    step = _step(frequency)
    values: list[date] = []
    current = first
    while current <= last:
        values.append(current)
        current += step
    return tuple(values)


def evaluate_cell(cell: ChartCellInput, rules: EligibilityRules) -> EligibilityResult:
    periods = tuple(sorted(set(cell.periods)))
    first = periods[0] if periods else None
    last = periods[-1] if periods else None
    expected = _expected_periods(first, last, cell.frequency) if first and last else ()
    longest_gap = 0
    if periods and first is not None and last is not None:
        expected_set = set(expected)
        cursor = first
        gap = 0
        while cursor <= last:
            if cursor in expected_set and cursor not in periods:
                gap += 1
                longest_gap = max(longest_gap, gap)
            else:
                gap = 0
            cursor += _step(cell.frequency)
    ratio = len(periods) / len(expected) if expected else 0.0
    depth = float(median(cell.depths)) if cell.depths else 0.0
    span_days = (last - first).days + 1 if first and last else 0
    years = span_days / 365.2425
    reasons: list[str] = []
    if ratio < rules.minimum_coverage:
        reasons.append("COVERAGE_BELOW_THRESHOLD")
    if years < rules.minimum_years:
        reasons.append("INSUFFICIENT_YEARS")
    if depth < rules.minimum_chart_depth:
        reasons.append("CHART_DEPTH_BELOW_THRESHOLD")
    if cell.source_quality < rules.minimum_source_quality:
        reasons.append("SOURCE_QUALITY_BELOW_THRESHOLD")
    if not periods:
        reasons.append("NO_OBSERVATIONS")
    return EligibilityResult(
        cell=cell,
        first_date=first,
        last_date=last,
        expected_periods=len(expected),
        observed_periods=len(periods),
        coverage_ratio=ratio,
        longest_gap=longest_gap,
        number_of_tracks=0,
        median_chart_depth=depth,
        eligible=not reasons,
        reasons=tuple(reasons),
    )


def select_comparable_cells(
    cells: Iterable[ChartCellInput], rules: EligibilityRules
) -> tuple[EligibilityResult, ...]:
    results = tuple(evaluate_cell(cell, rules) for cell in cells)
    return tuple(result for result in results if result.eligible)


def select_balanced_panel(
    cells: Iterable[EligibilityResult],
    *,
    corpus_start: date | None = None,
    corpus_end: date | None = None,
) -> BalancedPanel:
    selected = tuple(result for result in cells if result.eligible)
    period_sets = [
        set(_expected_periods(result.first_date, result.last_date, result.cell.frequency))
        for result in selected
        if result.first_date and result.last_date
    ]
    common = set.intersection(*period_sets) if period_sets else set()
    if corpus_start:
        common = {period for period in common if period >= corpus_start}
    if corpus_end:
        common = {period for period in common if period <= corpus_end}
    return BalancedPanel(selected, tuple(sorted(common)))
