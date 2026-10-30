"""Import compact, browser-collected chart snapshots without fetching metadata or lyrics.

Usage: python scripts/import_web_chart_titles.py PATH [--apply]
PATH contains JSON files with source_url, country_code, period_start, period_end,
provider, platform, chart_name and rows (rank, title, artist, optional native_id).
Dry-run is the default. PostgreSQL inserts are batched, additive and idempotent.
"""

import argparse
import hashlib
import json
import time
from datetime import UTC, date, datetime
from itertools import batched
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from chart_observatory.config import Settings
from chart_observatory.db.models.charts import ChartDefinition, ChartEntry, ChartSnapshot
from chart_observatory.db.models.tracks import PlatformItem

CUTOFF = date(2026, 10, 21)
SOURCES = {
    "YOUTUBE_CHARTS_WEB": ("charts.youtube.com", "YOUTUBE_MUSIC", "WEEKLY_TOP_SONGS"),
    "KWORB_SPOTIFY_WEB": ("kworb.net", "SPOTIFY", "DAILY_TOP_200"),
    "KAGGLE_ASANICZKA_WEB": ("www.kaggle.com", "SPOTIFY", "DAILY_TOP_50"),
}


def validate_snapshot(raw):
    if not isinstance(raw, dict):
        raise ValueError("snapshot must be an object")
    provider = raw["provider"]
    if not isinstance(provider, str) or provider not in SOURCES:
        raise ValueError("unknown chart provider")
    host, platform, chart = SOURCES[provider]
    parsed = urlparse(raw["source_url"])
    if parsed.scheme != "https" or parsed.hostname != host:
        raise ValueError("unexpected source URL")
    country = raw["country_code"]
    if (
        not isinstance(country, str)
        or country != "GLOBAL"
        and not (
            len(country) == 2 and country.isascii() and country.isalpha() and country.isupper()
        )
    ):
        raise ValueError("invalid country")
    start, end = date.fromisoformat(raw["period_start"]), date.fromisoformat(raw["period_end"])
    observed_country = raw.get("observed_country_code")
    if observed_country is not None and observed_country != country:
        raise ValueError("rendered market differs from requested market")
    if not date(2024, 12, 27) <= start <= end <= CUTOFF or end.year not in (2025, 2026):
        raise ValueError("period outside requested window")
    if provider == "YOUTUBE_CHARTS_WEB" and (end - start).days != 6:
        raise ValueError("weekly chart must cover seven days")
    if provider == "YOUTUBE_CHARTS_WEB":
        expected = f"/charts/TopSongs/{country.lower()}/weekly/{end:%Y%m%d}"
        if parsed.path != expected:
            raise ValueError("source URL does not match country and period")
    elif start != end:
        raise ValueError("daily chart must have a single reference date")
    if provider == "KWORB_SPOTIFY_WEB" and parsed.path != (
        f"/spotify/country/{country.lower()}_daily.html"
    ):
        raise ValueError("source URL does not match country")
    if not isinstance(raw["rows"], list) or not 1 <= len(raw["rows"]) <= 200:
        raise ValueError("unexpected chart depth")
    rows = []
    positions = set()
    for row in raw["rows"]:
        if not isinstance(row, dict) or not isinstance(row.get("title"), str):
            raise ValueError("invalid title")
        title = row["title"].strip()
        artist = " ".join(str(row.get("artist") or "").split())
        rank = row["rank"]
        if not title or len(title) > 1000 or len(artist) > 1000:
            raise ValueError("invalid title/artist")
        if type(rank) is not int or not 1 <= rank <= 200 or rank in positions:
            raise ValueError("invalid or duplicate chart position")
        positions.add(rank)
        native = str(row.get("native_id") or "").strip()
        if not native:
            identity = json.dumps([title, artist], ensure_ascii=False)
            native = "web-derived:" + hashlib.sha256(identity.encode()).hexdigest()
        if len(native) > 500:
            raise ValueError("native ID too long")
        source_rank = row.get("source_rank", rank)
        if type(source_rank) is not int or not 1 <= source_rank <= 200:
            raise ValueError("invalid source rank")
        rows.append(
            {
                "rank": rank,
                "source_rank": source_rank,
                "title": title,
                "artist": artist,
                "native_id": native,
            }
        )
        if "metric_value" in row:
            value = row["metric_value"]
            if type(value) is not int or value < 0 or value > 2**63 - 1:
                raise ValueError("invalid reproduction metric")
            rows[-1]["metric_value"] = value
    if not rows:
        raise ValueError("empty chart")
    missing = raw.get("missing_title_positions", [])
    if (
        not isinstance(missing, list)
        or any(type(p) is not int or not 1 <= p <= 200 or p in positions for p in missing)
        or len(set(missing)) != len(missing)
    ):
        raise ValueError("invalid missing title positions")
    rows.sort(key=lambda row: row["rank"])
    return {
        "provider": provider,
        "platform": platform,
        "chart_name": chart,
        "country_code": country,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "source_url": raw["source_url"],
        "rows": rows,
        "missing_title_positions": missing,
        "observed_country_code": observed_country,
    }


