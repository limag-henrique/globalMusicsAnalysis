"""Audit downloaded public charts, merge whole sources, and prepare 2018-2026 import."""

import argparse
import csv
import json
import os
from datetime import date
from pathlib import Path

os.environ.setdefault("POLARS_MAX_THREADS", "2")
import polars as pl

from chart_observatory.ingestion.historical_backfill import (
    annual_ranks,
    integer_metric,
    merge_sources,
)
from chart_observatory.ingestion.import_quotas import load_quotas

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/historical_backfill/20261030"
OLD = ROOT / "data/derived/research_quality/import-quotas-20261030"


def write_csv(path, rows):
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def normalize_kaggle(raw, normalized, cutoff):
    if normalized.exists():
        return
    source = (
        pl.scan_csv(raw, infer_schema=False)
        .select(
            pl.col("country").str.to_uppercase().alias("country_code"),
            pl.col("date").str.to_date().alias("period_end"),
            pl.col("uri").str.strip_prefix("spotify:track:").alias("native_id"),
            pl.col("track_name").alias("title"),
            pl.col("artist_names").alias("artist"),
            pl.col("streams").cast(pl.Int64, strict=False).alias("metric_value"),
        )
        .filter(pl.col("period_end").is_between(date(2018, 1, 1), cutoff))
    )
    temporary = normalized.with_suffix(".part")
    source.sink_parquet(temporary, compression="zstd", row_group_size=65536)
    temporary.replace(normalized)


def build(output, cutoff, include_kaggle, normalized_kaggle=None):
    output.mkdir(parents=True, exist_ok=True)
    quotas = load_quotas(OLD / "country_quotas.csv")
    rankings, coverage = [], []
    for platform, prefix, metric, native in (
        ("YOUTUBE", "youtube_top100", "views", "key"),
        ("SPOTIFY", "spotify_top200", "streams", "track_id"),
    ):
        for year in range(2018, 2027):
            path = RAW / "zenodo-23645386" / f"{prefix}_positions_{year}.csv.gz"
            if not path.exists():
                raise FileNotFoundError(path)
            frame = pl.read_csv(path, infer_schema=False).select(
                pl.col("cc").str.to_uppercase().alias("country_code"),
                pl.col("week_end").str.to_date().alias("period_end"),
                pl.col(native).alias("native_id"),
                pl.col("title"),
                pl.col("artists").alias("artist"),
                integer_metric(metric).alias("metric_value"),
            )
            rows, cells = annual_ranks(
                frame,
                markets=quotas,
                year=year,
                cutoff=cutoff,
                frequency="WEEKLY",
                platform=platform,
                provider=f"ZENODO_23645386_{platform}",
            )
            rankings.extend(rows)
            coverage.extend(cells)
            print(json.dumps(dict(source=platform, year=year, cells=len(cells))), flush=True)
    if include_kaggle:
        raw = RAW / "kaggle-gonzalopezgil-v151/charts_songs_daily.csv"
        normalized = normalized_kaggle or output / "kaggle_daily.parquet"
        print(json.dumps(dict(phase="normalize_kaggle")), flush=True)
        normalize_kaggle(raw, normalized, cutoff)
        for year in range(2018, 2027):
            frame = (
                pl.scan_parquet(normalized)
                .filter(pl.col("period_end").dt.year() == year)
                .collect(engine="streaming")
            )
            rows, cells = annual_ranks(
                frame,
                markets=quotas,
                year=year,
                cutoff=cutoff,
                frequency="DAILY",
                platform="SPOTIFY",
                provider="KAGGLE_GONZALOPEZGIL_V151",
            )
            rankings, coverage = merge_sources(rankings, coverage, rows, cells)
            print(json.dumps(dict(source="KAGGLE_DAILY", year=year, cells=len(cells))), flush=True)
    with (OLD / "source_coverage.csv").open(encoding="utf-8-sig") as handle:
        old_coverage = list(csv.DictReader(handle))
    # Historical local coverage uses the same frozen cutoff, never compare distinct windows.
    old_coverage = [r for r in old_coverage if int(r["year"]) >= 2018]
    if cutoff != date(2026, 10, 15):
        raise ValueError("local snapshot cutoff differs: rebuild its calendars before merging")
    old_rankings = (
        pl.read_parquet(OLD / "rankings.parquet").filter(pl.col("year") >= 2018).to_dicts()
    )
    rankings, coverage = merge_sources(old_rankings, old_coverage, rankings, coverage)
    pl.DataFrame(rankings).write_parquet(output / "rankings.parquet")
    write_csv(output / "source_coverage.csv", coverage)
    (output / "country_quotas.csv").write_bytes((OLD / "country_quotas.csv").read_bytes())
    (output / "backfill-manifest.json").write_text(
        json.dumps(
            dict(
                years=[2018, 2026],
                cutoff=cutoff.isoformat(),
                ranked_items=len(rankings),
                source_cells=len(coverage),
                paid_calls=0,
                includes_kaggle_daily=include_kaggle,
                warning="Calendar completeness does not certify recording identity or chart depth",
            ),
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cutoff", type=date.fromisoformat, default=date(2026, 10, 15))
    parser.add_argument("--include-kaggle", action="store_true")
    parser.add_argument(
        "--normalized-kaggle",
        type=Path,
        help="Reuse a normalized cache with the same 2018-2026 cutoff",
    )
    args = parser.parse_args()
    build(args.output, args.cutoff, args.include_kaggle, args.normalized_kaggle)
