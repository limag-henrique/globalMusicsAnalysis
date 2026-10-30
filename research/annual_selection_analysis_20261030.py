"""Local descriptive sensitivity analysis; does not select or classify a corpus.

Uses one historical Spotify provider, never combines mirrored observations.
Native Spotify items remain distinct: this is not a reviewed recording census.
"""

import calendar
import json
import os
from pathlib import Path

os.environ.setdefault("POLARS_MAX_THREADS", "2")
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/research_quality/annual-selection-method-20261030"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = ROOT / "data/normalized/mgd_observations.parquet"
    result, selected_ids = [], {q: set() for q in (80, 200, 0.8, 0.9, 0.95, 0.975)}
    for year in range(2017, 2022):
        raw = pl.scan_parquet(source).filter(pl.col("period_start").dt.year() == year)
        daily = raw.group_by("country_code", "period_start", "native_id").agg(
            pl.col("metric_value").n_unique().alias("metric_variants"),
            pl.col("rank").n_unique().alias("rank_variants"),
            pl.col("metric_value").max().alias("streams"),
            pl.col("rank").min().alias("rank"),
        ).collect(engine="streaming")
        for market in sorted(daily["country_code"].unique()):
            if len(market) != 2:
                continue  # GLOBAL is a territory, not a country.
            d = daily.filter(pl.col("country_code") == market)
            periods = d.group_by("period_start").agg(pl.len().alias("depth"))
            expected = 366 if calendar.isleap(year) else 365
            conflicts = d.filter((pl.col("metric_variants") != 1) | (pl.col("rank_variants") != 1)).height
            invalid = d.filter(pl.col("streams").is_null() | (pl.col("streams") < 0) | pl.col("native_id").is_null()).height
            row = dict(country_code=market, year=year, provider="MGD", observed_days=periods.height,
                       expected_days=expected, minimum_depth=int(periods["depth"].min()),
                       median_depth=float(periods["depth"].median()), conflicting_items=conflicts,
                       invalid_items=invalid)
            row["complete_calendar"] = periods.height == expected
            row["full_depth_calendar"] = row["complete_calendar"] and row["minimum_depth"] == 200
            annual = d.group_by("native_id").agg(pl.col("streams").sum()).sort(
                ["streams", "native_id"], descending=[True, False])
            weights = annual["streams"].to_list()
            total = sum(weights)
            row.update(annual_items=annual.height, observed_chart_streams=total)
            if total and not conflicts and not invalid:
                cumulative, running = [], 0
                for value in weights:
                    running += value
                    cumulative.append(running / total)
                for n in (50, 80, 100, 150, 200, 300, 500):
                    row[f"coverage_top{n}"] = cumulative[min(n, len(cumulative))-1]
                for q in (0.8, 0.9, 0.95, 0.975):
                    n = next(i+1 for i, c in enumerate(cumulative) if c >= q)
                    row[f"n_for_{q*100:g}pct"] = n
                row["effective_items_inverse_simpson"] = total**2 / sum(v*v for v in weights)
                if row["full_depth_calendar"]:
                    for q in selected_ids:
                        n = q if isinstance(q, int) else row[f"n_for_{q*100:g}pct"]
                        selected_ids[q].update(annual["native_id"].head(n).to_list())
            result.append(row)
        print(json.dumps({"year": year, "cells": len(result)}), flush=True)
    pl.DataFrame(result).write_csv(OUT / "country_year_sensitivity.csv")
    complete = [r for r in result if r["full_depth_calendar"] and not r["conflicting_items"] and not r["invalid_items"]]
    summary = dict(source=str(source.relative_to(ROOT)), years=[2017, 2021], cells=len(result),
                   full_depth_complete_cells=len(complete), excluded_global="GLOBAL is not a country",
                   union_native_ids_complete_cells={str(k): len(v) for k,v in selected_ids.items()},
                   note="Observed daily chart streams only. Identity and calendar audits remain provisional.")
    # Keep global markets out of country summaries, if the input ever adds them.
    assert all(len(r["country_code"]) == 2 for r in result)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