def import_snapshot(session, raw, source_file):
    """Persist one chart in the caller's transaction, without per-song lookups."""
    doc = validate_snapshot(raw)
    content = {k: v for k, v in doc.items() if k != "observed_country_code"}
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(encoded.encode()).hexdigest()
    snapshot_id = uuid5(NAMESPACE_URL, "chart-observatory:web:" + checksum)
    compatible_ids = [snapshot_id]
    if not doc["missing_title_positions"] and all(
        r["source_rank"] == r["rank"] for r in doc["rows"]
    ):
        # Recognize the five pilot snapshots written before source-rank metadata
        # was added. Both lookups use the primary-key index, never a JSON scan.
        legacy = {k: v for k, v in content.items() if k != "missing_title_positions"}
        legacy["rows"] = [{k: v for k, v in r.items() if k != "source_rank"} for r in doc["rows"]]
        old_bytes = json.dumps(legacy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        compatible_ids.append(
            uuid5(
                NAMESPACE_URL,
                "chart-observatory:web:" + hashlib.sha256(old_bytes.encode()).hexdigest(),
            )
        )
    if session.scalar(select(ChartSnapshot.id).where(ChartSnapshot.id.in_(compatible_ids))):
        return 0
    definition_key = ":".join(
        doc[key] for key in ("provider", "platform", "country_code", "chart_name")
    )
    definition_id = uuid5(NAMESPACE_URL, "chart-observatory:web-definition:" + definition_key)
    definitions = session.info.setdefault("web_chart_definitions", {})
    if definition_key not in definitions:
        session.execute(
            insert(ChartDefinition)
            .values(
                id=definition_id,
                platform_code=doc["platform"],
                source_code=doc["provider"],
                country_code=doc["country_code"],
                chart_name=doc["chart_name"],
                native_frequency="WEEKLY" if doc["provider"] == "YOUTUBE_CHARTS_WEB" else "DAILY",
                nominal_depth=max(row["rank"] for row in doc["rows"]),
                methodology_version="web-titles-v1",
            )
            .on_conflict_do_nothing()
        )
        # Resolve existing natural keys rather than assume our UUID owns them.
        definitions[definition_key] = session.scalar(
            select(ChartDefinition.id).where(
                ChartDefinition.platform_code == doc["platform"],
                ChartDefinition.source_code == doc["provider"],
                ChartDefinition.country_code == doc["country_code"],
                ChartDefinition.chart_name == doc["chart_name"],
            )
        )
    definition_id = definitions[definition_key]
    items = {}
    for row in doc["rows"]:
        native = row["native_id"]
        items[native] = {
            "id": uuid5(NAMESPACE_URL, f"chart-observatory:web-item:{doc['platform']}:{native}"),
            "platform_code": doc["platform"],
            "native_id": native,
            "item_kind": "CATALOG_TRACK",
            "title": row["title"],
            "artist": row["artist"] or None,
        }
    cache = session.info.setdefault("web_chart_items", {})
    if len(cache) > 20_000:
        cache.clear()
    unseen = {
        native: item for native, item in items.items() if (doc["platform"], native) not in cache
    }
    if unseen:
        session.execute(insert(PlatformItem).values(list(unseen.values())).on_conflict_do_nothing())
        found = session.execute(
            select(PlatformItem.native_id, PlatformItem.id).where(
                PlatformItem.platform_code == doc["platform"],
                PlatformItem.native_id.in_(unseen),
            )
        ).all()
        cache.update({(doc["platform"], native): item_id for native, item_id in found})
    item_ids = {native: cache[(doc["platform"], native)] for native in items}
    session.execute(
        insert(ChartSnapshot).values(
            id=snapshot_id,
            chart_definition_id=definition_id,
            period_start=date.fromisoformat(doc["period_start"]),
            period_end=date.fromisoformat(doc["period_end"]),
            observed_at=datetime.now(UTC),
            checksum=checksum,
            schema_version="web-titles-v1",
            collector_version="web-dom-v1",
            entry_count=len(doc["rows"]),
            provider_metadata={
                "source_url": doc["source_url"],
                "source_file": str(source_file),
                "content_sha256": checksum,
                "title_only_collection": True,
                "identity_status": "SOURCE_ONLY_UNRECONCILED",
                "calendar_boundary": "NATIVE_WEEK_END_YEAR",
                "position_semantics": "SOURCE_ROW_ORDER",
                "missing_title_positions": doc["missing_title_positions"],
            },
        )
    )
    session.execute(
        insert(ChartEntry).values(
            [
                {
                    "id": uuid5(snapshot_id, str(row["rank"])),
                    "snapshot_id": snapshot_id,
                    "platform_item_id": item_ids[row["native_id"]],
                    "canonical_track_id": None,
                    "position": row["rank"],
                    "metric_type": "NONE",
                    "metric_value": None,
                    "raw_fields": {"source_rank": row["source_rank"]},
                }
                for row in doc["rows"]
            ]
        )
    )
    return len(doc["rows"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    files = sorted(args.path.rglob("*.json")) if args.path.is_dir() else [args.path]
    files = [path for path in files if not path.name.endswith("manifest.json")]
    result = {"snapshots": 0, "rows": 0, "inserted_rows": 0, "applied": args.apply}
    if args.apply:
        settings = Settings.load(Path(__file__).resolve().parents[1])
        engine = create_engine(settings.database_url, connect_args={"connect_timeout": 5})
        with Session(engine) as session:
            for paths in batched(files, 100):
                # At most 100 charts in memory; one durable commit per batch.
                documents = [
                    (path, validate_snapshot(json.loads(path.read_text(encoding="utf-8"))))
                    for path in paths
                ]
                with session.begin():
                    for path, document in documents:
                        result["inserted_rows"] += import_snapshot(session, document, path)
                        result["snapshots"] += 1
                        result["rows"] += len(document["rows"])
        engine.dispose()
    else:
        for path in files:
            document = validate_snapshot(json.loads(path.read_text(encoding="utf-8")))
            result["snapshots"] += 1
            result["rows"] += len(document["rows"])
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
