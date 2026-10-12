"""Auditable annual context exports for the existing exploratory musical corpus."""

from pathlib import Path

import polars as pl

EXCLUDED_MARKETS = {"GLOBAL", "HK", "PR"}


def export_crossings(
    annual: pl.DataFrame,
    observations: pl.DataFrame,
    indicators: list[str],
    output: Path,
) -> dict[str, int]:
    """Export exact-year joins; preserve absent values and reject ambiguous keys."""
    annual = annual.filter(~pl.col("market_code").is_in(EXCLUDED_MARKETS))
    if annual.select(pl.struct("market_code", "year").n_unique()).item() != annual.height:
        raise ValueError("Duplicate market/year musical records")
    keys = ["market_code", "reference_year", "indicator_code"]
    if observations.select(pl.struct(keys).n_unique()).item() != observations.height:
        raise ValueError("Duplicate market/year/indicator observations")
    output.mkdir(parents=True, exist_ok=True)
    scope = annual.select("market_code", pl.col("year").alias("reference_year"))
    grid = scope.join(pl.DataFrame({"indicator_code": indicators}), how="cross")
    records = observations.join(scope, on=["market_code", "reference_year"], how="semi")
    if "coverage_status" not in records.columns:
        records = records.with_columns(
            pl.when(pl.col("value").is_not_null())
            .then(pl.lit("observed"))
            .otherwise(pl.lit("source_missing"))
            .alias("coverage_status")
        )
    coverage = grid.join(records, on=keys, how="left", validate="1:1").with_columns(
        pl.col("coverage_status").fill_null("not_returned")
    )
    wide = (
        coverage.select(*keys, "value")
        .pivot(on="indicator_code", index=["market_code", "reference_year"], values="value")
        .rename({"reference_year": "year"})
    )
    panel = annual.join(wide, on=["market_code", "year"], how="left", validate="1:1")
    panel = panel.with_columns(
        (pl.col("year").cast(pl.String) + "-01-01").alias("music_period_start"),
        pl.when(pl.col("year") == 2022)
        .then(pl.lit("2022-03-13"))
        .otherwise(pl.col("year").cast(pl.String) + "-12-31")
        .alias("music_period_end"),
        pl.when(pl.col("year") == 2022)
        .then(pl.lit("annual_context_extends_beyond_music"))
        .otherwise(pl.lit("same_calendar_year_context"))
        .alias("temporal_alignment"),
    )
    for name, frame in [
        ("country-context-observations", records),
        ("coverage", coverage),
        ("country-year-crossings", panel),
    ]:
        frame.write_csv(output / f"{name}.csv")
        frame.write_parquet(output / f"{name}.parquet")
    return {
        "country_years": panel.height,
        "coverage_cells": coverage.height,
        "observed_cells": coverage.filter(pl.col("value").is_not_null()).height,
    }
