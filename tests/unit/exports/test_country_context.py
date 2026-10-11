import csv
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from chart_observatory.analysis.country_context import export_context


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def annual(tmp_path: Path) -> Path:
    path = tmp_path / "annual.csv"
    path.write_text("market_code,year\nBR,2021\nBR,2022\nUS,2021\nHK,2021\n", encoding="utf-8")
    return path


def test_export_preserves_missing_and_local_scales(tmp_path: Path) -> None:
    output = tmp_path / "out"
    export_context(annual(tmp_path), output)
    plan = rows(output / "query-plan.csv")
    assert {r["country_iso2"] for r in plan} == {"BR", "US"}
    assert any(r["term"] == "pornografia" and r["language"] == "pt" for r in plan)
    assert any(r["term"] == "pornography" and r["language"] == "en" for r in plan)
    assert {r["period_end"] for r in plan if r["year"] == "2022"} == {"2022-03-13"}
    indicators = rows(output / "indicators.csv")
    assert all(r["value"] == "" for r in indicators)
    assert all(r["status"] == "missing_input" for r in indicators)
    assert all(r["cross_country_comparable"] == "false" for r in indicators)


def trends_manifest(tmp_path: Path, query: dict[str, str], content: str) -> Path:
    raw = tmp_path / "trends.csv"
    raw.write_text(content, encoding="utf-8")
    manifest = tmp_path / "exports.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "query_id": query["query_id"],
                    "path": "trends.csv",
                    "value_column": "porn: (Brazil)",
                    "date_column": "Week",
                    "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                    "source_url": query["source_url"],
                    "exported_at": "2026-10-10T20:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )
    return manifest


def test_export_imports_original_trends_zero_and_censored_values(tmp_path: Path) -> None:
    source = annual(tmp_path)
    output = tmp_path / "out"
    export_context(source, output)
    query = next(
        r
        for r in rows(output / "query-plan.csv")
        if r["country_iso2"] == "BR" and r["year"] == "2021" and r["term"] == "porn"
    )
    manifest = trends_manifest(
        tmp_path,
        query,
        "Category: All categories\n\nWeek,porn: (Brazil)\n"
        "2021-01-03,0\n2021-01-10,100\n2021-01-17,<1\n",
    )
    export_context(source, output, trends_manifest=manifest)
    imported = [r for r in rows(output / "indicators.csv") if r["query_id"] == query["query_id"]]
    assert [r["value"] for r in imported] == ["0.0", "100.0", ""]
    assert imported[-1]["status"] == "below_reporting_threshold"
    assert all(r["scale"] == "google_trends_local_0_100" for r in imported)
    assert all(r["cross_country_comparable"] == "false" for r in imported)
    assert len(imported[0]["raw_sha256"]) == 64
    assert (output / "raw" / f"trends-{query['query_id']}.csv").read_bytes() == (
        tmp_path / "trends.csv"
    ).read_bytes()


def test_export_rejects_modified_trends_input(tmp_path: Path) -> None:
    source = annual(tmp_path)
    output = tmp_path / "out"
    export_context(source, output)
    query = rows(output / "query-plan.csv")[0]
    manifest = trends_manifest(tmp_path, query, "Week,porn: (Brazil)\n2021-01-03,10\n")
    (tmp_path / "trends.csv").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        export_context(source, output, trends_manifest=manifest)


def test_radar_export_keeps_domains_and_recent_window_separate(tmp_path: Path) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if int(request.url.params["limit"]) > 200:
            return httpx.Response(
                400,
                json={
                    "success": False,
                    "errors": [{"code": 2001, "message": "limit above max limit of 200"}],
                },
            )
        assert request.url.params["dateStart"] == "2026-09-01T00:00:00Z"
        assert request.url.params["dateEnd"] == "2026-10-01T00:00:00Z"
        assert request.url.params["domain"] in {"pornhub.com", "xvideos.com", "xnxx.com"}
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "top_0": [{"clientCountryAlpha2": "BR", "value": "12.5"}],
                    "meta": {
                        "normalization": "PERCENTAGE",
                        "dateRange": [
                            {"startTime": "2026-09-01T00:00:00Z", "endTime": "2026-10-01T00:00:00Z"}
                        ],
                        "lastUpdated": "2026-10-01T00:00:00Z",
                    },
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        export_context(
            annual(tmp_path),
            tmp_path / "out",
            radar_token="test-token",
            radar_start="2026-09-01",
            radar_end="2026-10-01",
            client=client,
        )
    radar = [r for r in rows(tmp_path / "out/indicators.csv") if r["source"] == "cloudflare_radar"]
    br = [r for r in radar if r["country_iso2"] == "BR"]
    assert len(br) == 3
    assert all(r["value"] == "12.5" and r["scope"] == "recent" for r in br)
    assert all(r["cross_country_comparable"] == "true" for r in br)
    assert all(
        r["status"] == "not_returned" and r["value"] == ""
        for r in radar
        if r["country_iso2"] == "US"
    )


def test_cli_exports_without_external_credentials(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from chart_observatory.cli import app

    result = CliRunner().invoke(
        app,
        [
            "country-context",
            "export",
            "--annual",
            str(annual(tmp_path)),
            "--output",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["countries"] == 2


def test_radar_http_error_does_not_turn_into_zero(tmp_path: Path) -> None:
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(429, json={"success": False})
            )
        ) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        export_context(
            annual(tmp_path),
            tmp_path / "out",
            radar_token="test-token",
            radar_start="2026-09-01",
            radar_end="2026-10-01",
            client=client,
        )
    assert not (tmp_path / "out/indicators.csv").exists()
