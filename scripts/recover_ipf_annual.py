"""Recover public IPF annual performance tables using their public form session."""

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://ipf.si"
PAGE = BASE + "/ste-ustvarjalec/statistika/najbolj-predvajani-izvajalci-in-izvedbe/"
API = BASE + "/umbraco/Surface/AirPlaySurface/GetMusicPerformanceYearlyRankingsList"


def form(report_id, start, token):
    data = {
        "reportId": report_id,
        "draw": start // 100 + 1,
        "start": start,
        "length": 100,
        "term": "",
        "search[value]": "",
        "search[regex]": "false",
        "order[0][column]": 3,
        "order[0][dir]": "asc",
        "__RequestVerificationToken": token,
    }
    for i, key in enumerate(
        ["id", "reportGroupId", "year", "rank", "performer", "performance", "phonogramProducer"]
    ):
        for name, value in {
            "data": key,
            "name": key,
            "searchable": "true" if i > 2 else "false",
            "orderable": "true" if i > 2 else "false",
            "search[value]": "",
            "search[regex]": "false",
        }.items():
            data[f"columns[{i}][{name}]"] = value
    return data


def recover(output, years):
    output.mkdir(parents=True, exist_ok=False)
    captures, observations, checks = [], [], []
    session = requests.Session()
    session.headers["User-Agent"] = "ChartObservatory/1.0 (academic public source verification)"

    def preserve(response, name):
        response.raise_for_status()
        (output / name).write_bytes(response.content)
        captures.append(
            dict(
                path=name,
                url=response.url,
                status=response.status_code,
                sha256=hashlib.sha256(response.content).hexdigest(),
                retrieved_at=datetime.now(UTC).isoformat(),
            )
        )

    try:
        for year in years:
            url = PAGE + f"?y={year}"
            response = session.get(url, timeout=40)
            preserve(response, f"{year}-index.html")
            soup = BeautifulSoup(response.content, "html.parser")
            report_id = soup.select_one("#selected-report-id")["value"]
            token = soup.select_one('input[name="__RequestVerificationToken"]')["value"]
            records = []
            for start in range(0, 500, 100):
                time.sleep(1)
                response = session.post(
                    API,
                    data=form(report_id, start, token),
                    timeout=40,
                    headers={
                        "Referer": url,
                        "Origin": BASE,
                        "X-Requested-With": "XMLHttpRequest",
                        "RequestVerificationToken": token,
                    },
                )
                preserve(response, f"{year}-{start}.json")
                payload = response.json()
                if payload["recordsTotal"] != 500 or payload["recordsFiltered"] != 500:
                    raise ValueError("public table total changed; preserve and review")
                batch = payload["data"]
                if len(batch) != 100 or any(r["year"] != year for r in batch):
                    raise ValueError("annual table page/year mismatch")
                records.extend(batch)
            if [r["rank"] for r in records] != list(range(1, 501)):
                raise ValueError("ranks not exactly 1-500")
            rows = [
                dict(
                    country_code="SI",
                    year=year,
                    platform="NATIONAL_PUBLIC_PERFORMANCE",
                    provider="IPF",
                    period_start=None,
                    period_end=None,
                    position=r["rank"],
                    candidate_id=f"IPF:{year}:{r['id']}",
                    title=r["performance"],
                    artist=r["performer"],
                    metric_value=None,
                    phonogram_producer=r["phonogramProducer"],
                    source_report_id=report_id,
                    identity_status="chart_entry_pending_recording_review",
                )
                for r in records
            ]
            check = {
                "approved": False,
                "position_structure_valid": True,
                "reasons": ["source_period_bounds_unconfirmed"],
            }
            checks.append({**check, "rows": [], "source_period_definition_review_pending": True})
            observations.extend(rows)
            print(
                json.dumps(
                    {
                        "year": year,
                        "rows": len(rows),
                        "structural_pass": check["position_structure_valid"],
                        "scientific_approval": False,
                    }
                ),
                flush=True,
            )
    finally:
        (output / "manifest.json").write_text(
            json.dumps(
                {
                    "source": "IPF public annual performance statistics",
                    "captures": captures,
                    "checks": checks,
                    "rows": len(observations),
                    "scientific_approval": False,
                    "separate_stratum": True,
                    "publication_period_definition_pending": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf8",
        )
        (output / "observations.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in observations), encoding="utf8"
        )
        (output / "quota-candidates.jsonl").write_text(
            "".join(
                json.dumps(r, ensure_ascii=False) + "\n"
                for r in observations
                if r["position"] <= 110
            ),
            encoding="utf8",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2018, 2026)))
    args = parser.parse_args()
    recover(args.output, args.years)
