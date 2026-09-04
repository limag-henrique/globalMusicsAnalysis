from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class MetricObservation:
    period_start: date
    period_end: date
    rank: int
    native_frequency: str
    metric_type: str
    metric_value: Decimal | None
    resolved: bool


@dataclass(frozen=True)
class TrackPlatformCountrySummary:
    appearances: int
    distinct_periods: int
    days_or_weeks_in_chart: int
    period_unit: str
    first_period: date | None
    last_period: date | None
    peak_rank: int | None
    mean_rank: Decimal | None
    median_rank: Decimal | None
    top_10: int
    top_20: int
    top_50: int
    top_100: int
    stream_sum: Decimal | None
    view_sum: Decimal | None
    unit_sum: Decimal | None
    creation_sum: Decimal | None
    unresolved_numerator: int
    unresolved_denominator: int
