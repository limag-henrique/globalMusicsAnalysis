from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import polars as pl

from chart_observatory.sources.manifest import sha256_file
from chart_observatory.sources.models import (
    ImportSummary,
    SourceManifest,
    SourceObservation,
    SourceStatus,
)

CHART_COLUMNS = {
    "ID": "native_id",
    "Track": "track_title",
    "Artist": "artist",
    "Position": "rank",
    "Streams": "metric_value",
    "Date": "period_start",
    "Chart": "chart_name",
    "market": "country_code",
}


def _parse_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_metric(value: object) -> Decimal | None:
    if value is None or str(value).strip() in {"", "null", "None"}:
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _as_values(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


class MGDSource:
    """Inspect and stream the local MGD/MGD+ Spotify-origin chart files."""

    provider = "MGD"
    origin_platform = "SPOTIFY"
    parser_version = "mgd-v1"

    def __init__(self, root: Path) -> None:
        self.root = root

    def chart_files(self) -> tuple[Path, ...]:
        if not self.root.exists():
            return ()
        return tuple(
            sorted(
                path
                for path in self.root.glob("charts/**/*.csv")
                if ".ipynb_checkpoints" not in path.parts and path.name.endswith(".csv")
            )
        )

    def _scan(self, path: Path) -> pl.LazyFrame:
        return pl.scan_csv(
            path,
            separator="\t",
            infer_schema_length=1000,
            ignore_errors=False,
            try_parse_dates=False,
        )

    def inspect(self) -> tuple[SourceManifest, ...]:
        manifests: list[SourceManifest] = []
        for path in self.chart_files():
            frame = self._scan(path)
            columns = set(frame.collect_schema().names())
            missing = set(CHART_COLUMNS) - columns
            if missing:
                manifests.append(
                    SourceManifest(
                        provider=self.provider,
                        origin_platform=self.origin_platform,
                        filename=str(path.relative_to(self.root)),
                        path=path,
                        sha256=sha256_file(path),
                        size_bytes=path.stat().st_size,
                        row_count=0,
                        schema_version=f"missing:{','.join(sorted(missing))}",
                        status=SourceStatus.NEEDS_REVIEW,
                        parser_version=self.parser_version,
                    )
                )
                continue
            summary_frame = frame.select(
                pl.len().alias("row_count"),
                pl.col("market").cast(pl.String).n_unique().alias("country_count"),
                pl.col("market").cast(pl.String).unique().alias("countries"),
                pl.col("Chart").cast(pl.String).unique().alias("charts"),
                pl.col("Date").cast(pl.String).min().alias("earliest"),
                pl.col("Date").cast(pl.String).max().alias("latest"),
                pl.col("ID").cast(pl.String).n_unique().alias("tracks"),
            ).collect(engine="streaming")
            if summary_frame.height == 0:
                manifests.append(
                    SourceManifest(
                        provider=self.provider,
                        origin_platform=self.origin_platform,
                        filename=str(path.relative_to(self.root)),
                        path=path,
                        sha256=sha256_file(path),
                        size_bytes=path.stat().st_size,
                        row_count=0,
                        schema_version="mgd-tab-v1",
                        status=SourceStatus.AVAILABLE,
                        parser_version=self.parser_version,
                    )
                )
                continue
            summary = summary_frame.row(0, named=True)
            countries = tuple(
                sorted(str(value).upper() for value in _as_values(summary["countries"]))
            )
            charts = tuple(sorted(str(value) for value in _as_values(summary["charts"])))
            manifests.append(
                SourceManifest(
                    provider=self.provider,
                    origin_platform=self.origin_platform,
                    filename=str(path.relative_to(self.root)),
                    path=path,
                    sha256=sha256_file(path),
                    size_bytes=path.stat().st_size,
                    row_count=int(summary["row_count"]),
                    schema_version="mgd-tab-v1",
                    status=SourceStatus.AVAILABLE,
                    countries=countries,
                    chart_types=charts,
                    earliest_date=_parse_date(summary["earliest"]),
                    latest_date=_parse_date(summary["latest"]),
                    number_of_tracks=int(summary["tracks"]),
                    number_of_observations=int(summary["row_count"]),
                    parser_version=self.parser_version,
                )
            )
        return tuple(manifests)

    def iter_observations(
        self,
        countries: set[str] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        chart: str | None = None,
        batch_size: int = 10_000,
    ) -> Iterator[SourceObservation]:
        wanted = {country.upper() for country in countries} if countries else None
        row_number = 0
        for path in self.chart_files():
            reader = pl.read_csv_batched(
                path,
                separator="\t",
                infer_schema_length=1000,
                try_parse_dates=False,
                batch_size=batch_size,
            )
            while batches := reader.next_batches(1):
                for batch in batches:
                    for row in batch.iter_rows(named=True):
                        row_number += 1
                        country = str(row["market"]).upper()
                        period = _parse_date(row["Date"])
                        chart_name = str(row["Chart"])
                        if wanted and country not in wanted:
                            continue
                        if from_date and period < from_date:
                            continue
                        if to_date and period > to_date:
                            continue
                        if chart and chart.casefold() != chart_name.casefold():
                            continue
                        yield SourceObservation(
                            provider=self.provider,
                            origin_platform=self.origin_platform,
                            country_code=country,
                            chart_name=chart_name,
                            period_start=period,
                            period_end=period,
                            rank=int(row["Position"]),
                            track_title=str(row["Track"]),
                            artist=str(row["Artist"]),
                            native_id=str(row["ID"]) if row["ID"] is not None else None,
                            metric_value=_parse_metric(row.get("Streams")),
                            metric_type="STREAMS",
                            source_artifact=str(path),
                            source_row_number=row_number,
                            raw_fields={
                                key: value for key, value in row.items() if key not in CHART_COLUMNS
                            },
                        )

    def import_to(
        self,
        output_path: Path,
        countries: set[str] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        chart: str | None = None,
    ) -> ImportSummary:
        manifests = self.inspect()
        source_checksums = [manifest.sha256 for manifest in manifests]
        sidecar = output_path.with_suffix(output_path.suffix + ".manifest.json")
        if output_path.exists() and sidecar.exists():
            previous = json.loads(sidecar.read_text(encoding="utf-8"))
            if previous.get("source_checksums") == source_checksums:
                return ImportSummary(
                    self.provider,
                    0,
                    0,
                    0,
                    tuple(sorted({c for m in manifests for c in m.countries})),
                    tuple(sorted({c for m in manifests for c in m.chart_types})),
                    min((m.earliest_date for m in manifests if m.earliest_date), default=None),
                    max((m.latest_date for m in manifests if m.latest_date), default=None),
                    output_path,
                    SourceStatus.IMPORTED,
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        frames: list[pl.LazyFrame] = []
        for path in self.chart_files():
            frame = (
                self._scan(path)
                .with_columns(
                    pl.col("ID").cast(pl.String, strict=False).alias("native_id"),
                    pl.col("Track").cast(pl.String, strict=False).alias("track_title"),
                    pl.col("Artist").cast(pl.String, strict=False).alias("artist"),
                    pl.col("Position").cast(pl.Int32, strict=False).alias("rank"),
                    pl.col("Streams")
                    .cast(pl.String, strict=False)
                    .str.replace_all(",", "")
                    .cast(pl.Int64, strict=False)
                    .alias("metric_value"),
                    pl.col("Date")
                    .cast(pl.String, strict=False)
                    .str.strptime(pl.Date, format="%Y-%m-%d", strict=False)
                    .alias("period_start"),
                    pl.col("Chart").cast(pl.String, strict=False).alias("chart_name"),
                    pl.col("market")
                    .cast(pl.String, strict=False)
                    .str.to_uppercase()
                    .alias("country_code"),
                    pl.lit(self.provider).alias("provider"),
                    pl.lit(self.origin_platform).alias("origin_platform"),
                    pl.lit("STREAMS").alias("metric_type"),
                    pl.lit(str(path)).alias("source_artifact"),
                    pl.int_range(1, pl.len() + 1, dtype=pl.Int64).alias("source_row_number"),
                )
                .select(
                    "provider",
                    "origin_platform",
                    "country_code",
                    "chart_name",
                    "period_start",
                    pl.col("period_start").alias("period_end"),
                    "rank",
                    "track_title",
                    "artist",
                    "native_id",
                    "metric_value",
                    "metric_type",
                    "source_artifact",
                    "source_row_number",
                )
            )
            if countries:
                frame = frame.filter(pl.col("country_code").is_in(sorted(countries)))
            if from_date:
                frame = frame.filter(pl.col("period_start") >= from_date)
            if to_date:
                frame = frame.filter(pl.col("period_start") <= to_date)
            if chart:
                frame = frame.filter(pl.col("chart_name").str.to_lowercase() == chart.casefold())
            frames.append(frame)

        combined = pl.concat(frames, how="diagonal_relaxed")
        rows_written = int(combined.select(pl.len()).collect(engine="streaming").item())
        combined.sink_parquet(output_path, compression="zstd")
        rows_seen = rows_written
        total_rows = sum(manifest.row_count for manifest in manifests)
        countries_seen = set(
            countries or {country for manifest in manifests for country in manifest.countries}
        )
        charts_seen = set(
            [chart]
            if chart
            else [chart_name for manifest in manifests for chart_name in manifest.chart_types]
        )
        available_dates = [
            value
            for manifest in manifests
            for value in (manifest.earliest_date, manifest.latest_date)
            if value is not None
        ]
        earliest = from_date or (min(available_dates) if available_dates else None)
        latest = to_date or (max(available_dates) if available_dates else None)
        sidecar.write_text(
            json.dumps(
                {
                    "provider": self.provider,
                    "origin_platform": self.origin_platform,
                    "source_checksums": source_checksums,
                    "rows_written": rows_written,
                    "filters": {
                        "countries": sorted(countries) if countries else None,
                        "from_date": from_date.isoformat() if from_date else None,
                        "to_date": to_date.isoformat() if to_date else None,
                        "chart": chart,
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return ImportSummary(
            self.provider,
            rows_seen,
            rows_written,
            max(0, total_rows - rows_written),
            tuple(sorted(countries_seen)),
            tuple(sorted(charts_seen)),
            earliest,
            latest,
            output_path,
            SourceStatus.IMPORTED,
        )

    def write_manifest(self, output_path: Path) -> Path:
        manifests = self.inspect()
        payload = {
            "provider": self.provider,
            "origin_platform": self.origin_platform,
            "files": [manifest.__dict__ for manifest in manifests],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, default=str, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return output_path
