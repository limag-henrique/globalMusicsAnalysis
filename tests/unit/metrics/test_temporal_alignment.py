from datetime import date

import pytest

from chart_observatory.domain.enums import TemporalAlignmentPolicy
from chart_observatory.domain.errors import TemporalAlignmentRequired
from chart_observatory.metrics.temporal_alignment import NativePeriod, align_periods


def test_weekly_daily_alignment_requires_explicit_policy() -> None:
    daily = [NativePeriod(date(2026, 9, 1), date(2026, 9, 1), "DAILY")]
    weekly = [NativePeriod(date(2026, 8, 28), date(2026, 9, 3), "WEEKLY")]
    with pytest.raises(TemporalAlignmentRequired):
        align_periods(daily, weekly, policy=None)
    aligned = align_periods(daily, weekly, TemporalAlignmentPolicy.INTERVAL_OVERLAP)
    assert aligned == ((daily[0], weekly[0]),)
