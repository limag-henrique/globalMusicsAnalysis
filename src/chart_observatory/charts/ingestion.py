from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from chart_observatory.charts.dto import ChartPayload
from chart_observatory.charts.ports import CurrentChartRequest
from chart_observatory.charts.registry import AdapterRegistry
from chart_observatory.domain.enums import RightsOperation


@dataclass(frozen=True)
class IngestionResult:
    snapshot_id: UUID
    entry_count: int
    artifact_sha256: str


class IngestionSink(Protocol):
    def persist(
        self, payload: ChartPayload, checksum: str, period_start: date, period_end: date
    ) -> IngestionResult: ...


class ChartIngestionService:
    """Coordinates authorization before delegating persistence to an injected sink."""

    def __init__(self, registry: AdapterRegistry, sink: IngestionSink) -> None:
        self.registry = registry
        self.sink = sink

    def ingest_current(
        self, source_code: str, request: CurrentChartRequest, occurred_at: datetime | None = None
    ) -> IngestionResult:
        now = occurred_at or datetime.now(UTC)
        adapter = self.registry.get_enabled(source_code, RightsOperation.FETCH, now)
        payload = adapter.fetch_current(request).ordered()
        return self.sink.persist(
            payload,
            sha256(payload.raw_bytes).hexdigest(),
            payload.period_start or date.fromisoformat(now.date().isoformat()),
            payload.period_end or date.fromisoformat(now.date().isoformat()),
        )
