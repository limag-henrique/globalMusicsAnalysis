from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl

from chart_observatory.sources.catalog import CatalogFilters, filter_source_catalog
from chart_observatory.ui.classifications import ContentClassification
from chart_observatory.ui.taxonomy import taxonomy_codes


@dataclass(frozen=True, slots=True)
class ManifestSummary:
    status: str | None
    observations: int
    total_cells: int
    eligible_cells: int
    date_start: str | None
    date_end: str | None
    manifest_sha256: str | None
    freeze_kind: str | None
    frozen_at: str | None
    analytical_datasets: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True)
class ObservationFilters:
    country_code: str | None = None
    date_start: date | None = None
    date_end: date | None = None
    max_rank: int | None = None
    query: str | None = None
    classification_state: str | None = None
    limit: int = 200


@dataclass(frozen=True, slots=True)
class TrackDetail:
    track_id: str
    track_title: str | None
    artist: str | None
    appearances: int
    peak_rank: int
    mean_rank: float
    markets: tuple[str, ...]
    duration: int | None
    event: int | None
    genres: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class YoutubeSummary:
    observations: int
    markets: int
    videos: int
    total_views: int


def load_manifest_summary(manifest_path: Path) -> ManifestSummary:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    observations = payload.get("observations")
    datasets = payload.get("analytical_datasets")
    return ManifestSummary(
        status=_optional_str(payload.get("status")),
        observations=_nested_int(observations, "rows"),
        total_cells=_as_int(payload.get("total_cells")),
        eligible_cells=_as_int(payload.get("eligible_cells")),
        date_start=_optional_str(payload.get("date_start")),
        date_end=_optional_str(payload.get("date_end")),
        manifest_sha256=_optional_str(payload.get("manifest_sha256")),
        freeze_kind=_optional_str(payload.get("freeze_kind")),
        frozen_at=_optional_str(payload.get("frozen_at")),
        analytical_datasets=tuple(item for item in datasets if isinstance(item, dict))
        if isinstance(datasets, list)
        else (),
    )


def manifest_metric_labels(payload: Mapping[str, object]) -> dict[str, str]:
    observations = _nested_int(payload.get("observations"), "rows")
    datasets = payload.get("analytical_datasets")
    tracks = 0
    if isinstance(datasets, list):
        for dataset in datasets:
            if isinstance(dataset, Mapping) and str(dataset.get("path", "")).endswith(
                "track_master.parquet"
            ):
                tracks = _as_int(dataset.get("rows"))
                break
    market_label = (
        f"{_as_int(payload.get('eligible_cells'))}/{_as_int(payload.get('total_cells'))} elegíveis"
    )
    return {
        "observations": _format_number(observations),
        "tracks": _format_number(tracks),
        "markets": market_label,
        "freeze": _optional_str(payload.get("status")) or "—",
        "manifest_sha256": _optional_str(payload.get("manifest_sha256")) or "—",
    }


def filter_mgd_observations(
    path: Path, filters: ObservationFilters, annotated_track_ids: set[str]
) -> pl.DataFrame:
    query = pl.scan_parquet(path)
    if filters.country_code:
        query = query.filter(pl.col("country_code") == filters.country_code)
    if filters.date_start:
        query = query.filter(pl.col("period_start") >= filters.date_start)
    if filters.date_end:
        query = query.filter(pl.col("period_start") <= filters.date_end)
    if filters.max_rank is not None:
        query = query.filter(pl.col("rank") <= filters.max_rank)
    if filters.query:
        needle = filters.query.strip().lower()
        if needle:
            title_matches = (
                pl.col("track_title")
                .str.to_lowercase()
                .str.contains(needle, literal=True, strict=False)
            )
            artist_matches = (
                pl.col("artist").str.to_lowercase().str.contains(needle, literal=True, strict=False)
            )
            query = query.filter(title_matches | artist_matches)
    if filters.classification_state == "ANNOTATED":
        query = query.filter(pl.col("native_id").is_in(annotated_track_ids))
    elif filters.classification_state == "UNANNOTATED":
        query = query.filter(~pl.col("native_id").is_in(annotated_track_ids))
    return (
        query.with_columns(
            pl.when(pl.col("native_id").is_in(annotated_track_ids))
            .then(pl.lit("ANNOTATED"))
            .otherwise(pl.lit("UNANNOTATED"))
            .alias("classification_state")
        )
        .limit(max(filters.limit, 0))
        .collect()
    )


def filter_source_observations(
    paths: Iterable[Path], filters: CatalogFilters, annotated_track_ids: set[str]
) -> pl.DataFrame:
    """Query the source-preserving catalog, adding the UI classification label."""
    filters = CatalogFilters(
        provider=filters.provider,
        origin_platform=filters.origin_platform,
        country_code=filters.country_code,
        year=filters.year,
        date_start=filters.date_start,
        date_end=filters.date_end,
        max_rank=filters.max_rank,
        chart_family=filters.chart_family,
        chart_name=filters.chart_name,
        query=filters.query,
        classification_state=filters.classification_state,
        annotated_track_ids=frozenset(annotated_track_ids),
        limit=filters.limit,
    )
    observations = filter_source_catalog(paths, filters)
    return observations.with_columns(
        pl.when(pl.col("native_id").is_in(annotated_track_ids))
        .then(pl.lit("ANNOTATED"))
        .otherwise(pl.lit("UNANNOTATED"))
        .alias("classification_state")
    )


