"""Verify the frozen baseline before generating provisional exclusion sensitivities."""

import argparse
import json
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "research/article/analysis-final"
CATALOG = ROOT / (
    "data/derived/research_quality/country-all-history-20261011-022524/"
    "unique-chart-track-market-year-source.parquet"
)


def aggregate(pairs, labels, dimensions):
    counts = pairs.group_by("market_code").agg(pl.len().alias("chart_tracks"))
    classified = pairs.join(labels, on="chart_track_id", validate="m:1")
    stats = classified.group_by("market_code").agg(
        pl.len().alias("classified_tracks"),
        *[(pl.col(d) >= 2).sum().alias(d + "_positive") for d in dimensions],
    )
    return counts.join(stats, on="market_code", how="left").with_columns(
        (pl.col("classified_tracks") / pl.col("chart_tracks")).alias("coverage"),
        *[(100 * pl.col(d + "_positive") / pl.col("classified_tracks"))
          .alias(d + "_pct") for d in dimensions],
    ).sort("market_code")


def run(audit: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    baseline = pl.read_parquet(FROZEN / "country-metrics.parquet")
    dimensions = pl.read_csv(FROZEN / "all-dimensions.csv")["metric"].to_list()
    labels = pl.read_parquet(FROZEN / "native-id-annotations.parquet")
    pairs = pl.read_parquet(CATALOG).filter(
        (pl.col("origin_platform") == "SPOTIFY")
        & pl.col("market_code").is_in(baseline["market_code"].to_list())
    ).select("market_code", "chart_track_id").unique()
    reproduced = aggregate(pairs, labels, dimensions)
    columns = ["chart_tracks", "classified_tracks", *[d + "_positive" for d in dimensions]]
    check = baseline.join(reproduced, on="market_code", suffix="_reproduced", validate="1:1")
    differences = {
        name: check.filter(pl.col(name) != pl.col(name + "_reproduced")).height
        for name in columns
    }
    verified = check.height == baseline.height and not any(differences.values())
    report = {"baseline_reproduced": verified, "different_markets_by_column": differences,
              "corrected_ranking": False, "human_validation_pending": True}
    (output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not verified:
        raise ValueError("baseline not reproduced; no ranking comparison generated")
    audited = pl.read_parquet(audit / "document-audit.parquet")
    scenarios = {
        "human_reports_only": audited.filter(pl.col("human_report"))["document_id"],
        "all_text_signals": audited.filter(pl.col("flags").list.len() > 0)["document_id"],
    }
    comparisons = []
    for name, documents in scenarios.items():
        remaining = labels.filter(~pl.col("document_id").is_in(documents.implode()))
        revised = aggregate(pairs, remaining, dimensions)
        revised.write_csv(output / f"{name}-country-metrics.csv")
        for dimension in dimensions:
            pct = dimension + "_pct"
            before = baseline.select(
                "market_code", pl.col(pct).alias("before_pct"),
                pl.col(pct).rank("min", descending=True).alias("before_rank"),
            )
            after = revised.select(
                "market_code", "classified_tracks", "coverage", pl.col(pct).alias("after_pct"),
                pl.col(pct).rank("min", descending=True).alias("after_rank"),
            )
            comparisons.append(before.join(after, on="market_code").with_columns(
                pl.lit(name).alias("scenario"), pl.lit(dimension).alias("dimension"),
                (pl.col("after_pct") - pl.col("before_pct")).alias("delta_pp"),
                (pl.col("after_rank").cast(pl.Int64) - pl.col("before_rank"))
                .alias("rank_change"),
            ))
    pl.concat(comparisons).write_csv(output / "provisional-rank-comparisons.csv")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.audit_dir, args.output_dir)))
