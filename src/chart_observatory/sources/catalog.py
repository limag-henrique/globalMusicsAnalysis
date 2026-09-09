from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl
import pycountry

CATALOG_COLUMNS = (
    "source_observation_key",
    "provider",
    "origin_platform",
    "platform_code",
    "item_kind",
    "source_country_code",
    "market_code",
    "chart_family",
    "chart_name",
    "observed_at",
    "period_start",
    "period_end",
    "rank",
    "track_title",
    "artist",
    "native_id",
    "metric_type",
    "metric_value",
    "source_artifact",
    "source_row_number",
    "channel_id",
    "channel_title",
    "published_at",
    "video_category_id",
    "requested_video_category_id",
    "view_count",
    "like_count",
    "comment_count",
    "availability",
    "view_count_definition_version",
    "semantic_equivalence",
    "raw_artifact_path",
    "canonical_track_id",
    "resolution_status",
)

CATALOG_SCHEMA: dict[str, Any] = {
    "source_observation_key": pl.String,
    "provider": pl.String,
    "origin_platform": pl.String,
    "platform_code": pl.String,
    "item_kind": pl.String,
    "source_country_code": pl.String,
    "market_code": pl.String,
    "chart_family": pl.String,
    "chart_name": pl.String,
    "observed_at": pl.String,
    "period_start": pl.Date,
    "period_end": pl.Date,
    "rank": pl.Int64,
    "track_title": pl.String,
    "artist": pl.String,
    "native_id": pl.String,
    "metric_type": pl.String,
    "metric_value": pl.Float64,
    "source_artifact": pl.String,
    "source_row_number": pl.Int64,
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
    "canonical_track_id": pl.String,
    "resolution_status": pl.String,
}


@dataclass(frozen=True, slots=True)
class CatalogFilters:
    provider: str | None = None
    origin_platform: str | None = None
    country_code: str | None = None
    year: int | None = None
    date_start: date | None = None
    date_end: date | None = None
    max_rank: int | None = None
    chart_family: str | None = None
    chart_name: str | None = None
    query: str | None = None
    classification_state: str | None = None
    annotated_track_ids: frozenset[str] = field(default_factory=frozenset)
    limit: int = 200


def catalog_source_paths(
    root: Path = Path("."), *, include_materialized: bool = True
) -> tuple[Path, ...]:
    """Return known local source artifacts in deterministic order."""
    root = Path(root)
    materialized = root / "data/normalized/source_catalog.parquet"
    candidates = [
        root / "data/normalized/mgd_observations.parquet",
        root / "data/normalized/kaggle_spotify_observations.parquet",
        root / "data/normalized/chartmetric_observations.parquet",
        root / "data/normalized/youtube_video_most_popular.parquet",
        root / "research/promusica_top50_current.csv",
    ]
    candidates.extend(sorted((root / "data/normalized/chartmetric-backfill").glob("*.parquet")))
    source_paths = tuple(dict.fromkeys(path for path in candidates if path.is_file()))
    if include_materialized and materialized.is_file():
        materialized_mtime = materialized.stat().st_mtime_ns
        if not any(path.stat().st_mtime_ns > materialized_mtime for path in source_paths):
            return (materialized,)
    return source_paths


def scan_source_catalog(paths: Iterable[Path]) -> pl.LazyFrame:
    """Normalize all supplied source files without collecting their rows."""
    frames = [_normalize_source(Path(path)) for path in paths if Path(path).is_file()]
    if not frames:
        return pl.LazyFrame(schema=CATALOG_SCHEMA)
    return pl.concat(frames, how="vertical_relaxed")


def catalog_quality_report(paths: Iterable[Path]) -> pl.DataFrame:
    """Summarize the available catalog without materializing its observations."""
    return (
        scan_source_catalog(paths)
        .group_by("provider", "origin_platform", "item_kind", "chart_family")
        .agg(
            pl.len().alias("rows"),
            pl.col("market_code").n_unique().alias("markets"),
            pl.col("period_start").min().alias("date_start"),
            pl.col("period_end").max().alias("date_end"),
            pl.col("metric_value").is_null().sum().alias("null_metric_rows"),
        )
        .sort("provider", "origin_platform", "item_kind", "chart_family")
        .collect(engine="streaming")
    )


