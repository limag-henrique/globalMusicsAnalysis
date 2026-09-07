from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any, cast

import polars as pl

from chart_observatory.sources.models import MarketCapability, SourceManifest, SourceObservation


@dataclass(frozen=True)
class ReportSummary:
    output_path: Path
    rows_written: int
    countries: tuple[str, ...]
    earliest_year: int | None
    latest_year: int | None


@dataclass
class _ArtistYear:
    provider: str
    origin_platform: str
    country_code: str
    year: int
    chart_name: str
    artist: str
    appearances: int = 0
    unique_tracks: set[str] | None = None
    ranks: list[int] | None = None
    top10: int = 0
    top50: int = 0
    streams: int = 0
    stream_rows: int = 0

    def __post_init__(self) -> None:
        self.unique_tracks = set()
        self.ranks = []

    def add(self, observation: SourceObservation) -> None:
        assert self.unique_tracks is not None
        assert self.ranks is not None
        self.appearances += 1
        self.unique_tracks.add(observation.native_id or observation.track_title.casefold())
        self.ranks.append(observation.rank)
        self.top10 += observation.rank <= 10
        self.top50 += observation.rank <= 50
        if observation.metric_value is not None:
            self.streams += int(observation.metric_value)
            self.stream_rows += 1


def write_artist_year_report(
    observations: Iterable[SourceObservation],
    output_path: Path,
    latest_years: int | None = 5,
) -> ReportSummary:
    """Write ranked artist summaries without collapsing sources or platforms."""
    grouped: dict[tuple[str, str, str, int, str, str], _ArtistYear] = {}
    for observation in observations:
        key = (
            observation.provider,
            observation.origin_platform,
            observation.country_code,
            observation.period_start.year,
            observation.chart_name,
            observation.artist,
        )
        row = grouped.setdefault(key, _ArtistYear(*key))
        row.add(observation)

    years_by_country: defaultdict[str, set[int]] = defaultdict(set)
    for row in grouped.values():
        years_by_country[row.country_code].add(row.year)
    if latest_years is not None:
        allowed = {
            country: set(sorted(years)[-latest_years:])
            for country, years in years_by_country.items()
        }
        grouped = {
            key: row for key, row in grouped.items() if row.year in allowed[row.country_code]
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "provider",
        "origin_platform",
        "country_code",
        "year",
        "chart_name",
        "artist",
        "chart_appearances",
        "unique_tracks",
        "best_rank",
        "mean_rank",
        "top10_appearances",
        "top50_appearances",
        "streams_sum",
        "stream_observations",
    ]
    rows: list[dict[str, object]] = []
    for row in grouped.values():
        assert row.unique_tracks is not None
        assert row.ranks is not None
        rows.append(
            {
                "provider": row.provider,
                "origin_platform": row.origin_platform,
                "country_code": row.country_code,
                "year": row.year,
                "chart_name": row.chart_name,
                "artist": row.artist,
                "chart_appearances": row.appearances,
                "unique_tracks": len(row.unique_tracks),
                "best_rank": min(row.ranks),
                "mean_rank": f"{mean(row.ranks):.6f}",
                "top10_appearances": row.top10,
                "top50_appearances": row.top50,
                "streams_sum": row.streams if row.stream_rows else "",
                "stream_observations": row.stream_rows,
            }
        )
    rows.sort(
        key=lambda row: (
            row["country_code"],
            row["year"],
            -_as_int(row["chart_appearances"]),
            _as_int(row["best_rank"]),
            str(row["artist"]).casefold(),
        )
    )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    all_years = [_as_int(row["year"]) for row in rows]
    return ReportSummary(
        output_path,
        len(rows),
        tuple(sorted({str(row["country_code"]) for row in rows})),
        min(all_years) if all_years else None,
        max(all_years) if all_years else None,
    )


