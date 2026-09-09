from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import combinations
from pathlib import Path

import polars as pl

from chart_observatory.metrics.content_profile import (
    build_content_exposure_dataset,
    build_content_prevalence_dataset,
    classification_observations,
)
from chart_observatory.metrics.diversity import jensen_shannon
from chart_observatory.metrics.virality import build_virality_features, link_virality_to_tracks
from chart_observatory.ui.classifications import ContentClassification


def build_market_anxiety_dataset(observations: pl.DataFrame, *, top_n: int = 50) -> pl.DataFrame:
    """Measure how often each market replaces or moves its top-N tracks."""
    schema = {
        "market_code": pl.String,
        "period_start": pl.Date,
        "previous_period_start": pl.Date,
        "top_n": pl.Int64,
        "new_entries": pl.Int64,
        "exits": pl.Int64,
        "retained_tracks": pl.Int64,
        "jaccard": pl.Float64,
        "turnover_rate": pl.Float64,
        "mean_rank_displacement": pl.Float64,
    }
    required = {"market_code", "period_start", "canonical_track_id", "rank"}
    missing = required.difference(observations.columns)
    if missing:
        raise ValueError(f"market anxiety input is missing columns: {sorted(missing)}")
    grouped = (
        observations.filter(
            pl.col("canonical_track_id").is_not_null()
            & (pl.col("rank") > 0)
            & (pl.col("rank") <= top_n)
        )
        .select("market_code", "period_start", "canonical_track_id", "rank")
        .group_by("market_code", "period_start")
        .agg(pl.struct(["canonical_track_id", "rank"]).alias("ranked_tracks"))
        .sort("market_code", "period_start")
    )
    previous: dict[str, tuple[object, dict[str, int]]] = {}
    output: list[dict[str, object]] = []
    for row in grouped.iter_rows(named=True):
        market = str(row["market_code"])
        period = row["period_start"]
        current = {
            str(item["canonical_track_id"]): int(item["rank"])
            for item in row["ranked_tracks"]
            if item["canonical_track_id"] is not None
        }
        if market in previous:
            previous_period, prior = previous[market]
            left, right = set(prior), set(current)
            retained = left & right
            union = left | right
            jaccard = len(retained) / len(union) if union else None
            output.append(
                {
                    "market_code": market,
                    "period_start": period,
                    "previous_period_start": previous_period,
                    "top_n": top_n,
                    "new_entries": len(right - left),
                    "exits": len(left - right),
                    "retained_tracks": len(retained),
                    "jaccard": jaccard,
                    "turnover_rate": 1.0 - jaccard if jaccard is not None else None,
                    "mean_rank_displacement": (
                        sum(abs(current[key] - prior[key]) for key in retained) / len(retained)
                        if retained
                        else None
                    ),
                }
            )
        previous[market] = (period, current)
    return pl.DataFrame(output, schema=schema)


def build_persistence_dataset(observations: pl.DataFrame) -> pl.DataFrame:
    """Summarize resolved-track persistence in each native chart cell."""
    schema = {
        "provider": pl.String,
        "origin_platform": pl.String,
        "market_code": pl.String,
        "chart_family": pl.String,
        "canonical_track_id": pl.String,
        "first_chart_date": pl.Date,
        "last_chart_date": pl.Date,
        "native_periods": pl.UInt32,
        "calendar_span_days": pl.Int64,
        "peak_rank": pl.Int64,
        "mean_rank": pl.Float64,
        "unresolved_observations": pl.UInt32,
    }
    if observations.height == 0:
        return pl.DataFrame(schema=schema)
    required = {
        "provider",
        "origin_platform",
        "market_code",
        "chart_family",
        "period_start",
        "period_end",
        "rank",
        "canonical_track_id",
    }
    missing = required.difference(observations.columns)
    if missing:
        raise ValueError(f"persistence input is missing columns: {sorted(missing)}")
    resolved = observations.filter(pl.col("canonical_track_id").is_not_null())
    if resolved.height == 0:
        return pl.DataFrame(schema=schema)
    cell_columns = ["provider", "origin_platform", "market_code", "chart_family"]
    unresolved = (
        observations.filter(pl.col("canonical_track_id").is_null())
        .group_by(cell_columns)
        .agg(pl.len().cast(pl.UInt32).alias("unresolved_observations"))
    )
    return (
        resolved.group_by(
            *cell_columns,
            "canonical_track_id",
        )
        .agg(
            pl.col("period_start").min().alias("first_chart_date"),
            pl.col("period_start").max().alias("last_chart_date"),
            pl.col("period_start").n_unique().alias("native_periods"),
            pl.col("period_start").min().alias("_first_period"),
            pl.col("period_end").max().alias("_last_period"),
            pl.col("rank").min().alias("peak_rank"),
            pl.col("rank").mean().alias("mean_rank"),
        )
        .with_columns(
            (
                (pl.col("_last_period") - pl.col("_first_period"))
                .dt.total_days()
                .add(1)
                .cast(pl.Int64)
            ).alias("calendar_span_days"),
        )
        .join(unresolved, on=cell_columns, how="left")
        .with_columns(pl.col("unresolved_observations").fill_null(0).cast(pl.UInt32))
        .drop("_first_period", "_last_period")
        .select(list(schema))
        .sort("provider", "origin_platform", "market_code", "canonical_track_id")
    )


