"""Freeze historical annual top 80 and a popularity-first acquisition queue."""

import argparse
import calendar
import hashlib
import json
from pathlib import Path

import polars as pl
from sqlalchemy import create_engine, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.annual_cohort import ANNUAL_COHORT_VERSION, select_annual_top80
from chart_observatory.sources.catalog import _country_aliases

ROOT = Path(__file__).resolve().parents[1]


def run(output: Path, ranked_cohort: Path | None = None):
    output.mkdir(parents=True, exist_ok=False)
    inputs = [ROOT / "data/normalized" / name for name in (
        "mgd_observations.parquet", "kaggle_spotify_observations.parquet",
    )]
    aliases = _country_aliases()
    observations = pl.concat([pl.scan_parquet(p) for p in inputs]).filter(
        (pl.col("origin_platform") == "SPOTIFY")
        & (pl.col("metric_type") == "STREAMS")
        & (pl.col("metric_value") >= 0)
        & (pl.col("period_start") == pl.col("period_end"))
        & (pl.col("period_start").dt.year() < 2026)
        & pl.col("chart_name").str.to_lowercase().str.contains("top")
    ).with_columns(
        pl.col("country_code").replace(aliases).alias("market_code"),
        pl.col("period_start").dt.year().alias("year"),
        pl.col("native_id").str.extract(r"(?:/track/)?([A-Za-z0-9]{22})(?:\?.*)?$", 1)
        .alias("chart_track_id"),
    ).filter(pl.col("chart_track_id").is_not_null())
    markets = pl.read_parquet(ROOT / "research/article/analysis-final/country-metrics.parquet")[
        "market_code"
    ].to_list()
    observations = observations.filter(pl.col("market_code").is_in(markets))
    cohort = (pl.read_parquet(ranked_cohort) if ranked_cohort
              else select_annual_top80(observations))
    cohort.write_parquet(output / "annual-top80.parquet")
    cohort.write_csv(output / "annual-top80.csv")
    years = list(range(cohort["year"].min(), 2026))
    grid = pl.DataFrame({"market_code": markets}).join(
        pl.DataFrame({"year": years}).cast({"year": cohort.schema["year"]}), how="cross",
    )
    coverage = grid.join(cohort.group_by("market_code", "year").agg(
        pl.len().alias("selected_tracks"), pl.col("observed_days").first(),
    ), on=["market_code", "year"], how="left").fill_null(0)
    coverage.write_csv(output / "country-year-coverage.csv")
    wanted = set(cohort["chart_track_id"].to_list())
    links, documents = {}, {}
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        snapshot = str(conn.execute(text("SELECT transaction_timestamp()")).scalar_one())
        for row in conn.execute(text("""
            SELECT p.native_id, l.canonical_track_id FROM platform_items p
            JOIN platform_item_track_links l ON l.platform_item_id=p.id
            WHERE p.platform_code='SPOTIFY'
        """)).mappings():
            if row["native_id"] in wanted:
                links.setdefault(row["native_id"], set()).add(str(row["canonical_track_id"]))
        for row in conn.execute(text("""
            SELECT id, canonical_track_id, content_sha256 FROM lyric_documents
            ORDER BY retrieved_at DESC, id
        """)).mappings():
            documents.setdefault(str(row["canonical_track_id"]), []).append({
                "document_id": str(row["id"]), "lyrics_hash": row["content_sha256"],
            })
    engine.dispose()
    # Historical imports retain exact native-ID lineage outside platform links.
    # Reuse that binding only while its document/hash still matches the database.
    lineage_path = ROOT / (
        "data/derived/research_quality/country-all-history-20261011-022524/"
        "recovered-original-id-lineage.parquet"
    )
    document_tracks = {
        (doc["document_id"], doc["lyrics_hash"]): canonical
        for canonical, docs in documents.items() for doc in docs
    }
    for row in pl.read_parquet(lineage_path).select(
        "chart_track_id", "document_id", "lyrics_hash",
    ).to_dicts():
        canonical = document_tracks.get((row["document_id"], row["lyrics_hash"]))
        if row["chart_track_id"] in wanted and canonical:
            links.setdefault(row["chart_track_id"], set()).add(canonical)
    # Preserve every market/year membership; fetch a shared recording only once.
    queue = {}
    for row in cohort.sort("annual_rank", "market_code", "year").to_dicts():
        native = row["chart_track_id"]
        candidates = links.get(native, set())
        canonical = next(iter(candidates)) if len(candidates) == 1 else None
        key = canonical or f"SPOTIFY:{native}"
        bindings = documents.get(canonical, [])
        target = queue.setdefault(key, {
            "document_id": bindings[0]["document_id"] if bindings else f"chart:{native}",
            "lyrics_hash": bindings[0]["lyrics_hash"] if bindings else "",
            "track_id": canonical, "recording_id": f"SPOTIFY:{native}",
            "title": row["track_title"], "artist": row["artist"],
            "chart_bindings": [], "document_bindings": bindings,
            "identity_status": "linked" if canonical else "pending_canonical_identity",
            "cohort_version": ANNUAL_COHORT_VERSION,
        })
        target["chart_bindings"].append(row)
    with (output / "recovery-targets.jsonl").open("x", encoding="utf-8") as handle:
        for target in queue.values():
            handle.write(json.dumps(target, ensure_ascii=False) + "\n")
    manifest = {
        "protocol": ANNUAL_COHORT_VERSION, "target_per_country_year": 80,
        "ranking": "observed daily chart streams summed within one provider/year",
        "provider_selection": "most chart days, then observation count, then provider name",
        "queue_order": "annual_rank ascending, market_code, year; shared recording deduplicated",
        "database_snapshot": snapshot, "cohort_memberships": cohort.height,
        "unique_acquisition_targets": len(queue),
        "complete_top80_cells": coverage.filter(pl.col("selected_tracks") == 80).height,
        "insufficient_cells": coverage.filter(pl.col("selected_tracks") < 80).height,
        "partial_year_cells": sum(0 < r["observed_days"] < 365 + calendar.isleap(r["year"])
                                  for r in coverage.to_dicts()),
        "input_sha256": {str(p): hashlib.file_digest(p.open("rb"), "sha256").hexdigest()
                         for p in [*inputs, lineage_path]},
        "year_2026_included": False, "lyric_validation_complete": False,
        "article_regenerated": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ranked-cohort", type=Path, help="Reuse an already frozen top80 ranking")
    args = parser.parse_args()
    run(args.output, args.ranked_cohort)
