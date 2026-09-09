from __future__ import annotations

from collections.abc import Iterable

import polars as pl

from chart_observatory.ui.classifications import ContentClassification
from chart_observatory.ui.taxonomy import taxonomy_codes

CONTENT_PROFILE_SCHEMA = {
    "canonical_track_id": pl.String,
    "market_code": pl.String,
    "year": pl.Int32,
    "category": pl.String,
    "score": pl.Int64,
    "rank": pl.Int64,
    "exposure_weight": pl.Float64,
}


def classification_observations(
    observations: pl.DataFrame,
    classifications: Iterable[ContentClassification],
) -> pl.DataFrame:
    """Expand immutable classification records onto chart observations."""
    records = list(classifications)
    if observations.height == 0 or not records:
        return pl.DataFrame(schema=CONTENT_PROFILE_SCHEMA)
    required = {"canonical_track_id", "market_code", "period_start", "rank"}
    missing = required.difference(observations.columns)
    if missing:
        raise ValueError(f"content input is missing columns: {sorted(missing)}")
    scores = pl.DataFrame(
        [
            {"canonical_track_id": record.canonical_track_id, **record.scores}
            for record in records
        ],
        schema={"canonical_track_id": pl.String, **{code: pl.Int64 for code in taxonomy_codes()}},
    )
    long_scores = scores.unpivot(
        index="canonical_track_id", variable_name="category", value_name="score"
    )
    return (
        observations.filter(pl.col("canonical_track_id").is_not_null())
        .select("canonical_track_id", "market_code", "period_start", "rank")
        .join(long_scores, on="canonical_track_id", how="inner")
        .with_columns(
            pl.col("period_start").dt.year().cast(pl.Int32).alias("year"),
            (1 / pl.col("rank").cast(pl.Float64).clip(lower_bound=1)).alias("exposure_weight"),
        )
        .select(list(CONTENT_PROFILE_SCHEMA))
    )


def build_content_prevalence_dataset(rows: pl.DataFrame) -> pl.DataFrame:
    """Calculate category presence among track/category annotations."""
    schema = {
        "market_code": pl.String,
        "year": pl.Int32,
        "category": pl.String,
        "tracks_with_category": pl.UInt32,
        "annotated_track_denominator": pl.UInt32,
        "prevalence": pl.Float64,
    }
    if rows.height == 0:
        return pl.DataFrame(schema=schema)
    required = {"canonical_track_id", "market_code", "year", "category", "score"}
    missing = required.difference(rows.columns)
    if missing:
        raise ValueError(f"content prevalence input is missing columns: {sorted(missing)}")
    annotated = rows.filter(pl.col("score").is_not_null()).unique(
        subset=["canonical_track_id", "market_code", "year", "category"]
    )
    if annotated.height == 0:
        return pl.DataFrame(schema=schema)
    return (
        annotated.group_by("market_code", "year", "category")
        .agg(
            pl.col("canonical_track_id")
            .filter(pl.col("score") > 0)
            .n_unique()
            .alias("tracks_with_category"),
            pl.col("canonical_track_id").n_unique().alias("annotated_track_denominator"),
        )
        .with_columns(
            (
                pl.col("tracks_with_category") / pl.col("annotated_track_denominator")
            ).alias("prevalence")
        )
        .select(list(schema))
        .sort("market_code", "year", "category")
    )


def build_content_exposure_dataset(rows: pl.DataFrame) -> pl.DataFrame:
    """Calculate rank-weighted category exposure from annotated observations."""
    schema = {
        "market_code": pl.String,
        "year": pl.Int32,
        "category": pl.String,
        "weighted_exposure": pl.Float64,
        "observation_weight_denominator": pl.Float64,
        "exposure": pl.Float64,
    }
    if rows.height == 0:
        return pl.DataFrame(schema=schema)
    annotated = rows.filter(pl.col("score").is_not_null())
    if annotated.height == 0:
        return pl.DataFrame(schema=schema)
    weighted = annotated.with_columns(
        pl.when(pl.col("score") > 0)
        .then(pl.col("exposure_weight"))
        .otherwise(0.0)
        .alias("positive_weight")
    )
    return (
        weighted.group_by("market_code", "year", "category")
        .agg(
            pl.col("positive_weight").sum().alias("weighted_exposure"),
            pl.col("exposure_weight").sum().alias("observation_weight_denominator"),
        )
        .with_columns(
            (
                pl.col("weighted_exposure") / pl.col("observation_weight_denominator")
            ).alias("exposure")
        )
        .select(list(schema))
        .sort("market_code", "year", "category")
    )
