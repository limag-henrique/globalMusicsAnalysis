"""Reconcile exact Spotify item/stream sets before proposing missing-day repairs."""

import json
import os
from datetime import date
from pathlib import Path

os.environ.setdefault("POLARS_MAX_THREADS", "2")
import polars as pl

from chart_observatory.ingestion.historical_backfill import annual_ranks, archive_overlap_agrees

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "data/raw/historical_backfill/20261030/kaggle-dhruvildave-v85/full-top200.parquet"
OUT = ROOT / "data/derived/annual_revision/missing-day-reconciliation-v2-20261031"


def day_sets(frame):
    output = {}
    for (day,), rows in frame.partition_by("period_end", as_dict=True).items():
        variants = rows.group_by("native_id").agg(pl.col("metric_value").n_unique().alias("n"))
        if (
            rows["native_id"].null_count()
            or rows["metric_value"].null_count()
            or variants.filter(pl.col("n") != 1).height
        ):
            raise ValueError("missing identity/metric or contradictory daily native item")
        output[day] = dict(rows.select("native_id", "metric_value").iter_rows())
    return output


def main():
    OUT.mkdir(exist_ok=True)
    auxiliary = (
        pl.scan_parquet(ORIGINAL)
        .filter(
            pl.col("country_code").is_in(["RU", "IL"]) & (pl.col("period_end").dt.year() == 2021)
        )
        .select(
            "country_code",
            "period_end",
            "native_id",
            "title",
            "artist",
            "metric_value",
            "source_rank",
        )
        .collect()
    )
    primary = (
        pl.scan_parquet(ROOT / "data/normalized/mgd_observations.parquet")
        .filter(
            pl.col("country_code").is_in(["RU", "IL"])
            & (pl.col("period_start").dt.year() == 2021)
            & (pl.col("period_start") == pl.col("period_end"))
            & (pl.col("origin_platform") == "SPOTIFY")
            & pl.col("chart_name").str.to_lowercase().str.contains("top")
            & (pl.col("metric_type") == "STREAMS")
        )
        .select(
            "country_code",
            "period_end",
            pl.col("native_id").str.extract(r"(?:/track/)?([A-Za-z0-9]{22})(?:\?.*)?$", 1),
            pl.col("track_title").alias("title"),
            "artist",
            "metric_value",
        )
        .collect()
    )
    reports, repaired, ranks, coverage = [], [], [], []
    for country in ("RU", "IL"):
        old, new = [
            frame.filter(pl.col("country_code") == country) for frame in (primary, auxiliary)
        ]
        old_sets, new_sets = day_sets(old), day_sets(new)
        overlap = sorted(old_sets.keys() & new_sets.keys())
        conflicts = [str(day) for day in overlap if old_sets[day] != new_sets[day]]
        agreement = archive_overlap_agrees(old_sets, new_sets)
        additions = sorted(new_sets.keys() - old_sets.keys())
        complete_additions = all(
            len(new_sets[day]) == 200
            and sorted(new.filter(pl.col("period_end") == day)["source_rank"].to_list())
            == list(range(1, 201))
            for day in additions
        )
        report = dict(
            country_code=country,
            year=2021,
            primary_days=len(old_sets),
            auxiliary_days=len(new_sets),
            overlap_days=len(overlap),
            conflicting_overlap_dates=conflicts,
            proposed_dates=list(map(str, additions)),
            minimum_auxiliary_depth=min(map(len, new_sets.values()), default=0),
            exact_native_ids_and_metrics_match=bool(overlap) and not conflicts,
            overlap_agreement=agreement,
            added_days_have_200_native_items_and_contiguous_ranks=complete_additions,
        )
        if agreement["compatible"] and complete_additions and additions:
            patch = new.filter(pl.col("period_end").is_in(additions)).drop("source_rank")
            combined = pl.concat([old, patch])
            selected, cells = annual_ranks(
                combined,
                markets={country},
                year=2021,
                cutoff=date(2026, 10, 15),
                frequency="DAILY",
                platform="SPOTIFY",
                provider="RECONCILED_MGD_KAGGLE85_VERIFIED_OVERLAP",
            )
            ranks.extend(selected)
            coverage.extend(cells)
            repaired.append(combined)
            report["result_coverage"] = cells
        reports.append(report)
    if repaired:
        pl.concat(repaired).write_parquet(OUT / "reconciled-observations.parquet")
        pl.DataFrame(ranks).write_parquet(OUT / "rankings.parquet")
    (OUT / "audit.json").write_text(
        json.dumps(
            dict(cells=reports, coverage=coverage, recording_and_lyrics_validated=False), indent=2
        ),
        encoding="utf-8",
    )
    print(json.dumps(reports))


if __name__ == "__main__":
    main()
