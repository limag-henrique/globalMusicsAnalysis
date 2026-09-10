from __future__ import annotations

import importlib
import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl

from chart_observatory.sources.manifest import sha256_file
from chart_observatory.sources.models import (
    ImportSummary,
    SourceManifest,
    SourceObservation,
    SourceStatus,
)


class KaggleSpotifyChartsSource:
    provider = "KAGGLE_DHRUVILDAVE"
    origin_platform = "SPOTIFY"
    dataset_ref = "dhruvildave/spotify-charts"

    def __init__(self, root: Path) -> None:
        self.root = root

    def download(self) -> Path:
        """Download through kagglehub when installed; its cache is reused by kagglehub."""
        try:
            kagglehub = importlib.import_module("kagglehub")
        except ImportError as error:
            raise RuntimeError(
                "kagglehub is not installed; install it to download Kaggle data"
            ) from error
        path = Path(kagglehub.dataset_download(self.dataset_ref))
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "kagglehub_path.txt").write_text(str(path) + "\n", encoding="utf-8")
        return path

    def files(self) -> tuple[Path, ...]:
        local_files = tuple(sorted(self.root.rglob("*.csv"))) if self.root.exists() else ()
        marker = self.root / "kagglehub_path.txt"
        if marker.exists():
            cached_root = Path(marker.read_text(encoding="utf-8").strip())
            cached_files = tuple(sorted(cached_root.rglob("*.csv"))) if cached_root.exists() else ()
            return tuple(dict.fromkeys((*local_files, *cached_files)))
        return local_files

    def _charts_file(self) -> Path:
        candidates = [path for path in self.files() if path.name.casefold() == "charts.csv"]
        if not candidates:
            raise FileNotFoundError(f"no charts.csv found under {self.root}")
        return candidates[0]

    @staticmethod
    def _columns(path: Path) -> dict[str, str]:
        names = pl.scan_csv(path, infer_schema_length=1000).collect_schema().names()
        return {name.casefold(): name for name in names}

    def inspect(self) -> SourceManifest:
        path = self._charts_file()
        columns = self._columns(path)
        required = {"title", "rank", "date", "artist", "region"}
        missing = required - columns.keys()
        if missing:
            status = SourceStatus.NEEDS_REVIEW
            schema_version = f"missing:{','.join(sorted(missing))}"
            row_count = 0
            countries: tuple[str, ...] = ()
            earliest = latest = None
            tracks = observations = None
        else:
            frame = (
                pl.scan_csv(path, infer_schema_length=1000)
                .select(
                    pl.len().alias("rows"),
                    pl.col(columns["region"]).cast(pl.String).unique().alias("regions"),
                    pl.col(columns["date"]).cast(pl.String).min().alias("earliest"),
                    pl.col(columns["date"]).cast(pl.String).max().alias("latest"),
                    pl.col(columns["title"]).cast(pl.String).n_unique().alias("tracks"),
                )
                .collect(engine="streaming")
            )
            row: dict[str, Any] = (
                frame.row(0, named=True) if frame.height else {"rows": 0, "regions": []}
            )
            regions = (
                pl.scan_csv(path, infer_schema_length=1000)
                .select(pl.col(columns["region"]).cast(pl.String).unique())
                .collect(engine="streaming")
                .to_series()
                .to_list()
            )
            countries = tuple(sorted(str(value).upper() for value in regions))
            row_count = int(row.get("rows", 0))
            earliest = date.fromisoformat(str(row["earliest"])) if row.get("earliest") else None
            latest = date.fromisoformat(str(row["latest"])) if row.get("latest") else None
            tracks = int(row["tracks"])
            observations = row_count
            status = SourceStatus.AVAILABLE
            schema_version = "kaggle-spotify-charts-v1"
        return SourceManifest(
            provider=self.provider,
            origin_platform=self.origin_platform,
            filename=str(path.relative_to(self.root)),
            path=path,
            sha256=sha256_file(path),
            size_bytes=path.stat().st_size,
            row_count=row_count,
            schema_version=schema_version,
            status=status,
            countries=countries,
            chart_types=("top200", "viral50"),
            earliest_date=earliest,
            latest_date=latest,
            number_of_tracks=tracks,
            number_of_observations=observations,
        )

    def iter_observations(
        self,
        chart: str | None = None,
        top_n: int = 100,
        countries: set[str] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        batch_size: int = 10_000,
    ) -> Iterator[SourceObservation]:
        path = self._charts_file()
        columns = self._columns(path)
        chart_col = columns.get("chart")
        title_col = columns["title"]
        rank_col = columns["rank"]
        date_col = columns["date"]
        artist_col = columns["artist"]
        region_col = columns["region"]
        stream_col = columns.get("streams")
        reader = pl.read_csv_batched(path, infer_schema_length=1000, batch_size=batch_size)
        row_number = 0
        wanted = {value.upper() for value in countries} if countries else None
        while batches := reader.next_batches(1):
            for batch in batches:
                for row in batch.iter_rows(named=True):
                    row_number += 1
                    chart_name = str(row[chart_col]) if chart_col else "top200"
                    normalized_chart = chart_name.casefold().replace(" ", "")
                    if chart and normalized_chart != chart.casefold().replace(" ", ""):
                        continue
                    if top_n and int(row[rank_col]) > top_n:
                        continue
                    country = str(row[region_col]).upper()
                    if wanted and country not in wanted:
                        continue
                    period = date.fromisoformat(str(row[date_col]))
                    if from_date and period < from_date:
                        continue
                    if to_date and period > to_date:
                        continue
                    is_viral = "viral" in normalized_chart
                    metric = (
                        None if is_viral or stream_col is None else _integer(row.get(stream_col))
                    )
                    yield SourceObservation(
                        provider=self.provider,
                        origin_platform=self.origin_platform,
                        country_code=country,
                        chart_name="viral50" if is_viral else "top200",
                        period_start=period,
                        period_end=period,
                        rank=int(row[rank_col]),
                        track_title=str(row[title_col]),
                        artist=str(row[artist_col]),
                        native_id=str(row.get(columns["url"])) if columns.get("url") else None,
                        metric_value=metric,
                        metric_type="STREAMS" if metric is not None else None,
                        source_artifact=str(path),
                        source_row_number=row_number,
                        raw_fields={key: value for key, value in row.items()},
                    )

    def import_to(
        self,
        output_path: Path,
        *,
        chart: str | None = None,
        top_n: int = 100,
        countries: set[str] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> ImportSummary:
        source_path = self._charts_file()
        source_checksum = sha256_file(source_path)
        sidecar = output_path.with_suffix(output_path.suffix + ".manifest.json")
        if output_path.exists() and sidecar.exists():
            previous = json.loads(sidecar.read_text(encoding="utf-8"))
            if (
                previous.get("source_checksum") == source_checksum
                and previous.get("chart") == chart
                and previous.get("top_n") == top_n
            ):
                rows = int(previous.get("rows", 0))
                return ImportSummary(
                    self.provider,
                    rows,
                    rows,
                    0,
                    tuple(sorted(countries or set())),
                    (chart or "all",),
                    from_date,
                    to_date,
                    output_path,
                    SourceStatus.IMPORTED,
                )
        columns = self._columns(source_path)
        required = {"title", "rank", "date", "artist", "region"}
        missing = required - columns.keys()
        if missing:
            raise ValueError(f"Kaggle charts.csv is missing columns: {sorted(missing)}")
        chart_expr = (
            pl.col(columns["chart"]).cast(pl.String) if columns.get("chart") else pl.lit("top200")
        )
        normalized_chart = chart_expr.str.to_lowercase().str.replace_all(" ", "")
        metric_expr = pl.lit(None, dtype=pl.Int64)
        if columns.get("streams"):
            metric_expr = (
                pl.when(normalized_chart.str.contains("viral"))
                .then(pl.lit(None, dtype=pl.Int64))
                .otherwise(
                    pl.col(columns["streams"])
                    .cast(pl.String, strict=False)
                    .str.replace_all(",", "")
                    .cast(pl.Int64, strict=False)
                )
            )
        frame = (
            pl.scan_csv(source_path, infer_schema_length=1000)
            .with_columns(
                pl.lit(self.provider).alias("provider"),
                pl.lit(self.origin_platform).alias("origin_platform"),
                pl.col(columns["region"]).cast(pl.String).str.to_uppercase().alias("country_code"),
                normalized_chart.alias("chart_name"),
                pl.col(columns["date"])
                .cast(pl.String)
                .str.strptime(pl.Date, format="%Y-%m-%d", strict=False)
                .alias("period_start"),
                pl.col(columns["rank"]).cast(pl.Int32, strict=False).alias("rank"),
                pl.col(columns["title"]).cast(pl.String).alias("track_title"),
                pl.col(columns["artist"]).cast(pl.String).alias("artist"),
                pl.col(columns.get("url", columns["title"])).cast(pl.String).alias("native_id"),
                metric_expr.alias("metric_value"),
                pl.when(normalized_chart.str.contains("viral"))
                .then(pl.lit(None))
                .otherwise(pl.lit("STREAMS"))
                .alias("metric_type"),
                pl.lit(str(source_path)).alias("source_artifact"),
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
        if chart:
            frame = frame.filter(pl.col("chart_name") == chart.casefold().replace(" ", ""))
        if top_n:
            frame = frame.filter(pl.col("rank") <= top_n)
        if countries:
            frame = frame.filter(pl.col("country_code").is_in(sorted(countries)))
        if from_date:
            frame = frame.filter(pl.col("period_start") >= from_date)
        if to_date:
            frame = frame.filter(pl.col("period_start") <= to_date)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows = int(frame.select(pl.len()).collect(engine="streaming").item())
        frame.sink_parquet(output_path, compression="zstd")
        sidecar.write_text(
            json.dumps(
                {"source_checksum": source_checksum, "chart": chart, "top_n": top_n, "rows": rows},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return ImportSummary(
            self.provider,
            rows,
            rows,
            0,
            tuple(sorted(countries or set())),
            (chart or "all",),
            from_date,
            to_date,
            output_path,
            SourceStatus.IMPORTED,
        )


def _integer(value: object) -> Decimal | None:
    if value is None or str(value).strip() in {"", "null", "None"}:
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except ValueError:
        return None
