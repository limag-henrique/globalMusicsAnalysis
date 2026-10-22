"""Export source song names by country and year from the project database."""

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

from chart_observatory.config import Settings

ROOT = Path(__file__).resolve().parents[1]
QUERY = text("""
    SELECT d.country_code, EXTRACT(YEAR FROM s.period_end)::int AS year,
           d.source_code, p.title, COALESCE(p.artist, '') AS artist,
           MIN(s.period_start) AS first_period_start, MAX(s.period_end) AS last_period_end,
           COUNT(DISTINCT (s.period_start, s.period_end)) AS observed_periods
    FROM chart_definitions d
    JOIN chart_snapshots s ON s.chart_definition_id = d.id
    JOIN chart_entries e ON e.snapshot_id = s.id
    JOIN platform_items p ON p.id = e.platform_item_id
    WHERE s.schema_version = 'web-titles-v1'
      AND s.period_end BETWEEN '2025-01-01' AND :cutoff
    GROUP BY d.country_code, EXTRACT(YEAR FROM s.period_end), d.source_code, p.title, p.artist
    ORDER BY d.country_code, year, d.source_code, p.title, p.artist
""")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/derived/web_chart_titles/20261021/song_names.csv",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    temporary = args.output.with_suffix(".part")
    count = 0
    try:
        with (
            engine.connect() as connection,
            temporary.open("w", encoding="utf-8-sig", newline="") as handle,
        ):
            result = connection.execution_options(stream_results=True).execute(
                QUERY, {"cutoff": "2026-10-21"}
            )
            writer = csv.writer(handle)
            writer.writerow(result.keys())
            for row in result.yield_per(1000):
                writer.writerow(row)
                count += 1
        temporary.replace(args.output)
    finally:
        engine.dispose()
    print(
        json.dumps(
            {
                "file": str(args.output),
                "country_year_source_song_pairs": count,
                "exported_at": datetime.now(UTC).isoformat(),
                "coverage": "Consult coverage_manifest.json; export may be partial",
            }
        )
    )


if __name__ == "__main__":
    main()