def write_artist_year_report_from_parquet(
    observations_path: Path,
    output_path: Path,
    latest_years: int | None = 5,
) -> ReportSummary:
    """Aggregate a normalized corpus in Polars without materializing observations."""
    source = pl.scan_parquet(observations_path).with_columns(
        pl.col("period_start").dt.year().alias("year")
    )
    if latest_years is not None:
        latest = (
            source.group_by("country_code")
            .agg(pl.col("year").max().alias("latest_year"))
            .collect(engine="streaming")
        )
        bounds = {
            str(row["country_code"]): int(row["latest_year"]) - latest_years + 1
            for row in latest.iter_rows(named=True)
        }
        source = source.filter(
            pl.struct(["country_code", "year"]).map_elements(
                lambda row: int(row["year"]) >= bounds[str(row["country_code"])],
                return_dtype=pl.Boolean,
            )
        )
    summary = (
        source.group_by(
            "provider", "origin_platform", "country_code", "year", "chart_name", "artist"
        )
        .agg(
            pl.len().alias("chart_appearances"),
            pl.col("native_id").fill_null(pl.col("track_title")).n_unique().alias("unique_tracks"),
            pl.col("rank").min().alias("best_rank"),
            pl.col("rank").mean().round(6).alias("mean_rank"),
            (pl.col("rank") <= 10).sum().alias("top10_appearances"),
            (pl.col("rank") <= 50).sum().alias("top50_appearances"),
            pl.col("metric_value").sum().alias("streams_sum"),
            pl.col("metric_value").count().alias("stream_observations"),
        )
        .sort(
            ["country_code", "year", "chart_appearances", "best_rank", "artist"],
            descending=[False, False, True, False, False],
        )
        .collect(engine="streaming")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.write_csv(output_path)
    return ReportSummary(
        output_path,
        summary.height,
        tuple(str(value) for value in summary.get_column("country_code").unique().sort().to_list()),
        _series_int(summary, "year", minimum=True),
        _series_int(summary, "year", minimum=False),
    )


def write_top_artist_list(
    artist_year_report: Path, output_path: Path, top_n: int = 25
) -> ReportSummary:
    """Materialize a compact top-artist panel from the complete artist/year report."""
    frame = (
        pl.scan_csv(artist_year_report, try_parse_dates=False)
        .with_columns(
            pl.col("year").cast(pl.Int32),
            pl.col("chart_appearances").cast(pl.Int64),
            pl.col("best_rank").cast(pl.Int32),
            pl.col("mean_rank").cast(pl.Float64),
        )
        .sort(
            [
                "provider",
                "origin_platform",
                "country_code",
                "year",
                "chart_name",
                "chart_appearances",
                "best_rank",
                "mean_rank",
                "artist",
            ],
            descending=[False, False, False, False, False, True, False, False, False],
        )
        .with_columns(
            pl.int_range(1, pl.len() + 1)
            .over(["provider", "origin_platform", "country_code", "year", "chart_name"])
            .alias("artist_rank")
        )
        .filter(pl.col("artist_rank") <= top_n)
        .collect(engine="streaming")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_csv(output_path)
    return ReportSummary(
        output_path,
        frame.height,
        tuple(str(value) for value in frame.get_column("country_code").unique().sort().to_list())
        if frame.height
        else (),
        _series_int(frame, "year", minimum=True),
        _series_int(frame, "year", minimum=False),
    )


def write_global_market_coverage(manifests: Iterable[SourceManifest], output_dir: Path) -> Path:
    by_country: dict[str, dict[str, object]] = {}
    for manifest in manifests:
        for country in manifest.countries:
            row = by_country.setdefault(
                country,
                {
                    "country": country,
                    "providers": set(),
                    "platforms": set(),
                    "earliest": None,
                    "latest": None,
                },
            )
            providers = row["providers"]
            platforms = row["platforms"]
            assert isinstance(providers, set) and isinstance(platforms, set)
            providers.add(manifest.provider)
            platforms.add(manifest.origin_platform)
            earliest = cast(date | None, row["earliest"])
            if manifest.earliest_date and (
                earliest is None or manifest.earliest_date < earliest
            ):
                row["earliest"] = manifest.earliest_date
            latest = cast(date | None, row["latest"])
            if manifest.latest_date and (
                latest is None or manifest.latest_date > latest
            ):
                row["latest"] = manifest.latest_date

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "global_market_coverage.csv"
    fields = [
        "country",
        "providers",
        "number_of_sources",
        "origin_platforms",
        "number_of_origin_platforms",
        "common_start",
        "common_end",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for country in sorted(by_country):
            row = by_country[country]
            providers = sorted(cast(set[str], row["providers"]))
            platforms = sorted(cast(set[str], row["platforms"]))
            writer.writerow(
                {
                    "country": country,
                    "providers": ";".join(providers),
                    "number_of_sources": len(providers),
                    "origin_platforms": ";".join(platforms),
                    "number_of_origin_platforms": len(platforms),
                    "common_start": row["earliest"],
                    "common_end": row["latest"],
                }
            )
    return output_path


def write_market_capability_inventory(
    manifests: Iterable[SourceManifest],
    capabilities: Iterable[MarketCapability],
    output_path: Path,
) -> Path:
    """Combine discovered source capabilities without treating any source as ground truth."""
    rows: dict[tuple[str, str, str], dict[str, object]] = {}

    def ensure(capability: MarketCapability) -> dict[str, object]:
        key = (capability.provider, capability.origin_platform, capability.country_code)
        return rows.setdefault(
            key,
            {
                "provider": capability.provider,
                "origin_platform": capability.origin_platform,
                "country_code": capability.country_code,
                "country_name": capability.country_name or "",
                "territory_type": capability.territory_type,
                "available": capability.available,
                "earliest_date": capability.earliest_date,
                "latest_date": capability.latest_date,
                "chart_types": set(),
                "native_frequency": capability.native_frequency or "",
                "ranking_depth": capability.ranking_depth,
                "number_of_tracks": capability.number_of_tracks,
                "number_of_observations": capability.number_of_observations,
            },
        )

    for manifest in manifests:
        for country in manifest.countries:
            row = ensure(
                MarketCapability(
                    manifest.provider,
                    manifest.origin_platform,
                    country,
                    None,
                    territory_type="GLOBAL" if country == "GLOBAL" else "COUNTRY",
                    available=manifest.status.value in {"AVAILABLE", "IMPORTED"},
                    earliest_date=manifest.earliest_date,
                    latest_date=manifest.latest_date,
                    chart_types=manifest.chart_types,
                    ranking_depth=200 if manifest.chart_types else None,
                    number_of_tracks=manifest.number_of_tracks,
                    number_of_observations=manifest.number_of_observations,
                )
            )
            cast(set[str], row["chart_types"]).update(manifest.chart_types)

    for capability in capabilities:
        row = ensure(capability)
        cast(set[str], row["chart_types"]).update(capability.chart_types)
        if capability.country_name:
            row["country_name"] = capability.country_name
        if capability.earliest_date:
            row["earliest_date"] = capability.earliest_date
        if capability.latest_date:
            row["latest_date"] = capability.latest_date
        row["available"] = bool(row["available"]) or capability.available

    fields = [
        "provider",
        "origin_platform",
        "country_code",
        "country_name",
        "territory_type",
        "available",
        "earliest_date",
        "latest_date",
        "chart_types",
        "native_frequency",
        "ranking_depth",
        "number_of_tracks",
        "number_of_observations",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key in sorted(rows):
            row = rows[key]
            row["chart_types"] = ";".join(sorted(cast(set[str], row["chart_types"])))
            writer.writerow(row)
    return output_path


def _as_int(value: object) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    return int(str(value))


def _series_int(frame: pl.DataFrame, column: str, *, minimum: bool) -> int | None:
    value: Any = frame.get_column(column).min() if minimum else frame.get_column(column).max()
    return int(value) if value is not None else None


def write_overlap_report(
    left: Iterable[SourceObservation],
    right: Iterable[SourceObservation],
    output_path: Path,
) -> Path:
    def key(row: SourceObservation) -> tuple[object, ...]:
        return (
            row.origin_platform,
            row.country_code,
            row.chart_name,
            row.period_start,
            row.rank,
            row.native_id or (row.artist.casefold(), row.track_title.casefold()),
        )

    left_rows = {key(row): row for row in left}
    right_rows = {key(row): row for row in right}
    common = sorted(set(left_rows) & set(right_rows), key=str)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "# Cross-source overlap\n\n"
        f"* Left observations: {len(left_rows)}\n"
        f"* Right observations: {len(right_rows)}\n"
        f"* Equivalent observations: {len(common)}\n"
        f"* Left-only observations: {len(set(left_rows) - set(right_rows))}\n"
        f"* Right-only observations: {len(set(right_rows) - set(left_rows))}\n",
        encoding="utf-8",
    )
    return output_path
