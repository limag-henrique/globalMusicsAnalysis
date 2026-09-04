from chart_observatory.charts.dto import ChartPayload


def assert_chart_payload_contract(payload: ChartPayload) -> None:
    assert payload.raw_bytes
    assert [entry.position for entry in payload.ordered().entries] == sorted(
        entry.position for entry in payload.entries
    )
    assert all(entry.position > 0 for entry in payload.entries)
    assert all(entry.native_id for entry in payload.entries)
