from __future__ import annotations

import polars as pl


def link_virality_to_tracks(
    track_observations: pl.DataFrame,
    video_observations: pl.DataFrame,
    resolved_links: pl.DataFrame,
) -> pl.DataFrame:
    """Join resolved video-to-track links while retaining each video row."""
    required_links = {"video_native_id", "canonical_track_id"}
    required_videos = {"native_id", "market_code", "rank", "view_count"}
    missing = (required_links - set(resolved_links.columns)) | (
        required_videos - set(video_observations.columns)
    )
    if missing:
        raise ValueError(f"virality input is missing columns: {sorted(missing)}")
    links = resolved_links.filter(pl.col("canonical_track_id").is_not_null()).unique()
    if "canonical_track_id" in track_observations.columns and track_observations.height:
        track_ids = track_observations.select("canonical_track_id").drop_nulls().unique()
        links = links.join(track_ids, on="canonical_track_id", how="inner")
    if links.height == 0:
        return pl.DataFrame(
            schema={
                "canonical_track_id": pl.String,
                "video_native_id": pl.String,
                "market_code": pl.String,
                "rank": pl.Int64,
                "view_count": pl.Int64,
            }
        )
    return (
        video_observations.rename({"native_id": "video_native_id"})
        .join(links, on="video_native_id", how="inner")
        .select("canonical_track_id", "video_native_id", "market_code", "rank", "view_count")
    )


def build_virality_features(linked_videos: pl.DataFrame) -> pl.DataFrame:
    """Aggregate video signals without summing views across distinct videos."""
    schema = {
        "canonical_track_id": pl.String,
        "linked_video_count": pl.UInt32,
        "markets_with_video": pl.UInt32,
        "best_video_rank": pl.Int64,
        "max_view_count": pl.Int64,
        "median_view_count": pl.Float64,
    }
    if linked_videos.height == 0:
        return pl.DataFrame(schema=schema)
    return (
        linked_videos.group_by("canonical_track_id")
        .agg(
            pl.col("video_native_id").n_unique().alias("linked_video_count"),
            pl.col("market_code").n_unique().alias("markets_with_video"),
            pl.col("rank").min().alias("best_video_rank"),
            pl.col("view_count").max().alias("max_view_count"),
            pl.col("view_count").median().alias("median_view_count"),
        )
        .select(list(schema))
        .sort("canonical_track_id")
    )
