from pathlib import Path

import httpx
import polars as pl
import pytest

from chart_observatory.analysis.traffic_pilot import export_traffic_pilot


def test_pilot_validates_country_and_preserves_zero_missing_and_raw_checkpoint(tmp_path: Path):
    annual = pl.DataFrame({"market_code": ["BR"], "year": [2021]})
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.params["country"] == "BR"
        month = request.url.params["display_date"]
        return httpx.Response(
            200,
            text=f"target;visits;country;display_date;device_type\npornhub.com;0;BR;{month};all\n",
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        export_traffic_pilot(
            annual, tmp_path, api_key="secret-fixture", client=client, collect=True, limit=1
        )
        export_traffic_pilot(
            annual, tmp_path, api_key="secret-fixture", client=client, collect=False, limit=1
        )
        assert len(calls) == 1
        export_traffic_pilot(
            annual, tmp_path, api_key="secret-fixture", client=client, collect=True, limit=1
        )
    assert [c.url.params["display_date"] for c in calls] == ["2021-01-01", "2021-02-01"]
    data = pl.read_csv(tmp_path / "monthly-visits.csv")
    assert data.filter(pl.col("status") == "observed")["visits"].to_list() == [0.0, 0.0]
    assert data.filter(pl.col("status") == "not_returned").height == 4
    assert "secret-fixture" not in "".join(p.read_text() for p in tmp_path.rglob("*.json"))


def test_pilot_rejects_global_response_for_country_request(tmp_path: Path) -> None:
    annual = pl.DataFrame({"market_code": ["BR"], "year": [2021]})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="target;visits;country;display_date;device_type\n"
            "pornhub.com;123;GLOBAL;2021-01-01;all\n",
        )

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="mismatch"),
    ):
        export_traffic_pilot(annual, tmp_path, api_key="fixture", client=client, collect=True)
    assert not list((tmp_path / "raw").glob("*.csv"))
