from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

from chart_observatory.metadata.taxonomy import normalize_genre
from chart_observatory.metrics.content import (
    ContentObservation,
    category_exposure,
    category_prevalence,
)
from chart_observatory.metrics.diversity import genre_diversity


def build_mgd_track_master(path: Path) -> pl.DataFrame:
    return (
        pl.scan_parquet(path)
        .filter(pl.col("native_id").is_not_null())
        .select(
            pl.col("native_id").alias("canonical_track_id"),
            pl.col("track_title").alias("title"),
            pl.col("artist").alias("artist_names"),
        )
        .unique(subset=["canonical_track_id"], keep="first")
        .sort("canonical_track_id")
        .collect(engine="streaming")
    )


def build_turnover_dataset(path: Path, *, top_n: int = 50) -> pl.DataFrame:
    grouped = (
        pl.scan_parquet(path)
        .filter((pl.col("rank") > 0) & (pl.col("rank") <= top_n))
        .select("country_code", "period_start", "native_id", "rank")
        .group_by("country_code", "period_start")
        .agg(
            pl.struct(["native_id", "rank"])
            .filter(pl.col("native_id").is_not_null())
            .alias("ranked_tracks")
        )
        .sort("country_code", "period_start")
        .collect(engine="streaming")
    )
    output: list[dict[str, object]] = []
    previous: dict[str, tuple[date, dict[str, int]]] = {}
    for row in grouped.iter_rows(named=True):
        country = str(row["country_code"])
        period = row["period_start"]
        current = {
            str(item["native_id"]): int(item["rank"])
            for item in row["ranked_tracks"]
            if item["native_id"] is not None
        }
        if country in previous:
            previous_period, prior = previous[country]
            left = set(prior)
            right = set(current)
            retained = left & right
            union = left | right
            jaccard = len(retained) / len(union) if union else None
            output.append(
                {
                    "country_code": country,
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
        previous[country] = (period, current)
    return pl.DataFrame(output) if output else pl.DataFrame()


def build_content_datasets(rows: list[ContentObservation]) -> dict[str, pl.DataFrame]:
    return {
        "category_prevalence_by_country": category_prevalence(rows),
        "category_exposure_by_country": category_exposure(rows),
    }


def build_mgd_genre_claims(path: Path, artist_metadata_path: Path) -> pl.DataFrame:
    tracks = (
        pl.scan_parquet(path)
        .select(
            pl.col("native_id").alias("canonical_track_id"),
            pl.col("artist").alias("artist_name"),
        )
        .filter(pl.col("canonical_track_id").is_not_null())
        .unique()
        .collect(engine="streaming")
    )
    artists = (
        pl.read_csv(artist_metadata_path, separator="\t", infer_schema_length=1000)
        .select(pl.col("name").alias("artist_name"), pl.col("main_genre").alias("raw_label"))
        .drop_nulls()
        .unique(subset=["artist_name"])
    )
    joined = tracks.join(artists, on="artist_name", how="inner")
    if joined.height == 0:
        return pl.DataFrame(
            schema={
                "canonical_track_id": pl.String,
                "raw_label": pl.String,
                "normalized_genre": pl.String,
                "source": pl.String,
                "source_version": pl.String,
            }
        )
    return joined.with_columns(
        pl.col("raw_label")
        .map_elements(normalize_genre, return_dtype=pl.String)
        .alias("normalized_genre"),
        pl.lit("MGD_SPOTIFY_ARTIST_METADATA").alias("source"),
        pl.lit("complete-v1").alias("source_version"),
    ).select("canonical_track_id", "raw_label", "normalized_genre", "source", "source_version")


def build_genre_diversity_dataset(path: Path, genre_claims: pl.DataFrame) -> pl.DataFrame:
    if genre_claims.height == 0:
        return pl.DataFrame()
    observations = (
        pl.scan_parquet(path)
        .select("country_code", "period_start", "native_id", "rank")
        .filter(pl.col("native_id").is_not_null())
        .with_columns(pl.col("period_start").dt.year().alias("year"))
        .collect(engine="streaming")
    )
    joined = observations.join(
        genre_claims.select(pl.col("canonical_track_id").alias("native_id"), "normalized_genre"),
        on="native_id",
        how="inner",
    )
    distribution = joined.group_by("country_code", "year", "normalized_genre").len()
    rows: list[dict[str, object]] = []
    for group in distribution.group_by(["country_code", "year"], maintain_order=True):
        key, frame = group
        metrics = genre_diversity(
            dict(
                zip(
                    frame["normalized_genre"].to_list(),
                    frame["len"].to_list(),
                    strict=True,
                )
            )
        )
        rows.append(
            {
                "country_code": key[0],
                "year": key[1],
                "shannon_entropy": metrics.shannon_entropy,
                "simpson_diversity": metrics.simpson_diversity,
                "hhi": metrics.hhi,
            }
        )
    return pl.DataFrame(rows)


def write_mgd_analytical_datasets(
    path: Path,
    output_dir: Path,
    *,
    top_n: int = 50,
    artist_metadata_path: Path | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    datasets = {
        "track_master": build_mgd_track_master(path),
        "turnover_by_market_period": build_turnover_dataset(path, top_n=top_n),
    }
    if artist_metadata_path is not None and artist_metadata_path.is_file():
        genre_claims = build_mgd_genre_claims(path, artist_metadata_path)
        datasets["genre_claims"] = genre_claims
        datasets["genre_diversity_by_market_period"] = build_genre_diversity_dataset(
            path, genre_claims
        )
    paths: dict[str, Path] = {}
    for name, frame in datasets.items():
        target = output_dir / f"{name}.parquet"
        frame.write_parquet(target)
        paths[name] = target
    return paths
