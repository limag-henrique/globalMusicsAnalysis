"""Recover the pinned original archive without the legacy Top100 normalization cap."""

import hashlib
import json
import os
import shutil
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

os.environ.setdefault("POLARS_MAX_THREADS", "2")
import httpx
import polars as pl
from download_historical_charts import download

from chart_observatory.ingestion.historical_backfill import integer_metric
from chart_observatory.sources.catalog import _country_aliases

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/historical_backfill/20261030/kaggle-dhruvildave-v85"
STATE = ROOT / "data/runtime/kaggle-original-recovery-20261031"


def report(stage, **details):
    STATE.mkdir(parents=True, exist_ok=True)
    part = STATE / "status.part"
    part.write_text(
        json.dumps(
            dict(stage=stage, pid=os.getpid(), updated_at=datetime.now(UTC).isoformat(), **details),
            indent=2,
        ),
        encoding="utf-8",
    )
    part.replace(STATE / "status.json")


def main():
    OUT.mkdir(exist_ok=True)
    archive = OUT / "charts.csv.zip"
    report("downloading_original_archive", expected_bytes=991225045)
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        download(
            client,
            "https://www.kaggle.com/api/v1/datasets/download/dhruvildave/spotify-charts/charts.csv?datasetVersionNumber=85",
            archive,
            size=991225045,
        )
    original = OUT / "charts.csv"
    report("extracting_original_csv")
    with zipfile.ZipFile(archive) as package:
        member = package.getinfo("charts.csv")
        if member.file_size != 3483476388:
            raise ValueError("pinned original CSV size differs from public file manifest")
        if not original.exists():
            part = original.with_suffix(".part")
            with package.open(member) as source, part.open("wb") as target:
                shutil.copyfileobj(source, target, length=4 * 1024**2)
            if part.stat().st_size != member.file_size:
                raise ValueError("incomplete extracted CSV")
            part.replace(original)
        if original.stat().st_size != member.file_size:
            raise ValueError("existing extracted CSV size mismatch")
    with original.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    original.with_suffix(".csv.sha256").write_text(digest + "\n", encoding="utf-8")
    report("normalizing_all_top200_rows", original_sha256=digest)
    frame = pl.scan_csv(original, infer_schema=False)
    schema = frame.collect_schema()
    required = {"region", "date", "url", "title", "artist", "streams", "rank", "chart"}
    if not required.issubset(schema.names()):
        raise ValueError("unexpected original CSV columns")
    frame = (
        frame.filter(pl.col("chart") == "top200")
        .select(
            pl.col("region").str.to_uppercase().replace(_country_aliases()).alias("country_code"),
            pl.col("date").str.to_date().alias("period_end"),
            pl.col("url").str.extract(r"/track/([A-Za-z0-9]{22})(?:\?.*)?$", 1).alias("native_id"),
            pl.col("title"),
            pl.col("artist"),
            integer_metric("streams").alias("metric_value"),
            pl.col("rank").cast(pl.Int32, strict=False).alias("source_rank"),
        )
        .filter(pl.col("period_end").is_between(date(2018, 1, 1), date(2026, 10, 15)))
    )
    normalized = OUT / "full-top200.parquet"
    part = normalized.with_suffix(".part")
    frame.sink_parquet(part, compression="zstd", row_group_size=65536)
    part.replace(normalized)
    summary = (
        pl.scan_parquet(normalized)
        .group_by("country_code")
        .agg(
            pl.len().alias("rows"),
            pl.col("period_end").n_unique().alias("days"),
            pl.col("source_rank").max().alias("maximum_source_rank"),
        )
        .collect()
        .sort("country_code")
        .to_dicts()
    )
    (OUT / "normalization-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report(
        "normalized_pending_calendar_reconciliation",
        normalized_file=str(normalized),
        original_sha256=digest,
        countries=len(summary),
        maximum_rank=200,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        report("failed", error_type=type(exc).__name__)
        raise
