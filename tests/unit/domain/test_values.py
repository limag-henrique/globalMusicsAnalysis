from datetime import date

import pytest

from chart_observatory.domain.enums import ChartFrequency
from chart_observatory.domain.errors import DomainValidationError
from chart_observatory.domain.values import ChartPeriod, CountryCode, DateWindow, Rank


def test_weekly_period_remains_one_native_period() -> None:
    period = ChartPeriod.weekly(date(2026, 8, 28), date(2026, 9, 3))

    assert period.frequency is ChartFrequency.WEEKLY
    assert period.duration_days == 7
    assert period.as_native_periods() == (period,)


def test_daily_period_must_start_and_end_on_the_same_date() -> None:
    with pytest.raises(DomainValidationError, match="daily period"):
        ChartPeriod(
            start=date(2026, 9, 1),
            end=date(2026, 9, 2),
            frequency=ChartFrequency.DAILY,
        )


@pytest.mark.parametrize("rank", [0, -1])
def test_rank_must_be_positive(rank: int) -> None:
    with pytest.raises(DomainValidationError, match="positive"):
        Rank(rank)


def test_country_code_is_normalized_to_uppercase() -> None:
    assert CountryCode("br").value == "BR"


@pytest.mark.parametrize("country", ["B", "BRA", "B1", "ÇR"])
def test_country_code_must_be_two_ascii_letters(country: str) -> None:
    with pytest.raises(DomainValidationError, match="ASCII"):
        CountryCode(country)


def test_date_window_rejects_reversed_dates() -> None:
    with pytest.raises(DomainValidationError, match="end date"):
        DateWindow(start=date(2026, 9, 3), end=date(2026, 9, 2))