def build_genre_variation_dataset(
    observations: pl.DataFrame, genre_claims: pl.DataFrame
) -> pl.DataFrame:
    """Calculate distinct-track genre shares by market and calendar year."""
    schema = {
        "provider": pl.String,
        "origin_platform": pl.String,
        "market_code": pl.String,
        "year": pl.Int32,
        "genre": pl.String,
        "tracks": pl.UInt32,
        "track_denominator": pl.UInt32,
        "genre_share": pl.Float64,
    }
    if observations.height == 0 or genre_claims.height == 0:
        return pl.DataFrame(schema=schema)
    required_obs = {
        "provider",
        "origin_platform",
        "market_code",
        "period_start",
        "canonical_track_id",
    }
    required_claims = {"canonical_track_id", "normalized_genre"}
    missing = required_obs.difference(observations.columns) | required_claims.difference(
        genre_claims.columns
    )
    if missing:
        raise ValueError(f"genre variation input is missing columns: {sorted(missing)}")
    joined = (
        observations.filter(pl.col("canonical_track_id").is_not_null())
        .with_columns(pl.col("period_start").dt.year().cast(pl.Int32).alias("year"))
        .join(
            genre_claims.select("canonical_track_id", "normalized_genre").unique(),
            on="canonical_track_id",
            how="inner",
        )
        .rename({"normalized_genre": "genre"})
        .unique(
            subset=[
                "provider",
                "origin_platform",
                "market_code",
                "year",
                "genre",
                "canonical_track_id",
            ]
        )
    )
    if joined.height == 0:
        return pl.DataFrame(schema=schema)
    grouped = joined.group_by("provider", "origin_platform", "market_code", "year", "genre").agg(
        pl.col("canonical_track_id").n_unique().alias("tracks")
    )
    denominators = grouped.group_by("provider", "origin_platform", "market_code", "year").agg(
        pl.col("tracks").sum().alias("track_denominator")
    )
    return (
        grouped.join(denominators, on=["provider", "origin_platform", "market_code", "year"])
        .with_columns((pl.col("tracks") / pl.col("track_denominator")).alias("genre_share"))
        .select(list(schema))
        .sort("provider", "origin_platform", "market_code", "year", "genre")
    )


def build_genre_distance_dataset(
    distributions: Mapping[tuple[str, int], Mapping[str, float]],
) -> pl.DataFrame:
    """Calculate pairwise Jensen–Shannon genre distances within each year."""
    rows: list[dict[str, object]] = []
    for year in sorted({year for _, year in distributions}):
        markets = sorted(market for market, item_year in distributions if item_year == year)
        for left, right in combinations(markets, 2):
            rows.append(
                {
                    "year": year,
                    "left_market_code": left,
                    "right_market_code": right,
                    "jensen_shannon": jensen_shannon(
                        distributions[(left, year)], distributions[(right, year)]
                    ),
                }
            )
    return pl.DataFrame(
        rows,
        schema={
            "year": pl.Int32,
            "left_market_code": pl.String,
            "right_market_code": pl.String,
            "jensen_shannon": pl.Float64,
        },
    )


def write_article_datasets(
    observations: pl.DataFrame,
    output_dir: Path,
    *,
    genre_claims: pl.DataFrame | None = None,
    classifications: Iterable[ContentClassification] = (),
    video_observations: pl.DataFrame | None = None,
    resolved_video_links: pl.DataFrame | None = None,
) -> dict[str, Path]:
    """Write the reproducible data products consumed by the article."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, pl.DataFrame] = {
        "persistence": build_persistence_dataset(observations),
        "market_anxiety": build_market_anxiety_dataset(observations),
    }
    if genre_claims is not None:
        variation = build_genre_variation_dataset(observations, genre_claims)
        outputs["genre_variation"] = variation
        distributions: dict[tuple[str, int], dict[str, float]] = {}
        for row in variation.iter_rows(named=True):
            distributions.setdefault((row["market_code"], row["year"]), {})[
                row["genre"]
            ] = float(row["tracks"])
        outputs["genre_distance"] = build_genre_distance_dataset(distributions)
    records = list(classifications)
    if records:
        content = classification_observations(observations, records)
        outputs["content_observations"] = content
        outputs["content_prevalence"] = build_content_prevalence_dataset(content)
        outputs["content_exposure"] = build_content_exposure_dataset(content)
    if video_observations is not None and resolved_video_links is not None:
        linked_videos = link_virality_to_tracks(
            observations, video_observations, resolved_video_links
        )
        outputs["virality_features"] = build_virality_features(linked_videos)
    paths: dict[str, Path] = {}
    for name, frame in outputs.items():
        path = output_dir / f"{name}.parquet"
        frame.write_parquet(path)
        paths[name] = path
    return paths
