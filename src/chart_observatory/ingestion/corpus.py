from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.corpus.eligibility import (
    ChartCellInput,
    EligibilityResult,
    EligibilityRules,
    evaluate_cell,
)
from chart_observatory.corpus.repository import profile_chart_cell, upsert_geography
from chart_observatory.db.models.charts import ChartDefinition, ChartEntry, ChartSnapshot
from chart_observatory.db.models.tracks import (
    CanonicalTrack,
    PlatformItem,
    PlatformItemTrackLink,
)
from chart_observatory.metadata.geography import geography_for_market


@dataclass(frozen=True)
class MgdIngestionSummary:
    source_path: Path
    source_sha256: str
    rows_seen: int
    rows_written: int
    markets: int
    snapshots: int
    tracks: int
    profiles: tuple[EligibilityResult, ...]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def iter_parquet_rows(path: Path, batch_size: int = 50_000) -> Iterator[dict[str, object]]:
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(batch_size=batch_size):
        yield from batch.to_pylist()


def build_mgd_cell_inputs(path: Path) -> tuple[ChartCellInput, ...]:
    scan = pl.scan_parquet(path)
    periods = (
        scan.select("country_code", "chart_name", "period_start")
        .unique()
        .sort("country_code", "chart_name", "period_start")
        .collect(engine="streaming")
    )
    depths = (
        scan.group_by("country_code", "chart_name", "period_start")
        .agg(pl.col("rank").max().alias("depth"))
        .collect(engine="streaming")
    )
    depth_map: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row in depths.iter_rows(named=True):
        depth_map[(str(row["country_code"]).upper(), str(row["chart_name"]))].append(
            int(row["depth"] or 0)
        )
    grouped: dict[tuple[str, str], list[date]] = defaultdict(list)
    for row in periods.iter_rows(named=True):
        grouped[(str(row["country_code"]).upper(), str(row["chart_name"]))].append(
            row["period_start"]
        )
    return tuple(
        ChartCellInput(
            provider="MGD",
            platform_code="SPOTIFY",
            country_code=country,
            chart_family=chart.upper().replace(" ", "_"),
            frequency="DAILY",
            periods=tuple(values),
            depths=tuple(depth_map[(country, chart)]),
        )
        for (country, chart), values in sorted(grouped.items())
    )


