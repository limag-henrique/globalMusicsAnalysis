from __future__ import annotations

import re
from collections.abc import Mapping

import polars as pl

DEFAULT_PRECEDENCE: dict[str, int] = {
    "MGD": 0,
    "KAGGLE_DHRUVILDAVE": 1,
    "CHARTMETRIC": 2,
    "PRO_MUSICA_BRASIL": 3,
    "YOUTUBE_DATA_API": 4,
}

_GROUP_COLUMNS = [
    "origin_platform",
    "market_code",
    "chart_family",
    "period_start",
    "period_end",
    "canonical_track_id",
]

_SPOTIFY_ID_PATTERN = re.compile(
    r"(?:spotify:track:|/track/)?([A-Za-z0-9]{22})(?:[/?].*)?$"
)


def canonical_track_reference(value: str) -> str:
    """Normalize a Spotify ID/URL to the catalog's canonical reference."""
    match = _SPOTIFY_ID_PATTERN.fullmatch(value.strip())
    return f"canonical:spotify:{match.group(1)}" if match else value


def reconcile_catalog(
    frame: pl.DataFrame,
    precedence: Mapping[str, int] | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Resolve strong native-ID evidence and report source conflicts.

    The returned observations retain one row per source observation. A Spotify
    track ID is considered exact evidence across providers only when the item is
    a track; video IDs never resolve to tracks. Title/artist similarity is not
    sufficient evidence and remains ``UNRESOLVED``.
    """
    if frame.height == 0:
        return frame, pl.DataFrame()
    ranking = dict(precedence or DEFAULT_PRECEDENCE)
    enriched = frame.with_columns(
        _identity_key().alias("_identity_key"),
    ).with_columns(
        pl.when(pl.col("_identity_key").is_not_null())
        .then(pl.concat_str([pl.lit("canonical:"), pl.col("_identity_key")]))
        .otherwise(pl.lit(None, dtype=pl.String))
        .alias("canonical_track_id"),
    ).with_columns(
        pl.when(pl.col("canonical_track_id").is_not_null())
        .then(pl.lit("MATCHED_EXACT"))
        .otherwise(pl.lit("UNRESOLVED"))
        .alias("resolution_status"),
        _priority_expression(ranking).alias("_provider_priority"),
    )

    grouped = (
        enriched.filter(pl.col("canonical_track_id").is_not_null())
        .group_by(_GROUP_COLUMNS)
        .agg(
            pl.col("provider").n_unique().alias("provider_count"),
            pl.col("rank").n_unique().alias("rank_count"),
            pl.col("metric_type").n_unique().alias("metric_type_count"),
            pl.col("metric_value").n_unique().alias("metric_value_count"),
            pl.col("source_observation_key").sort().alias("source_observation_keys"),
        )
        .with_columns(
            (
                (pl.col("provider_count") > 1)
                & (
                    (pl.col("rank_count") > 1)
                    | (pl.col("metric_type_count") > 1)
                    | (pl.col("metric_value_count") > 1)
                )
            ).alias("has_conflict")
        )
    )
    selections = (
        enriched.filter(pl.col("canonical_track_id").is_not_null())
        .sort(_GROUP_COLUMNS[:-1] + ["canonical_track_id", "_provider_priority", "provider"])
        .group_by(_GROUP_COLUMNS)
        .agg(
            pl.col("provider").first().alias("selected_provider"),
            pl.col("source_observation_key").sort().alias("source_observation_keys"),
        )
    )
    canonical = (
        enriched.join(
            selections.select(_GROUP_COLUMNS + ["selected_provider"]),
            on=_GROUP_COLUMNS,
            how="left",
        )
        .join(
            grouped.select(_GROUP_COLUMNS + ["source_observation_keys", "has_conflict"]),
            on=_GROUP_COLUMNS,
            how="left",
            suffix="_group",
        )
        .with_columns(
            pl.when(pl.col("has_conflict").fill_null(False))
            .then(pl.lit("SOURCE_CONFLICT"))
            .otherwise(pl.lit("NONE"))
            .alias("conflict_status")
        )
        .drop("_identity_key", "_provider_priority", "has_conflict")
    )
    conflicts = (
        grouped.filter(pl.col("has_conflict"))
        .select(
            *_GROUP_COLUMNS,
            "source_observation_keys",
            pl.lit("SOURCE_CONFLICT").alias("conflict_status"),
        )
        .sort(_GROUP_COLUMNS)
    )
    return canonical, conflicts


def canonicalize_catalog_lazy(frame: pl.LazyFrame) -> pl.LazyFrame:
    """Add exact-ID resolution metadata without eager grouping or joins."""
    identity = _identity_key()
    return (
        frame.with_columns(identity.alias("_identity_key"))
        .with_columns(
            pl.when(pl.col("_identity_key").is_not_null())
            .then(pl.concat_str([pl.lit("canonical:"), pl.col("_identity_key")]))
            .otherwise(pl.lit(None, dtype=pl.String))
            .alias("canonical_track_id"),
            pl.when(pl.col("_identity_key").is_not_null())
            .then(pl.lit("MATCHED_EXACT"))
            .otherwise(pl.lit("UNRESOLVED"))
            .alias("resolution_status"),
        )
        .drop("_identity_key")
    )


def _identity_key() -> pl.Expr:
    native_id = pl.col("native_id").fill_null("").str.strip_chars()
    spotify_id = native_id.str.extract(_SPOTIFY_ID_PATTERN.pattern, 1)
    return (
        pl.when((pl.col("item_kind") == "TRACK") & (pl.col("origin_platform") == "SPOTIFY"))
        .then(
            pl.when(spotify_id.is_not_null())
            .then(pl.concat_str([pl.lit("spotify:"), spotify_id]))
            .otherwise(pl.lit(None, dtype=pl.String))
        )
        .otherwise(pl.lit(None, dtype=pl.String))
    )


def _priority_expression(precedence: Mapping[str, int]) -> pl.Expr:
    expression = pl.lit(999_999, dtype=pl.Int64)
    for provider, priority in precedence.items():
        expression = (
            pl.when(pl.col("provider") == provider)
            .then(pl.lit(priority, dtype=pl.Int64))
            .otherwise(expression)
        )
    return expression
