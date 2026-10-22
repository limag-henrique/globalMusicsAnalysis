"""Report verified weekly coverage from local captures, without network or database access."""

import argparse
import json
from collections import Counter
from pathlib import Path

from import_web_chart_titles import validate_snapshot
from scrape_youtube_chart_titles import OUTPUT, write_json_atomic


def coverage(directory):
    cells = {}
    invalid = []
    for path in sorted(directory.glob("YOUTUBE_CHARTS_WEB_*.json")):
        try:
            document = validate_snapshot(json.loads(path.read_text(encoding="utf-8")))
            if document.get("observed_country_code") == document["country_code"]:
                cells[(document["country_code"], document["period_end"])] = len(document["rows"])
        except (ValueError, KeyError, TypeError) as error:
            invalid.append({"file": path.name, "error": str(error)[:200]})
    inventory_path = directory / "inventory_manifest.json"
    inventory = (
        json.loads(inventory_path.read_text(encoding="utf-8")) if inventory_path.exists() else None
    )
    counts = Counter((country, end[:4]) for country, end in cells)
    rows = []
    if inventory:
        for country in inventory["available_markets"]:
            for year in ("2025", "2026"):
                expected = [p["end"] for p in inventory["periods"] if p["end"].startswith(year)]
                rows.append(
                    {
                        "country": country,
                        "year": int(year),
                        "collected_weeks": counts[country, year],
                        "expected_weeks": len(expected),
                        "missing_weeks": [end for end in expected if (country, end) not in cells],
                    }
                )
    return {
        "status": "COMPLETE"
        if inventory and rows and not invalid and all(not row["missing_weeks"] for row in rows)
        else "PARTIAL",
        "verified_weekly_snapshots": len(cells),
        "title_observations": sum(cells.values()),
        "inventory_available": inventory is not None,
        "coverage": rows,
        "invalid_files": invalid,
        "note": "Weekly source coverage by week-end year; Kworb daily snapshots excluded.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = coverage(args.input)
    write_json_atomic(args.input / "coverage_manifest.json", report)
    print(json.dumps({key: value for key, value in report.items() if key != "coverage"}))


if __name__ == "__main__":
    main()
