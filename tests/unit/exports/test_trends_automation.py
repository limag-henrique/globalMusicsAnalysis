import csv
import json
from pathlib import Path

import httpx

from chart_observatory.analysis.trends_automation import collect_trends


def test_automation_collects_english_and_native_terms_and_resumes(tmp_path: Path) -> None:
    annual = tmp_path / "annual.csv"
    annual.write_text("market_code,year\nBR,2021\n", encoding="utf-8")

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("explore"):
            payload = json.loads(request.url.params["req"])
            assert payload["comparisonItem"][0]["geo"] == "BR"
            return httpx.Response(
                200,
                text=")]}'"
                + json.dumps(
                    {
                        "widgets": [
                            {
                                "id": "TIMESERIES",
                                "token": "temporary-widget-token",
                                "request": payload,
                            }
                        ]
                    }
                ),
            )
        return httpx.Response(
            200,
            text=")]}',\n"
            + json.dumps(
                {
                    "default": {
                        "timelineData": [
                            {
                                "time": "1609632000",
                                "value": [0],
                                "hasData": [True],
                                "isPartial": False,
                            },
                            {
                                "time": "1610236800",
                                "value": [50],
                                "hasData": [True],
                                "isPartial": True,
                            },
                        ]
                    }
                }
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = collect_trends(annual, tmp_path / "out", client=client, wait=lambda seconds: None)
    assert result["completed_queries"] == 5
    with (tmp_path / "out/trends-observations.csv").open(encoding="utf-8-sig") as handle:
        records = list(csv.DictReader(handle))
    assert {r["language"] for r in records} == {"en", "pt"}
    assert {r["term"] for r in records} == {
        "porn",
        "pornography",
        "porn videos",
        "pornografia",
        "vídeos pornô",
    }
    assert {r["source"] for r in records} == {"google_trends_web_unofficial"}
    assert records[0]["value"] == "0.0"
    assert records[1]["status"] == "observed_partial_index"
    assert all(r["cross_country_comparable"] == "false" for r in records)
    assert "temporary-widget-token" not in "".join(
        p.read_text(encoding="utf-8-sig") for p in (tmp_path / "out").rglob("*.json")
    )

    def must_not_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Completed queries must be reused")

    with httpx.Client(transport=httpx.MockTransport(must_not_request)) as client:
        resumed = collect_trends(annual, tmp_path / "out", client=client, wait=lambda seconds: None)
    assert resumed["completed_queries"] == 5
    assert resumed["attempted_this_run"] == 0


def test_automation_stops_rate_limit_without_losing_measurements(tmp_path: Path) -> None:
    annual = tmp_path / "annual.csv"
    annual.write_text("market_code,year\nBR,2021\n", encoding="utf-8")
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(429, text="Too Many Requests"))
    ) as client:
        result = collect_trends(annual, tmp_path / "out", client=client, wait=lambda seconds: None)
    assert result["completed_queries"] == 0
    assert result["pending_queries"] == 5
    assert result["attempted_this_run"] == 1
    assert result["blocked"]["status"] == "rate_limited"
    with (tmp_path / "out/trends-observations.csv").open(encoding="utf-8-sig") as handle:
        assert all(r["value"] == "" for r in csv.DictReader(handle))
