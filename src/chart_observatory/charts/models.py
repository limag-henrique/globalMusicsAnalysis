from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class ChartObservation:
    snapshot_id: UUID
    platform_item_id: UUID
    position: int
    observed_at: datetime
    period_start: date
    period_end: date
    metric_value: Decimal | None = None
