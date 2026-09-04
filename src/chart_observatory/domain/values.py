from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from chart_observatory.domain.enums import ChartFrequency, PlatformCode, SourceCode
from chart_observatory.domain.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class CountryCode:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.upper()
        if len(normalized) != 2 or not normalized.isascii() or not normalized.isalpha():
            raise DomainValidationError("country code must contain two ASCII letters")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Rank:
    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or self.value <= 0:
            raise DomainValidationError("rank must be a positive integer")

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True, slots=True)
class DateWindow:
    start: date
    end: date | None

    def __post_init__(self) -> None:
        if self.end is not None and self.end < self.start:
            raise DomainValidationError("end date must not precede start date")


@dataclass(frozen=True, slots=True)
class ChartPeriod:
    start: date
    end: date
    frequency: ChartFrequency

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise DomainValidationError("chart period end date must not precede start date")
        if self.frequency is ChartFrequency.DAILY and self.start != self.end:
            raise DomainValidationError("daily period must begin and end on the same date")
        if self.frequency is ChartFrequency.WEEKLY and self.duration_days != 7:
            raise DomainValidationError("weekly period must contain exactly seven calendar days")

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days + 1

    def as_native_periods(self) -> tuple[ChartPeriod, ...]:
        return (self,)

    @classmethod
    def daily(cls, value: date) -> ChartPeriod:
        return cls(start=value, end=value, frequency=ChartFrequency.DAILY)

    @classmethod
    def weekly(cls, start: date, end: date) -> ChartPeriod:
        return cls(start=start, end=end, frequency=ChartFrequency.WEEKLY)


@dataclass(frozen=True, slots=True)
class ChartKey:
    origin_platform: PlatformCode
    source_provider: SourceCode
    country: CountryCode
    chart_family: str