def write_mgd_coverage(path: Path, output: Path, rules: EligibilityRules) -> pl.DataFrame:
    results = [evaluate_cell(cell, rules) for cell in build_mgd_cell_inputs(path)]
    frame = pl.DataFrame(
        [
            {
                "provider": result.cell.provider,
                "platform_code": result.cell.platform_code,
                "country_code": result.cell.country_code,
                "chart_family": result.cell.chart_family,
                "frequency": result.cell.frequency,
                "first_date": result.first_date,
                "last_date": result.last_date,
                "expected_periods": result.expected_periods,
                "observed_periods": result.observed_periods,
                "coverage_ratio": result.coverage_ratio,
                "longest_gap": result.longest_gap,
                "median_chart_depth": result.median_chart_depth,
                "eligible": result.eligible,
                "reasons": "|".join(result.reasons),
            }
            for result in results
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(output)
    return frame


def ingest_mgd_parquet(
    session: Session,
    path: Path,
    *,
    batch_size: int = 50_000,
    limit: int | None = None,
    rules: EligibilityRules | None = None,
) -> MgdIngestionSummary:
    source_hash = sha256_file(path)
    existing_snapshot = session.scalar(
        select(ChartSnapshot).where(
            ChartSnapshot.provider_metadata["source_sha256"].as_string() == source_hash
        )
    )
    if existing_snapshot is not None:
        profiles = tuple(
            evaluate_cell(cell, rules or EligibilityRules()) for cell in build_mgd_cell_inputs(path)
        )
        return MgdIngestionSummary(path, source_hash, 0, 0, len(profiles), 0, 0, profiles)

    definitions: dict[tuple[str, str], ChartDefinition] = {}
    snapshots: dict[tuple[str, str, date], ChartSnapshot] = {}
    items: dict[str, PlatformItem] = {}
    tracks: dict[str, CanonicalTrack] = {}
    links: set[str] = set()
    cell_periods: dict[tuple[str, str], set[date]] = defaultdict(set)
    cell_depths: dict[tuple[str, str, date], int] = {}
    rows_seen = rows_written = 0

    for raw in iter_parquet_rows(path, batch_size):
        if limit is not None and rows_seen >= limit:
            break
        rows_seen += 1
        country = str(raw["country_code"]).upper()
        chart_name = str(raw["chart_name"])
        period = raw["period_start"]
        if not isinstance(period, date):
            period = date.fromisoformat(str(period))
        key = (country, chart_name)
        cell_periods[key].add(period)
        rank = int(str(raw["rank"]))
        cell_depths[(country, chart_name, period)] = max(
            rank, cell_depths.get((country, chart_name, period), 0)
        )
        if key not in definitions:
            definition = session.scalar(
                select(ChartDefinition).where(
                    ChartDefinition.platform_code == "SPOTIFY",
                    ChartDefinition.source_code == "MGD",
                    ChartDefinition.country_code == country,
                    ChartDefinition.chart_name == chart_name,
                )
            )
            if definition is None:
                definition = ChartDefinition(
                    platform_code="SPOTIFY",
                    source_code="MGD",
                    country_code=country,
                    chart_name=chart_name,
                    native_frequency="DAILY",
                    nominal_depth=200,
                    methodology_version="mgd-v1",
                )
                session.add(definition)
                session.flush()
            definitions[key] = definition
            if country != "GLOBAL":
                upsert_geography(session, geography_for_market(country))
        snapshot_key = (country, chart_name, period)
        snapshot = snapshots.get(snapshot_key)
        if snapshot is None:
            snapshot = session.scalar(
                select(ChartSnapshot).where(
                    ChartSnapshot.chart_definition_id == definitions[key].id,
                    ChartSnapshot.period_start == period,
                    ChartSnapshot.period_end == period,
                )
            )
            if snapshot is None:
                snapshot = ChartSnapshot(
                    chart_definition_id=definitions[key].id,
                    period_start=period,
                    period_end=period,
                    observed_at=datetime.now(UTC),
                    checksum=hashlib.sha256(
                        f"{source_hash}:{country}:{chart_name}:{period}".encode()
                    ).hexdigest(),
                    schema_version="mgd-v1",
                    collector_version="mgd-ingestion-v1",
                    provider_metadata={"source_file": str(path), "source_sha256": source_hash},
                )
                session.add(snapshot)
                session.flush()
            snapshots[snapshot_key] = snapshot
        native_id = str(raw.get("native_id") or "").strip()
        title = str(raw.get("track_title") or "").strip()
        track_key = native_id or f"{title.casefold()}|{str(raw.get('artist') or '').casefold()}"
        track = tracks.get(track_key)
        if track is None:
            track = CanonicalTrack(title=title)
            session.add(track)
            session.flush()
            tracks[track_key] = track
        item_key = native_id or track_key
        item = items.get(item_key)
        if item is None:
            item = session.scalar(
                select(PlatformItem).where(
                    PlatformItem.platform_code == "SPOTIFY",
                    PlatformItem.native_id == item_key,
                )
            )
            if item is None:
                item = PlatformItem(
                    platform_code="SPOTIFY",
                    native_id=item_key,
                    item_kind="CATALOG_TRACK",
                    title=title,
                )
                session.add(item)
                session.flush()
            items[item_key] = item
        if item_key not in links:
            session.add(
                PlatformItemTrackLink(
                    canonical_track_id=track.id,
                    platform_item_id=item.id,
                    evidence="EXACT_NATIVE_ID" if native_id else "TITLE_ARTIST_KEY",
                )
            )
            links.add(item_key)
        metric_value = raw.get("metric_value")
        entry = ChartEntry(
            snapshot_id=snapshot.id,
            platform_item_id=item.id,
            canonical_track_id=track.id,
            position=rank,
            metric_type=str(raw.get("metric_type") or "NONE"),
            metric_value=Decimal(str(metric_value)) if metric_value is not None else None,
            raw_fields={"artist": str(raw.get("artist") or ""), "source_artifact": str(path)},
        )
        session.add(entry)
        rows_written += 1
        if rows_written % batch_size == 0:
            session.flush()
            session.commit()
    session.flush()
    session.commit()

    profile_inputs = tuple(
        ChartCellInput(
            "MGD",
            "SPOTIFY",
            country,
            chart.upper().replace(" ", "_"),
            "DAILY",
            tuple(sorted(periods)),
            tuple(cell_depths[(country, chart, period)] for period in sorted(periods)),
        )
        for (country, chart), periods in sorted(cell_periods.items())
    )
    results = tuple(evaluate_cell(cell, rules or EligibilityRules()) for cell in profile_inputs)
    for result in results:
        profile_chart_cell(session, result)
    session.commit()
    return MgdIngestionSummary(
        path,
        source_hash,
        rows_seen,
        rows_written,
        len(cell_periods),
        len(snapshots),
        len(tracks),
        results,
    )
