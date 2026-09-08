"""Materialization of authorized YouTube Data API video rankings."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from chart_observatory.charts.dto import ChartPayload


@dataclass(frozen=True)
class YouTubeCollectionSummary:
    regions_requested: int
    regions_collected: int
    rows_written: int
    pages: int
    failures: tuple[dict[str, str], ...]
    output: Path


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _rows_from_payload(
    payload: ChartPayload, raw_artifact_paths: list[Path]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in payload.entries:
        fields = entry.raw_fields
        rows.append(
            {
                "provider": payload.source_code,
                "platform_code": payload.platform_code,
                "chart_family": "YOUTUBE_VIDEO_MOST_POPULAR",
                "country_code": payload.country_code,
                "chart_name": payload.chart_name,
                "observed_at": payload.observed_at,
                "period_start": payload.observed_at.date(),
                "period_end": payload.observed_at.date(),
                "rank": entry.position,
                "native_id": entry.native_id,
                "item_kind": entry.item_kind,
                "title": entry.title,
                "metric_type": entry.metric_type,
                "metric_value": float(entry.metric_value)
                if entry.metric_value is not None
                else None,
                "channel_id": fields.get("channel_id"),
                "channel_title": fields.get("channel_title"),
                "published_at": fields.get("published_at"),
                "video_category_id": fields.get("video_category_id"),
                "requested_video_category_id": payload.provider_metadata.get("video_category_id"),
                "view_count": _int_or_none(fields.get("statistics_viewCount")),
                "like_count": _int_or_none(fields.get("statistics_likeCount")),
                "comment_count": _int_or_none(fields.get("statistics_commentCount")),
                "availability": fields.get("availability"),
                "view_count_definition_version": fields.get("view_count_definition_version"),
                "semantic_equivalence": "NOT_YOUTUBE_MUSIC_TOP_SONGS",
                "raw_artifact_path": str(raw_artifact_paths[0].parent)
                if raw_artifact_paths
                else None,
            }
        )
    return rows


def _write_raw_pages(
    payload: ChartPayload, region: str, raw_root: Path, observed_at: datetime
) -> list[Path]:
    target = raw_root / observed_at.date().isoformat() / region.upper()
    target.mkdir(parents=True, exist_ok=True)
    pages = json.loads(payload.raw_bytes)
    paths: list[Path] = []
    for index, encoded in enumerate(pages, start=1):
        path = target / f"page-{index:03d}.json"
        path.write_bytes(base64.b64decode(encoded))
        paths.append(path)
    return paths


def collect_youtube_current(
    source: Any,
    regions: Iterable[str],
    *,
    category_id: str = "10",
    observed_at: datetime | None = None,
    output: Path = Path("data/normalized/youtube_video_most_popular.parquet"),
    raw_root: Path = Path("data/raw/youtube_data"),
    failure_output: Path | None = None,
) -> YouTubeCollectionSummary:
    """Fetch and materialize current video rankings for each requested region."""
    occurred_at = observed_at or datetime.now(UTC)
    region_list = tuple(dict.fromkeys(region.upper() for region in regions if region.strip()))
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    page_count = 0
    collected = 0
    for region in region_list:
        try:
            payload = source.fetch(region, category_id, occurred_at)
            raw_paths = _write_raw_pages(payload, region, raw_root, occurred_at)
            rows.extend(_rows_from_payload(payload, raw_paths))
            page_count += len(raw_paths)
            collected += 1
        except Exception as error:  # per-market collection must not discard other markets
            failures.append({"country_code": region, "error": str(error)})

    schema: dict[str, Any] = {
        "provider": pl.String,
        "platform_code": pl.String,
        "chart_family": pl.String,
        "country_code": pl.String,
        "chart_name": pl.String,
        "observed_at": pl.Datetime(time_zone="UTC"),
        "period_start": pl.Date,
        "period_end": pl.Date,
        "rank": pl.Int64,
        "native_id": pl.String,
        "item_kind": pl.String,
        "title": pl.String,
        "metric_type": pl.String,
        "metric_value": pl.Float64,
        "channel_id": pl.String,
        "channel_title": pl.String,
        "published_at": pl.String,
        "video_category_id": pl.String,
        "requested_video_category_id": pl.String,
        "view_count": pl.Int64,
        "like_count": pl.Int64,
        "comment_count": pl.Int64,
        "availability": pl.String,
        "view_count_definition_version": pl.String,
        "semantic_equivalence": pl.String,
        "raw_artifact_path": pl.String,
    }
    frame = pl.DataFrame(rows, schema=schema) if rows else pl.DataFrame(schema=schema)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(output)
    if failure_output is not None:
        failure_output.parent.mkdir(parents=True, exist_ok=True)
        failure_output.write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    return YouTubeCollectionSummary(
        len(region_list), collected, frame.height, page_count, tuple(failures), output
    )
