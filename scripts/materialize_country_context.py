"""Combine acquired contextual observations, preserving source-specific scales."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.analysis.country_context import DOMAINS, FIELDS

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, records: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    base = PROJECT_ROOT / "data/derived/country_context"
    parser.add_argument("--radar", type=Path, default=base / "recent/indicators.csv")
    parser.add_argument(
        "--trends", type=Path, default=base / "trends-browser/trends-browser-observations.csv"
    )
    parser.add_argument("--output", type=Path, default=base / "collected")
    args = parser.parse_args()
    trends = read_csv(args.trends)
    radar = [r for r in read_csv(args.radar) if r["source"] == "cloudflare_radar"]
    countries = sorted({r["country_iso2"] for r in trends} | {r["country_iso2"] for r in radar})
    records = [*trends, *radar]
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=True)
    write_csv(
        output / "indicators.csv",
        records,
        [*FIELDS, "comparison_group", "aggregation", "boundary_bucket"],
    )
    coverage = []
    domain_fields = []
    for domain in DOMAINS:
        prefix = domain.split(".")[0]
        domain_fields.extend([f"{prefix}_dns_share_percent", f"{prefix}_status"])
    for country in countries:
        tr = [r for r in trends if r["country_iso2"] == country]
        row = {
            "country_iso2": country,
            "trends_groups": str(len({r["comparison_group"] for r in tr})),
            "trends_languages": ",".join(sorted({r["language"] for r in tr})),
            "trends_sample_rows": str(sum(bool(r["sample_date"]) for r in tr)),
            "trends_numeric_rows": str(sum(bool(r["value"]) for r in tr)),
            "trends_censored_rows": str(
                sum(r["status"] == "below_reporting_threshold" for r in tr)
            ),
            "trends_boundary_rows": str(sum(r["boundary_bucket"] == "true" for r in tr)),
            "trends_pending_rows": str(sum(r["status"] == "pending_browser_export" for r in tr)),
        }
        for r in radar:
            if r["country_iso2"] == country:
                prefix = r["domain"].split(".")[0]
                row[f"{prefix}_dns_share_percent"] = r["value"]
                row[f"{prefix}_status"] = r["status"]
        coverage.append(row)
    coverage_fields = [
        "country_iso2",
        "trends_groups",
        "trends_languages",
        "trends_sample_rows",
        "trends_numeric_rows",
        "trends_censored_rows",
        "trends_boundary_rows",
        "trends_pending_rows",
        *domain_fields,
    ]
    write_csv(output / "country-coverage.csv", coverage, coverage_fields)
    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "countries": countries,
        "trends_statuses": dict(Counter(r["status"] for r in trends)),
        "radar_statuses": dict(Counter(r["status"] for r in radar)),
        "radar_missing": [
            {"country_iso2": r["country_iso2"], "domain": r["domain"]}
            for r in radar
            if r["status"] != "observed_dns_share"
        ],
        "rows": len(records),
        "inputs": {
            str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [args.trends, args.radar]
        },
        "outputs": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.csv")
        },
        "limitations": [
            "No combined consumption score or ranking is calculated",
            "Trends scales are specific to comparison_group and full query window",
            "Repeated porn anchors are preserved in their respective groups",
            "boundary_bucket marks nominal periods crossing the requested end",
            "DNS shares have a global domain denominator, not 68-country renormalization",
            "Local vocabulary is provisional; six language gaps remain in the plan",
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "countries": len(countries),
                "rows": len(records),
                "trends_statuses": summary["trends_statuses"],
                "radar_statuses": summary["radar_statuses"],
                "radar_missing": summary["radar_missing"],
            }
        )
    )


if __name__ == "__main__":
    main()
