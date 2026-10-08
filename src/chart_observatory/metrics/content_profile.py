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

CHART_CELL_COLUMNS = (
    "provider",
    "origin_platform",
    "chart_family",
    "frequency",
    "native_period_days",
)


def _cell_columns(frame: pl.DataFrame) -> list[str]:
    return [column for column in CHART_CELL_COLUMNS if column in frame.columns]


def classification_observations(
    observations: pl.DataFrame,
    classifications: Iterable[ContentClassification],
) -> pl.DataFrame:
    """Expand immutable classification records onto chart observations."""
    records = list(classifications)
    track_ids = [record.canonical_track_id for record in records]
    if len(track_ids) != len(set(track_ids)):
        raise ValueError("multiple classifications for a track require explicit selection")
    if observations.height == 0:
        return pl.DataFrame(schema=CONTENT_PROFILE_SCHEMA)
    required = {"canonical_track_id", "market_code", "period_start", "rank"}
    missing = required.difference(observations.columns)
    if missing:
        raise ValueError(f"content input is missing columns: {sorted(missing)}")
    scores = pl.DataFrame(
        [{"canonical_track_id": record.canonical_track_id, **record.scores} for record in records],
        schema={"canonical_track_id": pl.String, **{code: pl.Int64 for code in taxonomy_codes()}},
    )
    long_scores = scores.unpivot(
        index="canonical_track_id", variable_name="category", value_name="score"
    )
    if "period_end" in observations.columns:
        observations = observations.with_columns(
            ((pl.col("period_end") - pl.col("period_start")).dt.total_days() + 1).alias(
                "native_period_days"
            )
        )
    cell_columns = _cell_columns(observations)
    categories = pl.DataFrame({"category": list(taxonomy_codes())})
    return (
        observations.filter(pl.col("canonical_track_id").is_not_null())
        .select("canonical_track_id", "market_code", "period_start", "rank", *cell_columns)
        .join(categories, how="cross")
        .join(long_scores, on=["canonical_track_id", "category"], how="left")
        .with_columns(
            pl.col("period_start").dt.year().cast(pl.Int32).alias("year"),
            (1 / pl.col("rank").cast(pl.Float64).clip(lower_bound=1)).alias("exposure_weight"),
        )
        .select(*CONTENT_PROFILE_SCHEMA, *cell_columns)
    )


def build_content_prevalence_dataset(rows: pl.DataFrame) -> pl.DataFrame:
    """Calculate category presence among track/category annotations."""
    schema: dict[str, type[pl.DataType] | pl.DataType] = {
        "market_code": pl.String,
        "year": pl.Int32,
        "category": pl.String,
        "tracks_with_category": pl.UInt32,
        "annotated_track_denominator": pl.UInt32,
        "prevalence": pl.Float64,
        "observed_track_denominator": pl.UInt32,
        "missing_tracks": pl.UInt32,
        "annotation_coverage": pl.Float64,
    }
    cell_columns = _cell_columns(rows)
    schema.update({column: rows.schema[column] for column in cell_columns})
    if rows.height == 0:
        return pl.DataFrame(schema=schema)
    required = {"canonical_track_id", "market_code", "year", "category", "score"}
    missing = required.difference(rows.columns)
    if missing:
        raise ValueError(f"content prevalence input is missing columns: {sorted(missing)}")
    groups = [*cell_columns, "market_code", "year", "category"]
    observed = rows.unique(subset=["canonical_track_id", *groups])
    return (
        observed.group_by(groups)
        .agg(
            pl.col("canonical_track_id")
            .filter(pl.col("score") > 0)
            .n_unique()
            .alias("tracks_with_category"),
            pl.col("canonical_track_id")
            .filter(pl.col("score").is_not_null())
            .n_unique()
            .alias("annotated_track_denominator"),
            pl.col("canonical_track_id").n_unique().alias("observed_track_denominator"),
        )
        .with_columns(
            (
                pl.col("tracks_with_category")
                / pl.when(pl.col("annotated_track_denominator") > 0).then(
                    pl.col("annotated_track_denominator")
                )
            ).alias("prevalence"),
            (pl.col("observed_track_denominator") - pl.col("annotated_track_denominator")).alias(
                "missing_tracks"
            ),
            (pl.col("annotated_track_denominator") / pl.col("observed_track_denominator")).alias(
                "annotation_coverage"
            ),
        )
        .select(list(schema))
        .sort(groups)
    )


def build_content_exposure_dataset(rows: pl.DataFrame) -> pl.DataFrame:
    """Calculate rank-weighted category exposure from annotated observations."""
    schema: dict[str, type[pl.DataType] | pl.DataType] = {
        "market_code": pl.String,
        "year": pl.Int32,
        "category": pl.String,
        "weighted_exposure": pl.Float64,
        "observation_weight_denominator": pl.Float64,
        "exposure": pl.Float64,
        "observed_weight_denominator": pl.Float64,
        "annotation_weight_coverage": pl.Float64,
        "weight_method": pl.String,
    }
    cell_columns = _cell_columns(rows)
    schema.update({column: rows.schema[column] for column in cell_columns})
    if rows.height == 0:
        return pl.DataFrame(schema=schema)
    groups = [*cell_columns, "market_code", "year", "category"]
    weighted = rows.with_columns(
        pl.when(pl.col("score") > 0)
        .then(pl.col("exposure_weight"))
        .otherwise(0.0)
        .alias("positive_weight")
    )
    return (
        weighted.group_by(groups)
        .agg(
            pl.col("positive_weight").sum().alias("weighted_exposure"),
            pl.col("exposure_weight")
            .filter(pl.col("score").is_not_null())
            .sum()
            .alias("observation_weight_denominator"),
            pl.col("exposure_weight").sum().alias("observed_weight_denominator"),
        )
        .with_columns(
            (
                pl.col("weighted_exposure")
                / pl.when(pl.col("observation_weight_denominator") > 0).then(
                    pl.col("observation_weight_denominator")
                )
            ).alias("exposure"),
            (
                pl.col("observation_weight_denominator") / pl.col("observed_weight_denominator")
            ).alias("annotation_weight_coverage"),
            pl.lit("inverse_rank_proxy_not_audience_share").alias("weight_method"),
        )
        .select(list(schema))
        .sort(groups)
    )
