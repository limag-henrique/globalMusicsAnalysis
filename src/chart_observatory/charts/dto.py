from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class ChartEntryDTO:
    position: int
    native_id: str
    item_kind: str
    metric_value: Decimal | None
    metric_type: str
    raw_fields: dict[str, object]
    title: str | None = None


@dataclass(frozen=True)
class ChartPayload:
    source_code: str
    platform_code: str
    country_code: str
    chart_name: str
    native_frequency: str
    observed_at: datetime
    raw_bytes: bytes
    entries: tuple[ChartEntryDTO, ...]
    period_start: date | None = None
    period_end: date | None = None
    provider_metadata: dict[str, object] = field(default_factory=dict)

    def ordered(self) -> "ChartPayload":
        return replace(self, entries=tuple(sorted(self.entries, key=lambda entry: entry.position)))