def load_track_detail(
    observations_path: Path, survival_path: Path, genre_claims_path: Path, track_id: str
) -> TrackDetail | None:
    observation = (
        pl.scan_parquet(observations_path)
        .filter(pl.col("native_id") == track_id)
        .select(
            pl.len().alias("appearances"),
            pl.col("rank").min().alias("peak_rank"),
            pl.col("rank").mean().alias("mean_rank"),
            pl.col("country_code").unique().sort().implode().alias("markets"),
            pl.col("track_title").first().alias("track_title"),
            pl.col("artist").first().alias("artist"),
        )
        .collect()
    )
    if observation["appearances"][0] == 0:
        return None
    survival = _filtered_optional_parquet(survival_path, "track_id", track_id)
    genres = _filtered_optional_parquet(genre_claims_path, "canonical_track_id", track_id)
    row = observation.row(0, named=True)
    return TrackDetail(
        track_id=track_id,
        track_title=row["track_title"],
        artist=row["artist"],
        appearances=row["appearances"],
        peak_rank=row["peak_rank"],
        mean_rank=row["mean_rank"],
        markets=tuple(row["markets"]),
        duration=_first_value(survival, "duration"),
        event=_first_value(survival, "event"),
        genres=tuple(sorted(genres["normalized_genre"].drop_nulls().unique().to_list()))
        if "normalized_genre" in genres.columns
        else (),
    )


def build_classification_profile(
    observations: pl.DataFrame, classifications: Sequence[ContentClassification]
) -> pl.DataFrame:
    countries = observations.select("country_code", "native_id").unique()
    scores = pl.DataFrame(
        [
            {
                "native_id": record.canonical_track_id,
                "category": category,
                "score": score,
            }
            for record in classifications
            for category, score in record.scores.items()
        ],
        schema={"native_id": pl.String, "category": pl.String, "score": pl.Int64},
    )
    categories = pl.DataFrame({"category": list(taxonomy_codes())})
    scaffold = countries.select("country_code").unique().join(categories, how="cross")
    if scores.is_empty():
        return scaffold.with_columns(
            pl.lit(0).alias("classified_track_count"),
            pl.lit(0).alias("tracks_with_category"),
            pl.lit(0.0).alias("prevalence"),
            pl.lit(None, dtype=pl.Float64).alias("mean_score"),
        )
    summary = (
        countries.join(scores, on="native_id", how="left")
        .group_by("country_code", "category")
        .agg(
            pl.col("score").count().alias("classified_track_count"),
            (pl.col("score") > 0).sum().fill_null(0).alias("tracks_with_category"),
            pl.col("score").mean().alias("mean_score"),
        )
        .with_columns(
            pl.when(pl.col("classified_track_count") > 0)
            .then(pl.col("tracks_with_category") / pl.col("classified_track_count"))
            .otherwise(pl.lit(0.0))
            .alias("prevalence")
        )
    )
    return scaffold.join(summary, on=["country_code", "category"], how="left").with_columns(
        pl.col("classified_track_count").fill_null(0),
        pl.col("tracks_with_category").fill_null(0),
        pl.col("prevalence").fill_null(0.0),
    )


def build_classification_profile_from_mgd_observations(
    observations_path: Path, classifications: Sequence[ContentClassification]
) -> pl.DataFrame:
    """Build a full-corpus profile independently of a bounded UI catalog."""
    observations = (
        pl.scan_parquet(observations_path).select("country_code", "native_id").unique().collect()
    )
    return build_classification_profile(observations, classifications)


def load_youtube_summary(path: Path) -> YoutubeSummary:
    frame, status = load_optional_parquet(path)
    if status or frame.is_empty():
        return YoutubeSummary(observations=0, markets=0, videos=0, total_views=0)
    total_views = _sum_column(frame, "view_count")
    return YoutubeSummary(
        observations=frame.height,
        markets=frame["country_code"].n_unique() if "country_code" in frame.columns else 0,
        videos=frame["native_id"].n_unique() if "native_id" in frame.columns else 0,
        total_views=total_views,
    )


def load_optional_parquet(path: Path) -> tuple[pl.DataFrame, str | None]:
    path = Path(path)
    if not path.exists():
        return pl.DataFrame(), f"Artefato opcional ausente: {path}"
    try:
        return pl.read_parquet(path), None
    except (OSError, pl.exceptions.PolarsError) as error:
        return pl.DataFrame(), f"Não foi possível ler artefato opcional {path}: {error}"


def _filtered_optional_parquet(path: Path, column: str, value: str) -> pl.DataFrame:
    if not Path(path).exists():
        return pl.DataFrame()
    return pl.scan_parquet(path).filter(pl.col(column) == value).collect()


def _first_value(frame: pl.DataFrame, column: str) -> int | None:
    if frame.is_empty() or column not in frame.columns:
        return None
    value = frame[column][0]
    return int(value) if value is not None else None


def _sum_column(frame: pl.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    value = frame[column].sum()
    return int(value) if value is not None else 0


def _nested_int(value: object, key: str) -> int:
    return _as_int(value.get(key)) if isinstance(value, Mapping) else 0


def _as_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _format_number(value: int) -> str:
    return f"{value:,}".replace(",", ".")