def filter_source_catalog(paths: Iterable[Path], filters: CatalogFilters) -> pl.DataFrame:
    query = scan_source_catalog(paths)
    if filters.provider:
        query = query.filter(pl.col("provider").str.to_lowercase() == filters.provider.casefold())
    if filters.origin_platform:
        query = query.filter(
            pl.col("origin_platform").str.to_lowercase() == filters.origin_platform.casefold()
        )
    if filters.country_code:
        market = _normalize_market_code(filters.country_code)
        query = query.filter(pl.col("market_code") == market)
    if filters.year is not None:
        query = query.filter(pl.col("period_start").dt.year() == filters.year)
    if filters.date_start is not None:
        query = query.filter(pl.col("period_start") >= filters.date_start)
    if filters.date_end is not None:
        query = query.filter(pl.col("period_start") <= filters.date_end)
    if filters.max_rank is not None:
        query = query.filter(pl.col("rank") <= filters.max_rank)
    if filters.chart_family:
        query = query.filter(
            pl.col("chart_family").str.to_lowercase() == filters.chart_family.casefold()
        )
    if filters.chart_name:
        query = query.filter(
            pl.col("chart_name").str.to_lowercase() == filters.chart_name.casefold()
        )
    if filters.query and filters.query.strip():
        needle = filters.query.strip().casefold()
        query = query.filter(
            pl.col("track_title")
            .fill_null("")
            .str.to_lowercase()
            .str.contains(needle, literal=True)
            | pl.col("artist").fill_null("").str.to_lowercase().str.contains(needle, literal=True)
        )
    if filters.classification_state == "ANNOTATED":
        query = query.filter(pl.col("native_id").is_in(filters.annotated_track_ids))
    elif filters.classification_state == "UNANNOTATED":
        query = query.filter(~pl.col("native_id").is_in(filters.annotated_track_ids))
    return (
        query.sort("period_start", "market_code", "rank", "provider")
        .limit(max(filters.limit, 0))
        .collect(engine="streaming")
    )


