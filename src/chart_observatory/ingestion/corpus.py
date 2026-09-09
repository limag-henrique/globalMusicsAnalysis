from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import polars as pl
import psycopg
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pycountry
from psycopg.types.json import Jsonb
from sqlalchemy import select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from chart_observatory.corpus.eligibility import (
    ChartCellInput,
    EligibilityResult,
    EligibilityRules,
    evaluate_cell,
    select_balanced_panel,
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
    duplicate_rows_skipped: int = 0


@dataclass(frozen=True)
class NormalizedIngestionSummary:
    source_path: Path
    source_sha256: str
    rows_seen: int
    rows_written: int
    cells: int
    snapshots: int
    tracks: int


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


def write_mgd_balanced_panel(path: Path, output: Path, rules: EligibilityRules) -> pl.DataFrame:
    """Write the common-period intersection of eligible MGD chart cells."""
    results = tuple(evaluate_cell(cell, rules) for cell in build_mgd_cell_inputs(path))
    panel = select_balanced_panel(results)
    rows = [
        {
            "provider": result.cell.provider,
            "platform_code": result.cell.platform_code,
            "country_code": result.cell.country_code,
            "chart_family": result.cell.chart_family,
            "period_start": period,
        }
        for result in panel.cells
        for period in panel.common_periods
    ]
    frame = pl.DataFrame(
        rows,
        schema={
            "provider": pl.String,
            "platform_code": pl.String,
            "country_code": pl.String,
            "chart_family": pl.String,
            "period_start": pl.Date,
        },
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
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        return ingest_mgd_postgres_copy(session, path, batch_size=batch_size, rules=rules)
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
        for result in profiles:
            profile_chart_cell(session, result)
        session.commit()
        return MgdIngestionSummary(path, source_hash, 0, 0, len(profiles), 0, 0, profiles)

    definitions: dict[tuple[str, str], ChartDefinition] = {}
    snapshots: dict[tuple[str, str, date], ChartSnapshot] = {}
    items: dict[str, PlatformItem] = {}
    tracks: dict[str, CanonicalTrack] = {}
    links: set[str] = set()
    cell_periods: dict[tuple[str, str], set[date]] = defaultdict(set)
    cell_depths: dict[tuple[str, str, date], int] = {}
    rows_seen = rows_written = duplicate_rows_skipped = 0
    positions_by_snapshot: dict[tuple[str, str, date], set[int]] = defaultdict(set)

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
        position_key = (country, chart_name, period)
        if rank in positions_by_snapshot[position_key]:
            duplicate_rows_skipped += 1
            continue
        positions_by_snapshot[position_key].add(rank)
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
        duplicate_rows_skipped,
    )


def ingest_normalized_parquet(
    session: Session,
    path: Path,
    *,
    batch_size: int = 50_000,
    rules: EligibilityRules | None = None,
) -> NormalizedIngestionSummary:
    """Load any normalized source artifact into the PostgreSQL chart store.

    Normalized source files intentionally share a small interchange contract while
    retaining provider-specific metadata.  The PostgreSQL implementation uses a
    temporary COPY staging table so multi-million-row artifacts do not go through
    the ORM one row at a time.
    """
    del batch_size
    if session.bind is None or session.bind.dialect.name != "postgresql":
        raise RuntimeError("normalized bulk ingestion requires PostgreSQL")
    source_hash = sha256_file(path)
    existing_snapshot = session.scalar(
        select(ChartSnapshot).where(
            ChartSnapshot.provider_metadata["source_sha256"].as_string() == source_hash
        )
    )
    if existing_snapshot is not None:
        cells = build_normalized_cell_inputs(path)
        profiles = tuple(evaluate_cell(cell, rules or EligibilityRules()) for cell in cells)
        for result in profiles:
            profile_chart_cell(session, result)
        session.commit()
        return NormalizedIngestionSummary(path, source_hash, 0, 0, len(cells), 0, 0)
    # The hash lookup opens a SQLAlchemy transaction.  Release it before the
    # independent psycopg COPY connection so interrupted imports do not leave
    # an idle transaction holding an old snapshot.
    session.rollback()

    bind = session.get_bind()
    engine = bind if isinstance(bind, Engine) else bind.engine
    url = make_url(str(engine.url)).set(drivername="postgresql")
    connection = psycopg.connect(url.render_as_string(hide_password=False))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TEMP TABLE normalized_import_stage (
                    provider text NOT NULL,
                    platform_code text NOT NULL,
                    country_code text NOT NULL,
                    chart_name text NOT NULL,
                    period_start date NOT NULL,
                    period_end date NOT NULL,
                    rank integer NOT NULL,
                    native_id text NOT NULL,
                    title text NOT NULL,
                    artist text,
                    metric_type text NOT NULL,
                    metric_value text,
                    item_kind text NOT NULL,
                    observed_at timestamptz,
                    source_artifact text
                ) ON COMMIT DROP
                """
            )
            _copy_rows(
                cursor,
                "normalized_import_stage",
                (
                    "provider",
                    "platform_code",
                    "country_code",
                    "chart_name",
                    "period_start",
                    "period_end",
                    "rank",
                    "native_id",
                    "title",
                    "artist",
                    "metric_type",
                    "metric_value",
                    "item_kind",
                    "observed_at",
                    "source_artifact",
                ),
                _normalized_stage_rows(path),
            )
            cursor.execute(
                """
                CREATE TEMP TABLE normalized_import_cells ON COMMIT DROP AS
                SELECT DISTINCT provider, platform_code, country_code, chart_name,
                       period_start, period_end, rank
                FROM normalized_import_stage
                """
            )
            _insert_normalized_geographies(cursor, path)
            cursor.execute(
                """
                INSERT INTO chart_definitions (
                    id, platform_code, source_code, country_code, chart_name,
                    native_frequency, nominal_depth, methodology_version
                )
                SELECT gen_random_uuid(), platform_code, provider, country_code, chart_name,
                       CASE WHEN platform_code = 'YOUTUBE_VIDEO' THEN 'SNAPSHOT' ELSE 'DAILY' END,
                       max(rank), 'normalized-v1'
                FROM normalized_import_stage
                GROUP BY platform_code, provider, country_code, chart_name
                ON CONFLICT (platform_code, source_code, country_code, chart_name) DO NOTHING
                """
            )
            cursor.execute(
                """
                CREATE TEMP TABLE normalized_import_items ON COMMIT DROP AS
                SELECT platform_code, native_id, max(item_kind) AS item_kind,
                       max(left(title, 1000)) AS title, max(left(artist, 1000)) AS artist
                FROM normalized_import_stage
                GROUP BY platform_code, native_id
                """
            )
            cursor.execute(
                """
                INSERT INTO platform_items (
                    id, platform_code, native_id, item_kind, title, artist
                )
                SELECT gen_random_uuid(), platform_code, native_id, item_kind, title, artist
                FROM normalized_import_items
                ON CONFLICT (platform_code, native_id) DO UPDATE
                    SET title = COALESCE(platform_items.title, EXCLUDED.title),
                        artist = COALESCE(platform_items.artist, EXCLUDED.artist)
                """
            )
            cursor.execute(
                """
                CREATE TEMP TABLE normalized_import_links ON COMMIT DROP AS
                SELECT i.id AS platform_item_id,
                       COALESCE(l.canonical_track_id, gen_random_uuid()) AS canonical_track_id,
                       i.title, i.artist,
                       (l.canonical_track_id IS NULL) AS is_new
                FROM platform_items i
                JOIN normalized_import_items ni
                  ON ni.platform_code = i.platform_code AND ni.native_id = i.native_id
                LEFT JOIN platform_item_track_links l ON l.platform_item_id = i.id
                """
            )
            cursor.execute(
                """
                INSERT INTO canonical_tracks (id, title)
                SELECT canonical_track_id, title
                FROM normalized_import_links
                WHERE is_new
                ON CONFLICT (id) DO NOTHING
                """
            )
            cursor.execute(
                """
                INSERT INTO platform_item_track_links (
                    id, canonical_track_id, platform_item_id, evidence
                )
                SELECT gen_random_uuid(), canonical_track_id, platform_item_id,
                       CASE WHEN artist IS NULL OR artist = ''
                            THEN 'NATIVE_ID' ELSE 'NATIVE_ID_ARTIST_METADATA' END
                FROM normalized_import_links
                ON CONFLICT (canonical_track_id, platform_item_id) DO NOTHING
                """
            )
            cursor.execute(
                """
                CREATE TEMP TABLE normalized_import_snapshots ON COMMIT DROP AS
                SELECT gen_random_uuid() AS id, d.id AS chart_definition_id,
                       s.period_start, s.period_end,
                       max(s.observed_at) AS observed_at,
                       encode(digest(%s::text || ':' || s.platform_code || ':' || s.provider ||
                                     ':' ||
                                     s.country_code || ':' || s.chart_name || ':' ||
                                     s.period_start::text || ':' || s.period_end::text,
                                     'sha256'), 'hex') AS checksum,
                       s.provider, s.platform_code, s.country_code, s.chart_name,
                       count(*)::integer AS entry_count
                FROM normalized_import_stage s
                JOIN chart_definitions d
                  ON d.platform_code = s.platform_code
                 AND d.source_code = s.provider
                 AND d.country_code = s.country_code
                 AND d.chart_name = s.chart_name
                GROUP BY d.id, s.period_start, s.period_end, s.provider,
                         s.platform_code, s.country_code, s.chart_name
                """,
                (source_hash,),
            )
            cursor.execute(
                """
                INSERT INTO chart_snapshots (
                    id, chart_definition_id, period_start, period_end, observed_at,
                    checksum, schema_version, collector_version, entry_count, provider_metadata
                )
                SELECT id, chart_definition_id, period_start, period_end,
                       COALESCE(observed_at, now()), checksum, 'normalized-v1',
                       'normalized-copy-v1', entry_count,
                       jsonb_build_object('source_file', %s::text, 'source_sha256', %s::text,
                                          'provider', provider, 'platform_code', platform_code)
                FROM normalized_import_snapshots
                """,
                (str(path), source_hash),
            )
            cursor.execute(
                """
                INSERT INTO chart_entries (
                    id, snapshot_id, platform_item_id, canonical_track_id, position,
                    metric_type, metric_value, raw_fields
                )
                SELECT gen_random_uuid(), si.id, pi.id, il.canonical_track_id, s.rank,
                       COALESCE(NULLIF(s.metric_type, ''), 'NONE'),
                       CASE WHEN s.metric_value ~ '^-?[0-9]+(\\.[0-9]+)?$'
                            THEN s.metric_value::numeric ELSE NULL END,
                       jsonb_build_object('artist', COALESCE(s.artist, ''),
                                          'source_artifact', COALESCE(s.source_artifact, ''),
                                          'source_sha256', %s::text, 'provider', s.provider)
                FROM normalized_import_stage s
                JOIN normalized_import_snapshots si
                  ON si.platform_code = s.platform_code AND si.provider = s.provider
                 AND si.country_code = s.country_code AND si.chart_name = s.chart_name
                 AND si.period_start = s.period_start AND si.period_end = s.period_end
                JOIN platform_items pi
                  ON pi.platform_code = s.platform_code AND pi.native_id = s.native_id
                JOIN normalized_import_links il ON il.platform_item_id = pi.id
                ON CONFLICT (snapshot_id, position) DO NOTHING
                """,
                (source_hash,),
            )
            written = cursor.rowcount
            snapshot_row = cursor.execute(
                "SELECT count(*) FROM normalized_import_snapshots"
            ).fetchone()
            track_row = cursor.execute(
                "SELECT count(*) FROM normalized_import_links WHERE is_new"
            ).fetchone()
            input_row = cursor.execute("SELECT count(*) FROM normalized_import_stage").fetchone()
            snapshots = int(snapshot_row[0] if snapshot_row else 0)
            tracks = int(track_row[0] if track_row else 0)
            rows_seen = int(input_row[0] if input_row else 0)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    cells = build_normalized_cell_inputs(path)
    profiles = tuple(evaluate_cell(cell, rules or EligibilityRules()) for cell in cells)
    for result in profiles:
        profile_chart_cell(session, result)
    session.commit()
    return NormalizedIngestionSummary(
        path, source_hash, rows_seen, written, len(cells), snapshots, tracks
    )


def build_normalized_cell_inputs(path: Path) -> tuple[ChartCellInput, ...]:
    scan = pl.scan_parquet(path)
    schema = scan.collect_schema()
    platform_column = "origin_platform" if "origin_platform" in schema else "platform_code"
    chart_column = "chart_name" if "chart_name" in schema else "chart_family"
    frame = (
        scan.with_columns(
            pl.col(platform_column).alias("_platform"),
            pl.col(chart_column).alias("_chart"),
        )
        .group_by("provider", "_platform", "country_code", "_chart", "period_start")
        .agg(pl.col("rank").max().alias("depth"))
        .collect(engine="streaming")
    )
    grouped: dict[tuple[str, str, str, str], list[tuple[date, int]]] = defaultdict(list)
    for row in frame.iter_rows(named=True):
        grouped[
            (
                str(row["provider"]),
                str(row["_platform"]),
                str(row["country_code"]).upper(),
                str(row["_chart"]),
            )
        ].append((row["period_start"], int(row["depth"] or 0)))
    return tuple(
        ChartCellInput(
            provider,
            platform,
            country,
            chart.upper().replace(" ", "_"),
            "SNAPSHOT" if platform == "YOUTUBE_VIDEO" else "DAILY",
            tuple(period for period, _ in values),
            tuple(depth for _, depth in values),
        )
        for (provider, platform, country, chart), values in sorted(grouped.items())
    )


def _normalized_stage_rows(path: Path) -> Iterator[tuple[object, ...]]:
    for raw in iter_parquet_rows(path):
        provider = str(raw.get("provider") or "UNKNOWN").strip()
        platform = str(raw.get("origin_platform") or raw.get("platform_code") or "UNKNOWN").strip()
        country = _normalize_country_code(raw.get("country_code"))
        chart = str(raw.get("chart_name") or raw.get("chart_family") or "UNKNOWN").strip()
        period_start = _as_date(raw.get("period_start"))
        period_end = _as_date(raw.get("period_end")) if raw.get("period_end") else period_start
        title = str(raw.get("track_title") or raw.get("title") or "").strip()
        native_id = _normalize_native_id(platform, raw.get("native_id"), title, raw.get("artist"))
        observed_at = raw.get("observed_at")
        yield (
            provider,
            platform,
            country,
            chart,
            period_start,
            period_end,
            int(str(raw.get("rank") or 0)),
            native_id,
            title,
            str(raw.get("artist") or "").strip() or None,
            str(raw.get("metric_type") or "NONE").strip() or "NONE",
            None if raw.get("metric_value") is None else str(raw.get("metric_value")),
            str(raw.get("item_kind") or ("VIDEO" if platform == "YOUTUBE_VIDEO" else "TRACK")),
            observed_at,
            str(raw.get("source_artifact") or raw.get("raw_artifact_path") or "") or None,
        )


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@lru_cache(maxsize=256)
def _normalize_country_code(value: object) -> str:
    raw = str(value or "GLOBAL").strip().upper()
    if raw == "GLOBAL":
        return raw
    if len(raw) == 2 and pycountry.countries.get(alpha_2=raw) is not None:
        return raw
    aliases = {
        "CZECH REPUBLIC": "CZ",
        "SOUTH KOREA": "KR",
        "TAIWAN": "TW",
        "TURKEY": "TR",
        "UNITED KINGDOM": "GB",
        "UNITED STATES": "US",
        "VIETNAM": "VN",
    }
    if raw in aliases:
        return aliases[raw]
    matches = pycountry.countries.search_fuzzy(raw)
    if not matches:
        raise ValueError(f"unknown ISO-3166 market: {value}")
    return str(matches[0].alpha_2)  # type: ignore[attr-defined]


def _normalize_native_id(platform: str, value: object, title: object, artist: object) -> str:
    raw = str(value or "").strip()
    if platform == "SPOTIFY" and "/track/" in raw:
        raw = raw.split("/track/", 1)[1].split("?", 1)[0].split("/", 1)[0]
    if raw:
        return raw
    digest = hashlib.sha256(
        f"{platform}|{str(artist or '').casefold()}|{str(title or '').casefold()}".encode()
    ).hexdigest()
    return f"derived:{digest}"


def _insert_normalized_geographies(cursor: Any, path: Path) -> None:
    countries = (
        pl.scan_parquet(path)
        .select(pl.col("country_code").cast(pl.String).alias("country"))
        .unique()
        .collect(engine="streaming")
        .get_column("country")
        .to_list()
    )
    for country_value in countries:
        country = _normalize_country_code(country_value)
        if country == "GLOBAL":
            continue
        record = geography_for_market(country)
        cursor.execute(
            """
            INSERT INTO market_geography (
                id, country_code, iso3, country_name, m49, region, subregion,
                intermediate_region, source, source_version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (country_code, source_version) DO NOTHING
            """,
            (
                uuid4(),
                record.country_code,
                record.iso3,
                record.country_name,
                record.m49,
                record.region,
                record.subregion,
                record.intermediate_region,
                record.source,
                record.source_version,
            ),
        )


def ingest_mgd_postgres_copy(
    session: Session,
    path: Path,
    *,
    batch_size: int = 50_000,
    rules: EligibilityRules | None = None,
) -> MgdIngestionSummary:
    """Bulk-load MGD dimensions and entries through PostgreSQL COPY."""
    del batch_size
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
        for result in profiles:
            profile_chart_cell(session, result)
        session.commit()
        return MgdIngestionSummary(path, source_hash, 0, 0, len(profiles), 0, 0, profiles)
    now = datetime.now(UTC)
    definitions: dict[tuple[str, str], UUID] = {}
    snapshots: dict[tuple[str, str, date], UUID] = {}
    snapshot_counts: dict[tuple[str, str, date], int] = defaultdict(int)
    tracks: dict[str, UUID] = {}
    track_titles: dict[str, str] = {}
    items: dict[str, UUID] = {}
    item_titles: dict[str, str] = {}
    links: dict[str, tuple[UUID, UUID, str]] = {}
    cell_periods: dict[tuple[str, str], set[date]] = defaultdict(set)
    cell_depths: dict[tuple[str, str, date], int] = {}
    rows_seen = 0
    duplicate_rows_skipped = 0
    seen_input_keys: set[tuple[str, str, date, int]] = set()

    for raw in iter_parquet_rows(path):
        rows_seen += 1
        country, chart_name, period, rank = _mgd_row_key(raw)
        duplicate_key = (country, chart_name, period, rank)
        if duplicate_key in seen_input_keys:
            duplicate_rows_skipped += 1
            continue
        seen_input_keys.add(duplicate_key)
        cell_periods[(country, chart_name)].add(period)
        cell_depths[(country, chart_name, period)] = max(
            rank, cell_depths.get((country, chart_name, period), 0)
        )
        definition_key = (country, chart_name)
        definitions.setdefault(definition_key, uuid4())
        snapshot_key = (country, chart_name, period)
        snapshots.setdefault(snapshot_key, uuid4())
        snapshot_counts[snapshot_key] += 1
        native_id = str(raw.get("native_id") or "").strip()
        title = str(raw.get("track_title") or "").strip()
        track_key = native_id or f"{title.casefold()}|{str(raw.get('artist') or '').casefold()}"
        tracks.setdefault(track_key, uuid4())
        track_titles.setdefault(track_key, title)
        item_key = native_id or track_key
        items.setdefault(item_key, uuid4())
        item_titles.setdefault(item_key, title)
        links.setdefault(
            item_key,
            (
                tracks[track_key],
                items[item_key],
                "EXACT_NATIVE_ID" if native_id else "TITLE_ARTIST_KEY",
            ),
        )

    bind = session.get_bind()
    engine = bind if isinstance(bind, Engine) else bind.engine
    url = make_url(str(engine.url)).set(drivername="postgresql")
    connection = psycopg.connect(url.render_as_string(hide_password=False))
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET synchronous_commit = off")
            _copy_rows(
                cursor,
                "market_geography",
                (
                    "id",
                    "country_code",
                    "iso3",
                    "country_name",
                    "m49",
                    "region",
                    "subregion",
                    "intermediate_region",
                    "source",
                    "source_version",
                ),
                _geography_rows(cell_periods),
            )
            _copy_rows(
                cursor,
                "chart_definitions",
                (
                    "id",
                    "platform_code",
                    "source_code",
                    "country_code",
                    "chart_name",
                    "native_frequency",
                    "nominal_depth",
                    "methodology_version",
                ),
                (
                    (
                        definition_id,
                        "SPOTIFY",
                        "MGD",
                        country,
                        chart_name,
                        "DAILY",
                        200,
                        "mgd-v1",
                    )
                    for (country, chart_name), definition_id in definitions.items()
                ),
            )
            _copy_rows(
                cursor,
                "canonical_tracks",
                ("id", "title"),
                ((track_id, track_titles[key]) for key, track_id in tracks.items()),
            )
            _copy_rows(
                cursor,
                "platform_items",
                ("id", "platform_code", "native_id", "item_kind", "title"),
                (
                    (item_id, "SPOTIFY", item_key, "CATALOG_TRACK", item_titles[item_key])
                    for item_key, item_id in items.items()
                ),
            )
            _copy_rows(
                cursor,
                "platform_item_track_links",
                ("id", "canonical_track_id", "platform_item_id", "evidence"),
                (
                    (
                        uuid4(),
                        track_id,
                        item_id,
                        evidence,
                    )
                    for track_id, item_id, evidence in links.values()
                ),
            )
            _copy_rows(
                cursor,
                "chart_snapshots",
                (
                    "id",
                    "chart_definition_id",
                    "period_start",
                    "period_end",
                    "observed_at",
                    "checksum",
                    "schema_version",
                    "collector_version",
                    "entry_count",
                    "provider_metadata",
                ),
                (
                    (
                        snapshot_id,
                        definitions[(country, chart_name)],
                        period,
                        period,
                        now,
                        hashlib.sha256(f"{source_hash}:{country}:{chart_name}:{period}".encode()).hexdigest(),
                        "mgd-v1",
                        "mgd-ingestion-copy-v1",
                        count,
                        Jsonb({"source_file": str(path), "source_sha256": source_hash}),
                    )
                    for (country, chart_name, period), snapshot_id in snapshots.items()
                    for count in (snapshot_counts[(country, chart_name, period)],)
                ),
            )
            _copy_rows(
                cursor,
                "chart_entries",
                (
                    "id",
                    "snapshot_id",
                    "platform_item_id",
                    "canonical_track_id",
                    "position",
                    "metric_type",
                    "metric_value",
                    "raw_fields",
                ),
                _entry_rows(
                    path,
                    source_hash,
                    snapshots,
                    tracks,
                    items,
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

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
        rows_seen - duplicate_rows_skipped,
        len(cell_periods),
        len(snapshots),
        len(tracks),
        results,
        duplicate_rows_skipped,
    )


def _mgd_row_key(raw: dict[str, object]) -> tuple[str, str, date, int]:
    country = str(raw["country_code"]).upper()
    chart_name = str(raw["chart_name"])
    period = raw["period_start"]
    if not isinstance(period, date):
        period = date.fromisoformat(str(period))
    return country, chart_name, period, int(str(raw["rank"]))


def _geography_rows(cell_periods: dict[tuple[str, str], set[date]]) -> Iterator[tuple[object, ...]]:
    for country in sorted({country for country, _ in cell_periods if country != "GLOBAL"}):
        record = geography_for_market(country)
        yield (
            uuid4(),
            record.country_code,
            record.iso3,
            record.country_name,
            record.m49,
            record.region,
            record.subregion,
            record.intermediate_region,
            record.source,
            record.source_version,
        )


def _entry_rows(
    path: Path,
    source_hash: str,
    snapshots: dict[tuple[str, str, date], UUID],
    tracks: dict[str, UUID],
    items: dict[str, UUID],
) -> Iterator[tuple[object, ...]]:
    seen_keys: set[tuple[str, str, date, int]] = set()
    for raw in iter_parquet_rows(path):
        country, chart_name, period, rank = _mgd_row_key(raw)
        key = (country, chart_name, period, rank)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        native_id = str(raw.get("native_id") or "").strip()
        title = str(raw.get("track_title") or "").strip()
        track_key = native_id or f"{title.casefold()}|{str(raw.get('artist') or '').casefold()}"
        item_key = native_id or track_key
        metric_value = raw.get("metric_value")
        yield (
            uuid4(),
            snapshots[(country, chart_name, period)],
            items[item_key],
            tracks[track_key],
            rank,
            str(raw.get("metric_type") or "NONE"),
            Decimal(str(metric_value)) if metric_value is not None else None,
            Jsonb(
                {
                    "artist": str(raw.get("artist") or ""),
                    "source_artifact": str(path),
                    "source_sha256": source_hash,
                }
            ),
        )


def _copy_rows(
    cursor: object,
    table: str,
    columns: tuple[str, ...],
    rows: Iterator[tuple[object, ...]],
) -> None:
    copy_sql = f"COPY {table} ({', '.join(columns)}) FROM STDIN"
    with cursor.copy(copy_sql) as copy:  # type: ignore[attr-defined]
        for row in rows:
            copy.write_row(row)
