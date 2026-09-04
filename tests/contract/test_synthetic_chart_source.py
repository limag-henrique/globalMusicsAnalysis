from datetime import UTC, datetime
from decimal import Decimal

from chart_observatory.charts.dto import ChartEntryDTO, ChartPayload
from chart_source_contract import assert_chart_payload_contract


def test_payload_preserves_raw_and_deterministic_rank_order() -> None:
    payload = ChartPayload(
        source_code="SYNTHETIC",
        platform_code="APPLE_MUSIC",
        country_code="BR",
        chart_name="most-played",
        native_frequency="DAILY",
        observed_at=datetime(2026, 9, 3, tzinfo=UTC),
        raw_bytes=b"raw",
        entries=(
            ChartEntryDTO(2, "b", "CATALOG_TRACK", None, "NONE", {}),
            ChartEntryDTO(1, "a", "CATALOG_TRACK", Decimal("10"), "STREAMS", {}),
        ),
    ).ordered()
    assert_chart_payload_contract(payload)
    assert payload.raw_bytes == b"raw"
    assert [entry.position for entry in payload.entries] == [1, 2]
    assert payload.entries[1].metric_value is None