def write_source_catalog(paths: Iterable[Path], output: Path) -> Path:
    """Materialize the complete available source-preserving catalog."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    selected_paths = tuple(Path(path) for path in paths if Path(path).is_file())
    frame = scan_source_catalog(selected_paths)
    if not selected_paths:
        pl.DataFrame(schema=CATALOG_SCHEMA).write_parquet(output)
    else:
        frame.sink_parquet(output, compression="zstd")
    return output


def _normalize_source(path: Path) -> pl.LazyFrame:
    source = (
        pl.scan_csv(path, infer_schema_length=1000)
        if path.suffix.casefold() == ".csv"
        else pl.scan_parquet(path)
    )
    columns = set(source.collect_schema().names())
    if "source_observation_key" in columns and "resolution_status" in columns:
        return source
    if "platform_code" in columns and "chart_family" in columns:
        return _normalize_youtube(source, columns, path)
    return _normalize_track_source(source, columns, path)


def _normalize_track_source(source: pl.LazyFrame, columns: set[str], path: Path) -> pl.LazyFrame:
    provider = _column(source, columns, "provider", pl.String)
    origin = _column(source, columns, "origin_platform", pl.String)
    source_country = _column(source, columns, "country_code", pl.String)
    chart_name = _column(source, columns, "chart_name", pl.String)
    period_start = _date_column(source, columns, "period_start")
    period_end = _date_column(source, columns, "period_end", fallback=period_start)
    source_artifact = _column(
        source,
        columns,
        "source_artifact",
        pl.String,
        fallback=pl.lit(str(path)),
    )
    row_number = _column(
        source,
        columns,
        "source_row_number",
        pl.Int64,
        fallback=pl.int_range(1, pl.len() + 1, dtype=pl.Int64),
    )
    return _select_catalog_columns(
        source.with_columns(
            provider.alias("_provider"),
            origin.alias("_origin"),
            source_country.alias("_source_country"),
            chart_name.alias("_chart_name"),
            period_start.alias("_period_start"),
            period_end.alias("_period_end"),
            source_artifact.alias("_source_artifact"),
            row_number.alias("_row_number"),
        ),
        path,
        item_kind="TRACK",
        source_country=pl.col("_source_country"),
        provider=pl.col("_provider"),
        origin=pl.col("_origin"),
        platform=_column(source, columns, "platform_code", pl.String, fallback=origin),
        chart_name=pl.col("_chart_name"),
        chart_family=_canonical_chart_family(pl.col("_chart_name")),
        period_start=pl.col("_period_start"),
        period_end=pl.col("_period_end"),
        source_artifact=pl.col("_source_artifact"),
        row_number=pl.col("_row_number"),
    )


def _normalize_youtube(source: pl.LazyFrame, columns: set[str], path: Path) -> pl.LazyFrame:
    source_country = _column(source, columns, "country_code", pl.String)
    return _select_catalog_columns(
        source,
        path,
        item_kind="VIDEO",
        source_country=source_country,
        provider=_column(source, columns, "provider", pl.String),
        origin=_column(source, columns, "platform_code", pl.String),
        platform=_column(source, columns, "platform_code", pl.String),
        chart_name=_column(source, columns, "chart_name", pl.String),
        chart_family=_column(source, columns, "chart_family", pl.String),
        period_start=_date_column(source, columns, "period_start"),
        period_end=_date_column(source, columns, "period_end"),
        source_artifact=_column(
            source,
            columns,
            "raw_artifact_path",
            pl.String,
            fallback=pl.lit(str(path)),
        ),
        row_number=_column(
            source,
            columns,
            "source_row_number",
            pl.Int64,
            fallback=pl.int_range(1, pl.len() + 1, dtype=pl.Int64),
        ),
    )


def _select_catalog_columns(
    source: pl.LazyFrame,
    path: Path,
    *,
    item_kind: str,
    source_country: pl.Expr,
    provider: pl.Expr,
    origin: pl.Expr,
    platform: pl.Expr,
    chart_name: pl.Expr,
    chart_family: pl.Expr,
    period_start: pl.Expr,
    period_end: pl.Expr,
    source_artifact: pl.Expr,
    row_number: pl.Expr,
) -> pl.LazyFrame:
    columns = set(source.collect_schema().names())
    source_country = source_country.cast(pl.String)
    provider = provider.cast(pl.String)
    origin = origin.cast(pl.String)
    platform = platform.cast(pl.String)
    chart_name = chart_name.cast(pl.String)
    title = _column(
        source,
        columns,
        "track_title",
        pl.String,
        fallback=_column(source, columns, "title", pl.String),
    )
    artist = _column(source, columns, "artist", pl.String)
    native_id = _column(source, columns, "native_id", pl.String)
    metric_value = _column(source, columns, "metric_value", pl.Float64)
    source_artifact = source_artifact.cast(pl.String)
    row_number = row_number.cast(pl.Int64)
    output = source.with_columns(
        source_country.alias("_source_country"),
        provider.alias("_provider"),
        origin.alias("_origin"),
        platform.alias("_platform"),
        chart_name.alias("_chart_name"),
        chart_family.cast(pl.String).alias("_chart_family"),
        period_start.alias("_period_start"),
        period_end.alias("_period_end"),
        title.alias("_title"),
        artist.alias("_artist"),
        native_id.alias("_native_id"),
        metric_value.alias("_metric_value"),
        source_artifact.alias("_source_artifact"),
        row_number.alias("_row_number"),
    )
    output = output.with_columns(
        pl.col("_source_country").str.to_uppercase().alias("_source_country_upper"),
        pl.col("_source_country")
        .str.to_uppercase()
        .replace(_COUNTRY_ALIASES)
        .alias("_market_code"),
    )
    return output.select(
        pl.concat_str(
            [
                pl.col("_provider"),
                pl.col("_source_artifact"),
                pl.col("_row_number").cast(pl.String),
            ],
            separator="|",
        ).alias("source_observation_key"),
        pl.col("_provider").alias("provider"),
        pl.col("_origin").alias("origin_platform"),
        pl.col("_platform").alias("platform_code"),
        pl.lit(item_kind).alias("item_kind"),
        pl.col("_source_country_upper").alias("source_country_code"),
        pl.col("_market_code").alias("market_code"),
        pl.col("_chart_family").alias("chart_family"),
        pl.col("_chart_name").alias("chart_name"),
        _string_column(output, columns, "observed_at").alias("observed_at"),
        pl.col("_period_start").alias("period_start"),
        pl.col("_period_end").alias("period_end"),
        _column(output, columns, "rank", pl.Int64).alias("rank"),
        pl.col("_title").alias("track_title"),
        pl.col("_artist").alias("artist"),
        pl.col("_native_id").alias("native_id"),
        _column(output, columns, "metric_type", pl.String).alias("metric_type"),
        pl.col("_metric_value").alias("metric_value"),
        pl.col("_source_artifact").alias("source_artifact"),
        pl.col("_row_number").alias("source_row_number"),
        *(_column(output, columns, "channel_id", pl.String).alias("channel_id"),),
        *(_column(output, columns, "channel_title", pl.String).alias("channel_title"),),
        *(_string_column(output, columns, "published_at").alias("published_at"),),
        *(_column(output, columns, "video_category_id", pl.String).alias("video_category_id"),),
        *(
            _column(output, columns, "requested_video_category_id", pl.String).alias(
                "requested_video_category_id"
            ),
        ),
        *(_column(output, columns, "view_count", pl.Int64).alias("view_count"),),
        *(_column(output, columns, "like_count", pl.Int64).alias("like_count"),),
        *(_column(output, columns, "comment_count", pl.Int64).alias("comment_count"),),
        *(_column(output, columns, "availability", pl.String).alias("availability"),),
        *(
            _column(output, columns, "view_count_definition_version", pl.String).alias(
                "view_count_definition_version"
            ),
        ),
        _column(
            output,
            columns,
            "semantic_equivalence",
            pl.String,
            fallback=pl.lit("TRACK_CHART"),
        ).alias("semantic_equivalence"),
        _column(output, columns, "raw_artifact_path", pl.String).alias("raw_artifact_path"),
        pl.lit(None, dtype=pl.String).alias("canonical_track_id"),
        pl.lit("UNRESOLVED", dtype=pl.String).alias("resolution_status"),
    )


def _column(
    source: pl.LazyFrame,
    columns: set[str],
    name: str,
    dtype: Any,
    *,
    fallback: pl.Expr | None = None,
) -> pl.Expr:
    expression = (
        pl.col(name)
        if name in columns
        else (fallback if fallback is not None else pl.lit(None, dtype=dtype))
    )
    return expression.cast(dtype, strict=False)


def _string_column(source: pl.LazyFrame, columns: set[str], name: str) -> pl.Expr:
    return _column(source, columns, name, pl.String)


def _date_column(
    source: pl.LazyFrame,
    columns: set[str],
    name: str,
    *,
    fallback: pl.Expr | None = None,
) -> pl.Expr:
    if name not in columns:
        return fallback if fallback is not None else pl.lit(None, dtype=pl.Date)
    return (
        pl.col(name)
        .cast(pl.String, strict=False)
        .str.strptime(pl.Date, format="%Y-%m-%d", strict=False)
    )


def _normalize_market_code(value: str) -> str:
    normalized = value.strip().upper()
    return _COUNTRY_ALIASES.get(normalized, normalized)


def _canonical_chart_family(chart_name: pl.Expr) -> pl.Expr:
    normalized = chart_name.fill_null("").str.to_lowercase()
    return (
        pl.when(normalized.str.contains("viral", literal=True))
        .then(pl.lit("VIRAL_50"))
        .when(normalized.str.contains("top", literal=True))
        .then(pl.lit("TOP_200"))
        .otherwise(chart_name.str.to_uppercase().str.replace_all(" ", "_"))
    )


def _country_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {"GLOBAL": "GLOBAL", "WORLD": "GLOBAL"}
    for country in pycountry.countries:
        aliases[country.alpha_2] = country.alpha_2
        aliases[country.alpha_3] = country.alpha_2
        aliases[country.name.upper()] = country.alpha_2
    aliases.update(
        {
            "CZECH REPUBLIC": "CZ",
            "SOUTH KOREA": "KR",
            "RUSSIA": "RU",
            "BOLIVIA": "BO",
            "VENEZUELA": "VE",
            "VIETNAM": "VN",
            "TAIWAN": "TW",
            "TURKEY": "TR",
            "UNITED STATES": "US",
            "UNITED KINGDOM": "GB",
            "UNITED ARAB EMIRATES": "AE",
            "HONG KONG": "HK",
        }
    )
    return aliases


_COUNTRY_ALIASES = _country_aliases()
