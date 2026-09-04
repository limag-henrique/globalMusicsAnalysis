from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from chart_observatory.charts.dto import ChartEntryDTO, ChartPayload
from chart_observatory.charts.ingestion import ChartIngestionService, IngestionResult
from chart_observatory.charts.ports import CurrentChartRequest
from chart_observatory.charts.registry import AdapterRegistration, AdapterRegistry


class SyntheticSource:
    def fetch_current(self, request: CurrentChartRequest) -> ChartPayload:
        return ChartPayload(
            "SYNTHETIC",
            "APPLE_MUSIC",
            request.country_code,
            request.chart_name,
            "DAILY",
            datetime(2026, 9, 4, tzinfo=UTC),
            b"raw",
            (
                ChartEntryDTO(2, "b", "CATALOG_TRACK", None, "NONE", {}),
                ChartEntryDTO(1, "a", "CATALOG_TRACK", Decimal("1"), "STREAMS", {}),
            ),
        )


class CapturingSink:
    def __init__(self) -> None:
        self.positions: list[int] = []

    def persist(self, payload, checksum, period_start, period_end) -> IngestionResult:
        self.positions = [entry.position for entry in payload.entries]
        return IngestionResult(uuid4(), len(payload.entries), checksum)


def test_ingestion_orders_entries_and_checksums_raw_payload() -> None:
    source_id = uuid4()
    registry = AdapterRegistry()
    registry.register(AdapterRegistration("SYNTHETIC", source_id, SyntheticSource(), True))
    sink = CapturingSink()
    result = ChartIngestionService(registry, sink).ingest_current(
        "SYNTHETIC",
        CurrentChartRequest("BR", "synthetic"),
        datetime(2026, 9, 4, tzinfo=UTC),
    )
    assert sink.positions == [1, 2]
    assert (
        result.artifact_sha256 == "d7439bee24773bcbfa2d0a97947ee36227b10d1022b1a55847e928965bb6bfde"
    )
