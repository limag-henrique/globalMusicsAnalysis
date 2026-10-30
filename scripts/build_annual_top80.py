"""Build the capped article selection from verified metric captures (no network)."""

import argparse
import csv
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from import_web_chart_titles import validate_snapshot
from sqlalchemy import create_engine, text

from chart_observatory.config import Settings
from chart_observatory.ingestion.annual_selection import select_annual

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/annual_top80/20261021"
OUT = ROOT / "data/derived/annual_top80/20261021"
CUTOFF = date(2026, 10, 21)


def build(raw=RAW):
    inventory = json.loads((raw / "inventory_manifest.json").read_text(encoding="utf-8"))
    expected = {}
    for country in inventory["requested_markets"]:
        for year in (2025, 2026):
            end = min(date(year, 12, 31), CUTOFF)
            day = date(year, 1, 1)
            days = set()
            while day <= end:
                days.add(day.isoformat())
                day += timedelta(days=1)
            expected[country, year, "SPOTIFY"] = days
            expected[country, year, "YOUTUBE"] = (
                {p["end"] for p in inventory["periods"] if p["end"].startswith(str(year))}
                if country in inventory["available_markets"]
                else set()
            )

    def captures(paths):
        for path in paths:
            doc = validate_snapshot(json.loads(path.read_text(encoding="utf-8")))
            if doc.get("observed_country_code") != doc.get("country_code"):
                continue
            provider = doc["provider"]
            if provider not in ("YOUTUBE_CHARTS_WEB", "KWORB_SPOTIFY_WEB"):
                continue
            doc["provider"] = "YOUTUBE" if provider == "YOUTUBE_CHARTS_WEB" else "SPOTIFY"
            yield doc

    # Bound working memory to one country/year, rather than retaining all charts.
    paths = sorted(raw.glob("*_WEB_*.json"))
    groups = {}
    for path in paths:
        parts = path.name.split("_")
        groups.setdefault((parts[3], int(parts[4][:4])), []).append(path)
    result = dict(selections=[], coverage=[])
    for country, year in sorted({(c, y) for c, y, _ in expected}):
        group_expected = {
            key: value for key, value in expected.items() if key[:2] == (country, year)
        }
        selected = select_annual(captures(groups.get((country, year), [])), group_expected)
        for field in result:
            result[field].extend(selected[field])
    return result


def persist(engine, rows):
    """Replace only this article selection transactionally; preserve raw charts."""
    with engine.begin() as conn:
        conn.execute(
            text("""CREATE TABLE IF NOT EXISTS article_annual_top80 (
            country_code varchar(2) NOT NULL, year integer NOT NULL CHECK(year IN (2025,2026)),
            position integer NOT NULL CHECK(position BETWEEN 1 AND 80),
            platform varchar(10) NOT NULL CHECK(platform IN ('SPOTIFY','YOUTUBE')),
            title text NOT NULL, artist text NOT NULL,
            metric_value bigint NOT NULL CHECK(metric_value >= 0),
            cutoff date NOT NULL, methodology_version text NOT NULL,
            PRIMARY KEY(country_code,year,position))""")
        )
        # Serialize replacement against a second accidental builder.
        conn.execute(text("LOCK TABLE article_annual_top80 IN EXCLUSIVE MODE"))
        conn.execute(
            text("DELETE FROM article_annual_top80 WHERE cutoff=:cutoff"), {"cutoff": CUTOFF}
        )
        if rows:
            conn.execute(
                text("""INSERT INTO article_annual_top80
                (country_code,year,position,platform,title,artist,metric_value,cutoff,methodology_version)
                VALUES (:country_code,:year,:position,:platform,:title,:artist,:metric_value,
                        :cutoff,'annual-chart-metric-v1')"""),
                [dict(r, cutoff=CUTOFF) for r in rows],
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = build(args.raw)
    OUT.mkdir(parents=True, exist_ok=True)
    result["updated_at"] = datetime.now(UTC).isoformat()
    result["limit_per_country_year"] = 80
    result["cutoff"] = CUTOFF.isoformat()
    result["methodology"] = (
        "Sum of metrics while present in source charts, not all platform consumption. "
        "YouTube uses native week-end year (boundary weeks can cross calendar years). "
        "Spotify daily streams take priority only with a complete annual calendar. "
        "Missing coverage produces no final annual selection."
    )
    result["status"] = (
        "COMPLETE"
        if all(
            any(
                r["country"] == country and r["year"] == year and r["status"] == "COMPLETE"
                for r in result["coverage"]
            )
            for country, year in {(r["country"], r["year"]) for r in result["coverage"]}
        )
        else "INCOMPLETE"
    )
    if args.apply:
        engine = create_engine(
            Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5}
        )
        try:
            persist(engine, result["selections"])
        finally:
            engine.dispose()
    columns = ["country_code", "year", "platform", "position", "title", "artist", "metric_value"]
    part = OUT / "song_names.part"
    with part.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(result["selections"])
    part.replace(OUT / "song_names.csv")
    part = OUT / "selection_manifest.part"
    part.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    part.replace(OUT / "selection_manifest.json")
    print(
        json.dumps({"status": result["status"], "selected": len(result["selections"])}), flush=True
    )


if __name__ == "__main__":
    main()
