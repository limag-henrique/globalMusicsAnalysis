# ruff: noqa: B008

import json
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import polars as pl
import typer
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

from chart_observatory.adapters.files.manual import ImportMetadata
from chart_observatory.adapters.youtube_data.most_popular import YouTubeMostPopularSource
from chart_observatory.application import ResearchApplication
from chart_observatory.charts.registry import AdapterRegistry
from chart_observatory.config import Settings
from chart_observatory.corpus.catalog_reconciliation import (
    canonical_track_reference,
    canonicalize_catalog_lazy,
)
from chart_observatory.corpus.eligibility import EligibilityRules
from chart_observatory.corpus.freeze import freeze_source_artifacts
from chart_observatory.corpus.repository import (
    CorpusFreezeRequest,
    freeze_corpus,
    reconcile_entries,
)
from chart_observatory.db.models.charts import ChartSnapshot
from chart_observatory.domain.enums import RightsOperation, RightsProfileStatus
from chart_observatory.domain.errors import SourceDisabled
from chart_observatory.exports.analytical import write_mgd_analytical_datasets
from chart_observatory.exports.article_analytics import write_article_datasets
from chart_observatory.ingestion.corpus import (
    ingest_mgd_parquet,
    ingest_normalized_parquet,
    write_mgd_balanced_panel,
    write_mgd_coverage,
)
from chart_observatory.ingestion.youtube import collect_youtube_current
from chart_observatory.lyrics.gemini_pipeline import (
    GeminiAnnotationClient,
    GeminiApiError,
    LrclibClient,
    LyricsOvhClient,
    append_jsonl,
    existing_song_ids,
    throttle,
)
from chart_observatory.lyrics.repository import (
    LyricDocumentInput,
    annotate_document,
    annotation_input_from_dict,
    ingest_lyric_document,
)
from chart_observatory.procurement.schema_profiler import profile_sample
from chart_observatory.rights.gate import RightsGate
from chart_observatory.rights.models import RightsGrant, RightsProfile
from chart_observatory.rights.repository import InMemoryRightsRepository
from chart_observatory.sources.catalog import (
    CatalogFilters,
    catalog_source_paths,
    filter_source_catalog,
    scan_source_catalog,
    write_source_catalog,
)
from chart_observatory.sources.chartmetric import ChartmetricClient, ChartmetricError
from chart_observatory.sources.chartmetric_backfill import (
    BackfillRequest,
    ChartmetricBackfillRunner,
    consolidate_backfill_observations,
)
from chart_observatory.sources.http import HttpxTransport
from chart_observatory.sources.kaggle import KaggleSpotifyChartsSource
from chart_observatory.sources.mgd import MGDSource
from chart_observatory.sources.promusica import ProMusicaBrasilSource
from chart_observatory.sources.reports import (
    write_artist_year_report_from_parquet,
    write_global_market_coverage,
    write_market_capability_inventory,
    write_top_artist_list,
)
from chart_observatory.sources.youtube import YouTubeMarketDiscovery
from chart_observatory.ui.classifications import JsonClassificationRepository
from chart_observatory.ui.taxonomy import TAXONOMY_VERSION

app = typer.Typer(help="Rights-gated cross-platform chart research tools.")
collect_app = typer.Typer()
import_app = typer.Typer()
coverage_app = typer.Typer()
metrics_app = typer.Typer()
export_app = typer.Typer()
procurement_app = typer.Typer()
sources_app = typer.Typer(help="Inspect and administer source inventories.")
mgd_app = typer.Typer(help="Local MGD/MGD+ source.")
kaggle_app = typer.Typer(help="Kaggle Spotify Charts source.")
chartmetric_app = typer.Typer(help="Chartmetric authenticated source.")
promusica_app = typer.Typer(help="Pro-Música Brasil public source.")
youtube_app = typer.Typer(help="YouTube Data API market discovery.")
corpus_app = typer.Typer(help="Canonical corpus, eligibility, and scientific freeze operations.")
db_app = typer.Typer(help="Operational PostgreSQL schema management.")
app.add_typer(collect_app, name="collect")
app.add_typer(import_app, name="import-chart")
app.add_typer(coverage_app, name="coverage")
app.add_typer(metrics_app, name="metrics")
app.add_typer(export_app, name="export")
app.add_typer(procurement_app, name="procurement")
app.add_typer(sources_app, name="sources")
sources_app.add_typer(mgd_app, name="mgd")
sources_app.add_typer(kaggle_app, name="kaggle")
sources_app.add_typer(chartmetric_app, name="chartmetric")
sources_app.add_typer(promusica_app, name="promusica")
sources_app.add_typer(youtube_app, name="youtube")
app.add_typer(corpus_app, name="corpus")
app.add_typer(db_app, name="db")


@db_app.command("upgrade")
def database_upgrade(
    database_url: str | None = typer.Option(None, envvar="CHART_OBSERVATORY_DATABASE_URL"),
    revision: str = typer.Option("head", help="Alembic revision to apply."),
) -> None:
    """Apply database migrations before starting API or Streamlit."""
    settings = Settings.load(Path.cwd())
    url = database_url or settings.database_url
    config = AlembicConfig(str(Path("alembic.ini").resolve()))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    alembic_command.upgrade(config, revision)
    typer.echo(json.dumps({"status": "UPGRADED", "revision": revision}))


class _ConfiguredYouTubeKey:
    def __init__(self, value: str) -> None:
        self.value = value

    def api_key(self) -> str:
        return self.value


def _service(authorized: bool = False) -> ResearchApplication:
    settings = Settings.load(Path.cwd())
    return ResearchApplication(
        Path("data/runtime"), database_url=settings.database_url, manual_authorized=authorized
    )


@corpus_app.command("coverage")
def corpus_coverage(
    input_path: Path = typer.Option(Path("data/normalized/mgd_observations.parquet"), "--input"),
    output: Path = typer.Option(Path("data/derived/mgd_coverage.parquet")),
    minimum_coverage: float = typer.Option(0.95),
    minimum_years: int = typer.Option(3),
    minimum_chart_depth: int = typer.Option(100),
    balanced_output: Path = typer.Option(Path("data/derived/mgd_balanced_panel.parquet")),
) -> None:
    """Profile provider/platform/market/chart-family cells and select comparability."""
    frame = write_mgd_coverage(
        input_path,
        output,
        EligibilityRules(
            minimum_coverage=minimum_coverage,
            minimum_years=minimum_years,
            minimum_chart_depth=minimum_chart_depth,
        ),
    )
    balanced = write_mgd_balanced_panel(
        input_path,
        balanced_output,
        EligibilityRules(
            minimum_coverage=minimum_coverage,
            minimum_years=minimum_years,
            minimum_chart_depth=minimum_chart_depth,
        ),
    )
    typer.echo(
        json.dumps(
            {
                "status": "PROFILED",
                "cells": frame.height,
                "eligible_cells": int(frame.filter(frame["eligible"] == True).height),  # noqa: E712
                "output": str(output),
                "balanced_panel_rows": balanced.height,
                "balanced_panel_output": str(balanced_output),
            }
        )
    )


@corpus_app.command("ingest-mgd")
def corpus_ingest_mgd(
    input_path: Path = typer.Option(Path("data/normalized/mgd_observations.parquet"), "--input"),
    database_url: str | None = typer.Option(None, envvar="CHART_OBSERVATORY_DATABASE_URL"),
    limit: int | None = typer.Option(None, min=1),
    batch_size: int = typer.Option(50_000, min=100),
) -> None:
    """Import the local MGD Parquet into the operational database."""
    settings = Settings.load(Path.cwd())
    service = ResearchApplication(
        Path("data/runtime"),
        database_url=database_url or settings.database_url,
        manual_authorized=True,
    )
    summary = ingest_mgd_parquet(
        service.session,
        input_path,
        limit=limit,
        batch_size=batch_size,
        rules=EligibilityRules(
            minimum_coverage=settings.comparable_corpus.minimum_coverage,
            minimum_years=settings.comparable_corpus.minimum_years,
            minimum_chart_depth=settings.comparable_corpus.minimum_chart_depth,
            minimum_source_quality=settings.comparable_corpus.minimum_source_quality,
        ),
    )
    typer.echo(
        json.dumps(
            {
                "status": "IMPORTED",
                "rows_seen": summary.rows_seen,
                "rows_written": summary.rows_written,
                "markets": summary.markets,
                "snapshots": summary.snapshots,
                "tracks": summary.tracks,
                "duplicate_rows_skipped": summary.duplicate_rows_skipped,
                "eligible_cells": sum(result.eligible for result in summary.profiles),
            }
        )
    )


@corpus_app.command("ingest-normalized")
def corpus_ingest_normalized(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
    database_url: str | None = typer.Option(None, envvar="CHART_OBSERVATORY_DATABASE_URL"),
    batch_size: int = typer.Option(50_000, min=100),
) -> None:
    """Import a normalized Kaggle, Chartmetric, or YouTube Parquet artifact."""
    settings = Settings.load(Path.cwd())
    service = ResearchApplication(
        Path("data/runtime"),
        database_url=database_url or settings.database_url,
        manual_authorized=True,
    )
    summary = ingest_normalized_parquet(
        service.session,
        input_path,
        batch_size=batch_size,
        rules=EligibilityRules(
            minimum_coverage=settings.comparable_corpus.minimum_coverage,
            minimum_years=settings.comparable_corpus.minimum_years,
            minimum_chart_depth=settings.comparable_corpus.minimum_chart_depth,
            minimum_source_quality=settings.comparable_corpus.minimum_source_quality,
        ),
    )
    typer.echo(
        json.dumps(
            {
                "status": "IMPORTED",
                "source": str(summary.source_path),
                "rows_seen": summary.rows_seen,
                "rows_written": summary.rows_written,
                "cells": summary.cells,
                "snapshots": summary.snapshots,
                "tracks": summary.tracks,
            }
        )
    )


@corpus_app.command("reconcile")
def corpus_reconcile(
    database_url: str | None = typer.Option(None, envvar="CHART_OBSERVATORY_DATABASE_URL"),
) -> None:
    """Build canonical chart entries without deleting source entries."""
    settings = Settings.load(Path.cwd())
    service = ResearchApplication(
        Path("data/runtime"), database_url=database_url or settings.database_url
    )
    summary = reconcile_entries(service.session)
    service.session.commit()
    typer.echo(
        json.dumps(
            {
                "status": "RECONCILED",
                "canonical_entries": summary.canonical_entries,
                "conflicts": summary.conflicts,
                "unresolved_source_entries": summary.skipped_unresolved,
            }
        )
    )


@corpus_app.command("export-analytical")
def corpus_export_analytical(
    input_path: Path = typer.Option(Path("data/normalized/mgd_observations.parquet"), "--input"),
    output_dir: Path = typer.Option(Path("data/derived"), "--output-dir"),
    top_n: int = typer.Option(50, min=1),
    artist_metadata: Path = typer.Option(
        Path("mgd/artists/spotify_artists_info_complete.csv"), "--artist-metadata"
    ),
) -> None:
    """Materialize track, turnover, genre, and diversity datasets."""
    paths = write_mgd_analytical_datasets(
        input_path,
        output_dir,
        top_n=top_n,
        artist_metadata_path=artist_metadata if artist_metadata.is_file() else None,
    )
    typer.echo(
        json.dumps(
            {"status": "EXPORTED", "datasets": {name: str(path) for name, path in paths.items()}}
        )
    )


@corpus_app.command("catalog")
def corpus_catalog(
    root: Path = typer.Option(Path("."), "--root", help="Raiz que contém data/ e research/."),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Parquet/CSV de saída; sem filtros, materializa todo o catálogo disponível.",
    ),
    provider: str | None = typer.Option(None, "--provider"),
    origin_platform: str | None = typer.Option(None, "--platform"),
    country_code: str | None = typer.Option(None, "--country"),
    year: int | None = typer.Option(None, "--year"),
    chart_family: str | None = typer.Option(None, "--chart-family"),
    chart_name: str | None = typer.Option(None, "--chart-name"),
    query: str | None = typer.Option(None, "--query"),
    limit: int = typer.Option(200, min=0, max=100_000),
) -> None:
    """List or materialize all locally available source-preserving observations."""
    materialized_path = (root / "data/normalized/source_catalog.parquet").resolve()
    use_materialized = output is None or output.resolve() != materialized_path
    paths = catalog_source_paths(root, include_materialized=use_materialized)
    has_filters = any(
        value is not None
        for value in (
            provider,
            origin_platform,
            country_code,
            year,
            chart_family,
            chart_name,
            query,
        )
    )
    if output is not None and not has_filters:
        write_source_catalog(paths, output)
        rows = None
    else:
        frame = filter_source_catalog(
            paths,
            CatalogFilters(
                provider=provider,
                origin_platform=origin_platform,
                country_code=country_code,
                year=year,
                chart_family=chart_family,
                chart_name=chart_name,
                query=query,
                limit=limit,
            ),
        )
        rows = frame.to_dicts()
        if output is not None:
            if output.suffix.casefold() == ".csv":
                frame.write_csv(output)
            else:
                frame.write_parquet(output)
    typer.echo(
        json.dumps(
            {
                "status": "MATERIALIZED" if output is not None else "LISTED",
                "source_artifacts": len(paths),
                "source_paths": [str(path) for path in paths],
                "output": str(output) if output is not None else None,
                "rows": rows,
            },
            default=str,
            ensure_ascii=False,
        )
    )


@corpus_app.command("analytics")
def corpus_analytics(
    observations: Path = typer.Option(
        Path("data/normalized/source_catalog.parquet"),
        "--observations",
        help="Parquet normalizado; será reconciliado se não tiver IDs canônicos.",
    ),
    output_dir: Path = typer.Option(Path("data/derived/article"), "--output-dir"),
    genre_claims: Path | None = typer.Option(None, "--genre-claims"),
    classifications: Path | None = typer.Option(None, "--classifications"),
    video_observations: Path | None = typer.Option(None, "--video-observations"),
    resolved_video_links: Path | None = typer.Option(None, "--resolved-video-links"),
) -> None:
    """Materialize datasets for persistence, genre, content, and article analysis."""
    if not observations.is_file():
        raise typer.BadParameter(f"observation file not found: {observations}")
    raw_scan = pl.scan_parquet(observations)
    raw_columns = raw_scan.collect_schema().names()
    source_scan = (
        raw_scan
        if {"market_code", "chart_family", "canonical_track_id"}.issubset(raw_columns)
        else scan_source_catalog([observations])
    )
    needs_lazy_resolution = "canonical_track_id" not in raw_columns
    if not needs_lazy_resolution:
        needs_lazy_resolution = (
            source_scan.filter(pl.col("canonical_track_id").is_not_null()).limit(1).collect().is_empty()
        )
    if needs_lazy_resolution:
        source_scan = canonicalize_catalog_lazy(source_scan)
    frame = source_scan.select(
        [
            column
            for column in (
                "source_observation_key",
                "provider",
                "origin_platform",
                "item_kind",
                "market_code",
                "chart_family",
                "period_start",
                "period_end",
                "rank",
                "native_id",
                "metric_type",
                "metric_value",
                "canonical_track_id",
            )
            if column in source_scan.collect_schema().names()
        ]
    ).collect(engine="streaming")
    conflict_rows = None
    claims = pl.read_parquet(genre_claims) if genre_claims is not None else None
    if claims is not None and "canonical_track_id" in claims.columns:
        claims = claims.with_columns(
            pl.col("canonical_track_id")
            .map_elements(canonical_track_reference, return_dtype=pl.String)
            .alias("canonical_track_id")
        )
    videos = (
        pl.scan_parquet(video_observations).collect(engine="streaming")
        if video_observations is not None and video_observations.is_file()
        else None
    )
    links = (
        pl.scan_parquet(resolved_video_links).collect(engine="streaming")
        if resolved_video_links is not None and resolved_video_links.is_file()
        else None
    )
    records = []
    if classifications is not None and classifications.is_file():
        records = JsonClassificationRepository(classifications, TAXONOMY_VERSION).list_all()
        records = [
            replace(record, canonical_track_id=canonical_track_reference(record.canonical_track_id))
            for record in records
        ]
    paths = write_article_datasets(
        frame,
        output_dir,
        genre_claims=claims,
        classifications=records,
        video_observations=videos,
        resolved_video_links=links,
    )
    output_rows = {
        name: pl.scan_parquet(path).select(pl.len()).collect().item()
        for name, path in paths.items()
    }
    manifest = {
        "schema_version": "article-analytics-v1",
        "resolution": "EXACT_ID_ONLY_LAZY",
        "input": {"path": str(observations), "sha256": _file_sha256(observations)},
        "parameters": {
            "genre_claims": str(genre_claims) if genre_claims is not None else None,
            "classifications": str(classifications) if classifications is not None else None,
            "video_observations": (
                str(video_observations) if video_observations is not None else None
            ),
            "resolved_video_links": (
                str(resolved_video_links) if resolved_video_links is not None else None
            ),
        },
        "outputs": {
            name: {"path": str(path), "sha256": _file_sha256(path), "rows": output_rows[name]}
            for name, path in paths.items()
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    typer.echo(
        json.dumps(
            {
                "status": "MATERIALIZED",
                "input": str(observations),
                "input_rows": frame.height,
                "conflicts": conflict_rows,
                "resolution": "EXACT_ID_ONLY_LAZY",
                "outputs": {name: str(path) for name, path in paths.items()},
                "output_rows": output_rows,
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
        )
    )


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@corpus_app.command("freeze")
def corpus_freeze(
    database_url: str | None = typer.Option(None, envvar="CHART_OBSERVATORY_DATABASE_URL"),
    coverage_path: Path = typer.Option(Path("data/derived/mgd_coverage.parquet"), "--coverage"),
    name: str = typer.Option("CANONICAL_CORPUS"),
    version: str = typer.Option("v1"),
) -> None:
    """Freeze the observed database inputs and eligible chart cells as a manifest."""
    settings = Settings.load(Path.cwd())
    service = ResearchApplication(
        Path("data/runtime"), database_url=database_url or settings.database_url
    )
    coverage = __import__("polars").read_parquet(coverage_path)
    eligible = coverage.filter(__import__("polars").col("eligible"))
    if eligible.height == 0:
        raise typer.BadParameter("coverage file contains no eligible cells")
    start = min(value for value in eligible["first_date"].to_list() if value is not None)
    end = max(value for value in eligible["last_date"].to_list() if value is not None)
    memberships = tuple(
        {
            "member_type": "CHART_CELL",
            "member_key": (
                f"{row['provider']}/{row['platform_code']}/"
                f"{row['country_code']}/{row['chart_family']}"
            ),
            "provider": row["provider"],
            "platform_code": row["platform_code"],
            "country_code": row["country_code"],
            "chart_family": row["chart_family"],
            "period_start": row["first_date"],
            "period_end": row["last_date"],
            "eligible": bool(row["eligible"]),
            "reason": row["reasons"] or None,
        }
        for row in eligible.iter_rows(named=True)
    )
    snapshot_ids = tuple(str(value) for (value,) in service.session.query(ChartSnapshot.id).all())
    frozen = freeze_corpus(
        service.session,
        CorpusFreezeRequest(
            name,
            version,
            {
                "minimum_coverage": settings.comparable_corpus.minimum_coverage,
                "minimum_years": settings.comparable_corpus.minimum_years,
                "minimum_chart_depth": settings.comparable_corpus.minimum_chart_depth,
            },
            snapshot_ids,
            start,
            end,
            memberships,
        ),
    )
    service.session.commit()
    typer.echo(
        json.dumps(
            {
                "status": "FROZEN",
                "corpus_version_id": str(frozen.id),
                "manifest_sha256": frozen.manifest_sha256,
            }
        )
    )


@corpus_app.command("freeze-source")
def corpus_freeze_source(
    input_path: Path = typer.Option(Path("data/normalized/mgd_observations.parquet"), "--input"),
    coverage_path: Path = typer.Option(Path("data/derived/mgd_coverage.parquet"), "--coverage"),
    output: Path = typer.Option(Path("data/derived/corpus_v1_source_manifest.json")),
    datasets_dir: Path = typer.Option(Path("data/derived"), "--datasets-dir"),
) -> None:
    """Freeze source files and analytical artifacts before PostgreSQL membership freeze."""
    settings = Settings.load(Path.cwd())
    datasets = tuple(
        path
        for path in sorted(datasets_dir.glob("*.parquet"))
        if path.name not in {coverage_path.name, "mgd_balanced_panel.parquet"}
    )
    manifest = freeze_source_artifacts(
        input_path,
        coverage_path,
        output,
        analytical_datasets=datasets,
        rules=EligibilityRules(
            minimum_coverage=settings.comparable_corpus.minimum_coverage,
            minimum_years=settings.comparable_corpus.minimum_years,
            minimum_chart_depth=settings.comparable_corpus.minimum_chart_depth,
            minimum_source_quality=settings.comparable_corpus.minimum_source_quality,
        ),
    )
    typer.echo(
        json.dumps(
            {
                "status": manifest["status"],
                "manifest_sha256": manifest["manifest_sha256"],
                "eligible_cells": manifest["eligible_cells"],
                "output": str(output),
            }
        )
    )


@corpus_app.command("ingest-lyrics")
def corpus_ingest_lyrics(
    input_path: Path,
    database_url: str | None = typer.Option(None, envvar="CHART_OBSERVATORY_DATABASE_URL"),
) -> None:
    """Import authorized lyric documents and review/LLM annotation JSONL."""
    settings = Settings.load(Path.cwd())
    service = ResearchApplication(
        Path("data/runtime"), database_url=database_url or settings.database_url
    )
    documents = annotations = 0
    for line_number, line in enumerate(
        input_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            retrieved_at = payload.get("retrieved_at")
            document = ingest_lyric_document(
                service.session,
                LyricDocumentInput(
                    canonical_track_id=UUID(str(payload["canonical_track_id"])),
                    source=str(payload["source"]),
                    source_version=str(payload["source_version"]),
                    rights_status=str(payload["rights_status"]),
                    language_code=payload.get("language_code"),
                    text=payload.get("text"),
                    retrieved_at=(
                        datetime.fromisoformat(str(retrieved_at))
                        if retrieved_at
                        else datetime.now(UTC)
                    ),
                    metadata=dict(payload.get("metadata", {})),
                ),
            )
            new_annotations = annotate_document(
                service.session,
                document.id,
                [annotation_input_from_dict(value) for value in payload.get("annotations", [])],
            )
            documents += 1
            annotations += len(new_annotations)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            service.session.rollback()
            raise typer.BadParameter(
                f"invalid lyric JSONL at line {line_number}: {error}"
            ) from error
    service.session.commit()
    typer.echo(
        json.dumps({"status": "IMPORTED", "documents": documents, "annotations": annotations})
    )


@corpus_app.command("gemini-analyze")
def corpus_gemini_analyze(
    tracks: Path = typer.Option(
        Path("data/derived/track_master.parquet"),
        "--tracks",
        help="Parquet with canonical_track_id, title and artist_names.",
    ),
    output: Path = typer.Option(
        Path("data/derived/lyrics/gemini_annotations.jsonl"),
        "--output",
        help="Append-only JSONL output; completed song IDs are skipped on reruns.",
    ),
    model: str = typer.Option("gemini-3.8-flash", help="Gemini model name."),
    limit: int | None = typer.Option(None, min=1, help="Optional bounded run for a smoke test."),
    delay: float = typer.Option(0.35, min=0.0, help="Delay between sequential provider requests."),
) -> None:
    """Fetch original lyrics and ask Gemini for an English translation plus annotations."""
    settings = Settings.load(Path.cwd())
    if not settings.gemini_api_key:
        raise typer.BadParameter("Set GEMINI in .env before running this command.")
    if not tracks.exists():
        raise typer.BadParameter(f"Track file does not exist: {tracks}")

    table = pl.read_parquet(tracks)
    required = {"canonical_track_id", "title", "artist_names"}
    missing = required.difference(table.columns)
    if missing:
        raise typer.BadParameter(f"Track file is missing columns: {', '.join(sorted(missing))}")
    completed = existing_song_ids(output)
    lrclib = LrclibClient()
    lyrics_ovh = LyricsOvhClient()
    gemini = GeminiAnnotationClient(settings.gemini_api_key, model=model)
    processed = skipped = missing_lyrics = analyzed = failed = 0
    rows = table.iter_rows(named=True)
    for row in rows:
        if limit is not None and processed >= limit:
            break
        song_id = str(row["canonical_track_id"])
        if song_id in completed:
            skipped += 1
            continue
        title = str(row["title"])
        artists_value = row["artist_names"]
        if isinstance(artists_value, (list, tuple)):
            artist = ", ".join(str(value) for value in artists_value)
        else:
            artist = str(artists_value)
        lyrics: str | None = None
        source = None
        source_metadata: dict[str, Any] = {}
        try:
            lrclib_result = lrclib.fetch(title, artist)
            if lrclib_result is not None:
                lyrics, source_metadata = lrclib_result
                source = "LRCLIB"
            else:
                throttle(delay)
                lyrics = lyrics_ovh.fetch(title, artist)
                source = "LYRICS_OVH" if lyrics else None
            if lyrics is None:
                append_jsonl(
                    output,
                    {
                        "song_id": song_id,
                        "title": title,
                        "artist": artist,
                        "lyrics_status": "MISSING",
                        "lyrics_source": None,
                        "gemini_model": model,
                    },
                )
                missing_lyrics += 1
            else:
                analysis = gemini.annotate(song_id, title, artist, lyrics)
                append_jsonl(
                    output,
                    {
                        "song_id": song_id,
                        "title": title,
                        "artist": artist,
                        "lyrics_status": "FOUND",
                        "lyrics_source": source,
                        "source_metadata": source_metadata,
                        "original_lyrics": lyrics,
                        "gemini_model": model,
                        "analysis": analysis,
                    },
                )
                analyzed += 1
        except GeminiApiError as error:
            append_jsonl(
                output,
                {
                    "song_id": song_id,
                    "title": title,
                    "artist": artist,
                    "lyrics_status": "GEMINI_ERROR",
                    "lyrics_source": source,
                    "gemini_model": model,
                    "error": str(error),
                },
            )
            failed += 1
        except (httpx.HTTPError, TimeoutError, OSError) as error:
            append_jsonl(
                output,
                {
                    "song_id": song_id,
                    "title": title,
                    "artist": artist,
                    "lyrics_status": "PROVIDER_ERROR",
                    "lyrics_source": source,
                    "gemini_model": model,
                    "error": type(error).__name__,
                },
            )
            failed += 1
        processed += 1
        throttle(delay)
    typer.echo(
        json.dumps(
            {
                "status": "COMPLETED",
                "processed": processed,
                "skipped_existing": skipped,
                "analyzed": analyzed,
                "missing_lyrics": missing_lyrics,
                "failed": failed,
                "output": str(output),
            }
        )
    )


@collect_app.command("current")
def collect_current(
    source: str = typer.Option(...),
    country: str = typer.Option(...),
    chart: str = typer.Option(...),
) -> None:
    try:
        AdapterRegistry.with_disabled_network_sources().get_enabled(
            source, RightsOperation.FETCH, datetime.now(UTC)
        )
    except SourceDisabled as error:
        typer.echo(
            json.dumps(
                {
                    "status": "DENIED_OR_DISABLED",
                    "reason": str(error),
                    "source": source,
                    "country": country,
                    "chart": chart,
                }
            )
        )


@import_app.command("preview")
def import_preview(
    path: Path,
    schema: str = "manual_generic_v2",
    provider: str | None = typer.Option(None),
    origin_platform: str | None = typer.Option(None, "--platform"),
    chart_family: str | None = typer.Option(None, "--chart-family"),
    native_frequency: str | None = typer.Option(None, "--frequency"),
    metric_type: str | None = typer.Option(None, "--metric-type"),
) -> None:
    metadata = _import_metadata(
        provider, origin_platform, chart_family, native_frequency, metric_type
    )
    typer.echo(json.dumps(_service().preview_import(path, schema, metadata), default=str))


@import_app.command("apply")
def import_apply(
    path: Path,
    schema: str = "manual_generic_v2",
    authorize_local_file: bool = typer.Option(False, help="Explicitly authorize this local run"),
    provider: str | None = typer.Option(None),
    origin_platform: str | None = typer.Option(None, "--platform"),
    chart_family: str | None = typer.Option(None, "--chart-family"),
    native_frequency: str | None = typer.Option(None, "--frequency"),
    metric_type: str | None = typer.Option(None, "--metric-type"),
) -> None:
    service = _service(authorize_local_file)
    metadata = _import_metadata(
        provider, origin_platform, chart_family, native_frequency, metric_type
    )
    preview = service.preview_import(path, schema, metadata)
    typer.echo(json.dumps(service.apply_import(str(preview["token"])), default=str))


def _import_metadata(
    provider: str | None,
    origin_platform: str | None,
    chart_family: str | None,
    native_frequency: str | None,
    metric_type: str | None,
) -> ImportMetadata | None:
    values = (provider, origin_platform, chart_family, native_frequency, metric_type)
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise typer.BadParameter(
            "provider, --platform, --chart-family, --frequency, and --metric-type "
            "are required together"
        )
    return ImportMetadata(
        provider=provider or "",
        origin_platform=origin_platform or "",
        chart_family=chart_family or "",
        native_frequency=native_frequency or "",
        metric_type=metric_type or "",
    )


def _chartmetric_streaming_type(platform: str) -> str:
    return {
        "spotify": "spotify_track",
        "applemusic": "apple_music_track",
        "youtube": "youtube",
        "amazon": "amazon",
    }.get(platform.casefold(), platform.casefold())


@coverage_app.command("show")
def coverage_show(country: str | None = None) -> None:
    typer.echo(json.dumps(_service().coverage(country)))


@metrics_app.command("summarize")
def metrics_summarize(country: str | None = None) -> None:
    typer.echo(json.dumps(_service().rankings(country)))


@export_app.command("create")
def export_create(
    dataset: str, format: str = "parquet", authorize_local_file: bool = typer.Option(False)
) -> None:
    typer.echo(json.dumps(_service(authorize_local_file).export(dataset, format)))


@procurement_app.command("profile-sample")
def procurement_profile_sample(path: Path) -> None:
    """Inspect a vendor sample without importing or retaining its row values."""
    typer.echo(json.dumps(profile_sample(path).as_dict(), sort_keys=True))


@mgd_app.command("inspect")
def sources_mgd_inspect(
    root: Path = typer.Option(Path("mgd"), exists=False, file_okay=False),
    manifest_output: Path = typer.Option(Path("research/mgd_source_manifest.json")),
) -> None:
    """Inventory every local MGD chart file without importing rows."""
    source = MGDSource(root)
    manifests = source.inspect()
    source.write_manifest(manifest_output)
    typer.echo(json.dumps([asdict(manifest) for manifest in manifests], default=str))


@mgd_app.command("import")
def sources_mgd_import(
    root: Path = typer.Option(Path("mgd"), exists=False, file_okay=False),
    output: Path = typer.Option(Path("data/normalized/mgd_observations.parquet")),
    countries: str | None = typer.Option(None, help="Comma-separated ISO codes."),
    from_date: str | None = typer.Option(None, "--from"),
    to_date: str | None = typer.Option(None, "--to"),
    chart: str | None = typer.Option(None),
) -> None:
    """Stream MGD chart rows into a normalized Parquet corpus."""
    from datetime import date

    selected = {value.strip().upper() for value in countries.split(",")} if countries else None
    summary = MGDSource(root).import_to(
        output,
        countries=selected,
        from_date=date.fromisoformat(from_date) if from_date else None,
        to_date=date.fromisoformat(to_date) if to_date else None,
        chart=chart,
    )
    typer.echo(json.dumps(asdict(summary), default=str))


@mgd_app.command("report")
def sources_mgd_report(
    observations: Path = typer.Option(Path("data/normalized/mgd_observations.parquet")),
    output: Path = typer.Option(Path("research/mgd_artist_year_rankings.csv")),
    latest_years: int = typer.Option(5, min=1),
) -> None:
    summary = write_artist_year_report_from_parquet(observations, output, latest_years)
    typer.echo(json.dumps(asdict(summary), default=str))


@mgd_app.command("top-artists")
def sources_mgd_top_artists(
    report: Path = typer.Option(Path("research/mgd_artist_year_rankings.csv")),
    output: Path = typer.Option(Path("research/top_artists_by_country_latest5.csv")),
    top_n: int = typer.Option(25, min=1),
) -> None:
    summary = write_top_artist_list(report, output, top_n)
    typer.echo(json.dumps(asdict(summary), default=str))


@sources_app.command("coverage")
def sources_coverage(
    manifest: Path = typer.Option(Path("research/mgd_source_manifest.json")),
    output_dir: Path = typer.Option(Path("research")),
) -> None:
    from chart_observatory.sources.models import MarketCapability, SourceManifest, SourceStatus

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifests = tuple(
        SourceManifest(
            provider=item["provider"],
            origin_platform=item["origin_platform"],
            filename=item["filename"],
            path=Path(item["path"]),
            sha256=item["sha256"],
            size_bytes=int(item["size_bytes"]),
            row_count=int(item["row_count"]),
            schema_version=item["schema_version"],
            status=SourceStatus(item["status"]),
            countries=tuple(item.get("countries", [])),
            chart_types=tuple(item.get("chart_types", [])),
            earliest_date=(
                date.fromisoformat(item["earliest_date"]) if item.get("earliest_date") else None
            ),
            latest_date=(
                date.fromisoformat(item["latest_date"]) if item.get("latest_date") else None
            ),
            number_of_tracks=item.get("number_of_tracks"),
            number_of_observations=item.get("number_of_observations"),
            missing_periods=item.get("missing_periods"),
            parser_version=item.get("parser_version", "1"),
        )
        for item in payload.get("files", [])
    )
    path = write_global_market_coverage(manifests, output_dir)
    capabilities: list[MarketCapability] = []
    chartmetric_path = output_dir / "chartmetric_capabilities.json"
    if chartmetric_path.exists():
        capabilities.extend(
            MarketCapability(**item)
            for item in json.loads(chartmetric_path.read_text(encoding="utf-8"))
        )
    youtube_path = output_dir / "youtube_regions.json"
    if youtube_path.exists():
        youtube = json.loads(youtube_path.read_text(encoding="utf-8"))
        capabilities.extend(
            MarketCapability(
                provider="YOUTUBE_DATA_API",
                origin_platform="YOUTUBE_VIDEO",
                country_code=item["code"],
                country_name=item["name"],
                chart_types=("mostPopular",),
                native_frequency="SNAPSHOT",
            )
            for item in youtube.get("regions", [])
        )
    capabilities.append(
        MarketCapability(
            provider="PRO_MUSICA_BRASIL",
            origin_platform="MULTI_PLATFORM_AGGREGATE",
            country_code="BR",
            country_name="Brazil",
            chart_types=("top50_streaming",),
            ranking_depth=50,
        )
    )
    inventory = write_market_capability_inventory(
        manifests, capabilities, output_dir / "market_capabilities.csv"
    )
    typer.echo(json.dumps({"output": str(path), "market_capabilities": str(inventory)}))


@kaggle_app.command("download")
def sources_kaggle_download(
    root: Path = typer.Option(Path("data/raw/kaggle/spotify-charts")),
    allow_network: bool = typer.Option(
        False,
        help="Opt in to the external Kaggle download; cached local imports need no network.",
    ),
) -> None:
    if not allow_network:
        typer.echo(json.dumps({"status": "NETWORK_DISABLED", "provider": "KAGGLE_DHRUVILDAVE"}))
        return
    path = KaggleSpotifyChartsSource(root).download()
    typer.echo(json.dumps({"status": "DOWNLOADED", "path": str(path)}))


@kaggle_app.command("import")
def sources_kaggle_import(
    root: Path = typer.Option(Path("data/raw/kaggle/spotify-charts")),
    output: Path = typer.Option(Path("data/normalized/kaggle_spotify_observations.parquet")),
    chart: str | None = typer.Option(None),
    top_n: int = typer.Option(100, min=1, max=200),
) -> None:
    summary = KaggleSpotifyChartsSource(root).import_to(output, chart=chart, top_n=top_n)
    typer.echo(json.dumps(asdict(summary), default=str))


@chartmetric_app.command("auth-test")
def sources_chartmetric_auth_test(
    allow_network: bool = typer.Option(
        False,
        help="Opt in to one bounded authenticated token exchange.",
    ),
) -> None:
    settings = Settings.load(Path.cwd())
    if not settings.chartmetric_refresh_token or not settings.chartmetric_refresh_token.strip():
        typer.echo(json.dumps({"status": "NOT_CONFIGURED", "provider": "CHARTMETRIC"}))
        return
    if not allow_network:
        typer.echo(json.dumps({"status": "NETWORK_DISABLED", "provider": "CHARTMETRIC"}))
        return
    transport = HttpxTransport("https://api.chartmetric.com")
    try:
        token = ChartmetricClient(
            settings.chartmetric_refresh_token, transport=transport
        ).access_token()
        typer.echo(
            json.dumps(
                {"status": "AUTHENTICATED", "provider": "CHARTMETRIC", "token_cached": bool(token)}
            )
        )
    except ChartmetricError as error:
        typer.echo(
            json.dumps(
                {
                    "status": "AUTH_FAILED",
                    "provider": "CHARTMETRIC",
                    "status_code": error.status_code,
                }
            )
        )
    finally:
        transport.close()


@chartmetric_app.command("discover")
def sources_chartmetric_discover(
    allow_network: bool = typer.Option(
        False,
        help="Opt in to bounded authenticated capability discovery.",
    ),
) -> None:
    settings = Settings.load(Path.cwd())
    if not settings.chartmetric_refresh_token or not settings.chartmetric_refresh_token.strip():
        typer.echo(json.dumps({"status": "NOT_CONFIGURED", "provider": "CHARTMETRIC"}))
        return
    if not allow_network:
        typer.echo(json.dumps({"status": "NETWORK_DISABLED", "provider": "CHARTMETRIC"}))
        return
    transport = HttpxTransport("https://api.chartmetric.com")
    try:
        capabilities = ChartmetricClient(
            settings.chartmetric_refresh_token, transport=transport
        ).discover_capabilities()
        output = Path("research/chartmetric_capabilities.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps([asdict(capability) for capability in capabilities], default=str, indent=2)
            + "\n",
            encoding="utf-8",
        )
        typer.echo(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "provider": "CHARTMETRIC",
                    "capabilities": len(capabilities),
                    "output": str(output),
                }
            )
        )
    except ChartmetricError as error:
        typer.echo(
            json.dumps(
                {"status": "FAILED", "provider": "CHARTMETRIC", "status_code": error.status_code}
            )
        )
    finally:
        transport.close()


@chartmetric_app.command("dates")
def sources_chartmetric_dates(
    streaming_type: str = typer.Option(
        ..., help="Chartmetric streaming type, for example spotify_track."
    ),
    from_days_ago: int = typer.Option(
        28, min=1, max=9999, help="Provider look-back window in days; 9999 means all history."
    ),
    all_history: bool = typer.Option(
        False, "--all-history", help="Request all provider-supported dates (fromDaysAgo=9999)."
    ),
    chart_entity: str | None = typer.Option(None),
    chart_type: str | None = typer.Option(None),
    duration: str | None = typer.Option(None),
    country: str | None = typer.Option(None),
    genre: str | None = typer.Option(None),
    allow_network: bool = typer.Option(
        False,
        help="Opt in to one bounded authenticated dates request.",
    ),
) -> None:
    """List provider-supported dates without collecting chart rows."""
    settings = Settings.load(Path.cwd())
    if not settings.chartmetric_refresh_token or not settings.chartmetric_refresh_token.strip():
        typer.echo(json.dumps({"status": "NOT_CONFIGURED", "provider": "CHARTMETRIC"}))
        return
    if not allow_network:
        typer.echo(json.dumps({"status": "NETWORK_DISABLED", "provider": "CHARTMETRIC"}))
        return
    transport = HttpxTransport("https://api.chartmetric.com")
    try:
        dates = ChartmetricClient(
            settings.chartmetric_refresh_token, transport=transport
        ).chart_dates(
            streaming_type,
            from_days_ago=9999 if all_history else from_days_ago,
            chart_entity=chart_entity,
            chart_type=chart_type,
            duration=duration,
            country=country,
            genre=genre,
        )
        typer.echo(
            json.dumps(
                {
                    "status": "DATES_DISCOVERED",
                    "provider": "CHARTMETRIC",
                    "streaming_type": streaming_type,
                    "count": len(dates),
                    "dates": [value.isoformat() for value in dates],
                }
            )
        )
    except ChartmetricError as error:
        typer.echo(
            json.dumps(
                {"status": "FAILED", "provider": "CHARTMETRIC", "status_code": error.status_code}
            )
        )
    finally:
        transport.close()


@chartmetric_app.command("platforms")
def sources_chartmetric_platforms(
    allow_network: bool = typer.Option(
        False, help="Opt in to authenticated platform and market discovery."
    ),
) -> None:
    """Discover platforms with chart capabilities available to this account."""
    settings = Settings.load(Path.cwd())
    if not settings.chartmetric_refresh_token or not settings.chartmetric_refresh_token.strip():
        typer.echo(json.dumps({"status": "NOT_CONFIGURED", "provider": "CHARTMETRIC"}))
        return
    if not allow_network:
        typer.echo(json.dumps({"status": "NETWORK_DISABLED", "provider": "CHARTMETRIC"}))
        return
    transport = HttpxTransport("https://api.chartmetric.com")
    try:
        capabilities = ChartmetricClient(
            settings.chartmetric_refresh_token, transport=transport
        ).discover_capabilities(
            platforms=("spotify", "applemusic", "youtube", "amazon")
        )
        platforms = sorted(
            {
                capability.origin_platform
                for capability in capabilities
                if capability.available
            }
        )
        typer.echo(
            json.dumps(
                {"status": "DISCOVERED", "provider": "CHARTMETRIC", "platforms": platforms}
            )
        )
    except ChartmetricError as error:
        typer.echo(
            json.dumps(
                {"status": "FAILED", "provider": "CHARTMETRIC", "status_code": error.status_code}
            )
        )
    finally:
        transport.close()


@chartmetric_app.command("markets")
def sources_chartmetric_markets(
    platform: str = typer.Option(..., help="Chartmetric origin platform."),
    allow_network: bool = typer.Option(
        False, help="Opt in to authenticated market discovery."
    ),
) -> None:
    """List markets available for one Chartmetric origin platform."""
    settings = Settings.load(Path.cwd())
    if not settings.chartmetric_refresh_token or not settings.chartmetric_refresh_token.strip():
        typer.echo(json.dumps({"status": "NOT_CONFIGURED", "provider": "CHARTMETRIC"}))
        return
    if not allow_network:
        typer.echo(json.dumps({"status": "NETWORK_DISABLED", "provider": "CHARTMETRIC"}))
        return
    transport = HttpxTransport("https://api.chartmetric.com")
    try:
        capabilities = ChartmetricClient(
            settings.chartmetric_refresh_token, transport=transport
        ).discover_capabilities(platforms=(platform,))
        markets = sorted(
            {
                capability.country_code
                for capability in capabilities
                if capability.available and capability.origin_platform == platform.upper()
            }
        )
        typer.echo(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "provider": "CHARTMETRIC",
                    "platform": platform.upper(),
                    "markets": markets,
                }
            )
        )
    except ChartmetricError as error:
        typer.echo(
            json.dumps(
                {"status": "FAILED", "provider": "CHARTMETRIC", "status_code": error.status_code}
            )
        )
    finally:
        transport.close()


@chartmetric_app.command("collect")
def sources_chartmetric_collect(
    platform: str = typer.Option(..., help="Origin platform, for example spotify."),
    country_code: str = typer.Option(..., help="ISO-3166 alpha-2 market code."),
    interval: str = typer.Option(..., help="Provider interval, for example daily."),
    chart_type: str = typer.Option(..., help="Provider chart type."),
    period: str = typer.Option(..., help="Native period date in YYYY-MM-DD format."),
    output: Path = typer.Option(Path("data/normalized/chartmetric_observations.parquet")),
    checkpoint: Path = typer.Option(Path("data/interim/chartmetric-checkpoint.json")),
    page_size: int = typer.Option(200, min=1, max=200),
    max_pages: int = typer.Option(1, min=1, max=100),
    allow_network: bool = typer.Option(
        False,
        help="Opt in to one bounded authenticated collection; no broad collection is performed.",
    ),
) -> None:
    """Collect one explicitly selected Chartmetric chart window."""
    settings = Settings.load(Path.cwd())
    if not settings.chartmetric_refresh_token or not settings.chartmetric_refresh_token.strip():
        typer.echo(json.dumps({"provider": "CHARTMETRIC", "status": "NOT_CONFIGURED"}))
        return
    if not allow_network:
        typer.echo(json.dumps({"provider": "CHARTMETRIC", "status": "NETWORK_DISABLED"}))
        return

    import polars as pl

    collection_period = date.fromisoformat(period)
    transport = HttpxTransport("https://api.chartmetric.com")
    try:
        rows = ChartmetricClient(
            settings.chartmetric_refresh_token, transport=transport
        ).collect_chart_pages(
            platform=platform,
            country_code=country_code,
            interval=interval,
            chart_type=chart_type,
            period=collection_period,
            page_size=page_size,
            checkpoint_path=checkpoint,
            max_pages=max_pages,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(
            [
                {key: value for key, value in asdict(row).items() if key != "raw_fields"}
                for row in rows
            ]
        ).write_parquet(output)
        typer.echo(
            json.dumps(
                {
                    "provider": "CHARTMETRIC",
                    "status": "COLLECTED",
                    "rows": len(rows),
                    "output": str(output),
                    "checkpoint": str(checkpoint),
                }
            )
        )
    except ChartmetricError as error:
        typer.echo(
            json.dumps(
                {
                    "provider": "CHARTMETRIC",
                    "status": "FAILED",
                    "status_code": error.status_code,
                }
            )
        )
    finally:
        transport.close()


@chartmetric_app.command("backfill")
def sources_chartmetric_backfill(
    platform: str = typer.Option(..., help="Origin platform, for example spotify."),
    countries: str = typer.Option(
        "discovered",
        help="Comma-separated ISO codes, or 'discovered' for available provider markets.",
    ),
    all_markets: bool = typer.Option(
        False, "--all-markets", help="Discover and collect every available market."
    ),
    interval: str = typer.Option(..., help="Provider interval, for example daily."),
    chart_type: str = typer.Option(..., help="Provider chart type."),
    from_date: str | None = typer.Option(
        None, "--from", help="Inclusive period in YYYY-MM-DD format."
    ),
    to_date: str | None = typer.Option(
        None, "--to", help="Inclusive period in YYYY-MM-DD format."
    ),
    all_dates: bool = typer.Option(
        False, "--all-dates", help="Discover provider-supported dates per market."
    ),
    streaming_type: str | None = typer.Option(
        None, help="Dates endpoint type; defaults to '<platform>_tracks'."
    ),
    from_days_ago: int = typer.Option(9999, min=1, max=9999),
    output_dir: Path = typer.Option(Path("data/normalized/chartmetric-backfill")),
    state_dir: Path = typer.Option(Path("data/interim/chartmetric-backfill")),
    output: Path = typer.Option(Path("data/normalized/chartmetric_observations.parquet")),
    page_size: int = typer.Option(200, min=1, max=200),
    resume: bool = typer.Option(True, "--resume/--no-resume"),
    allow_network: bool = typer.Option(
        False,
        help="Opt in to bounded collection for every planned market and period.",
    ),
) -> None:
    """Collect every selected Chartmetric market/period with resumable task state."""
    settings = Settings.load(Path.cwd())
    if not settings.chartmetric_refresh_token or not settings.chartmetric_refresh_token.strip():
        typer.echo(json.dumps({"provider": "CHARTMETRIC", "status": "NOT_CONFIGURED"}))
        return
    if not allow_network:
        typer.echo(json.dumps({"provider": "CHARTMETRIC", "status": "NETWORK_DISABLED"}))
        return
    transport = HttpxTransport("https://api.chartmetric.com")
    try:
        client = ChartmetricClient(settings.chartmetric_refresh_token, transport=transport)
        if all_markets or countries.casefold() == "discovered":
            capabilities = client.discover_capabilities(platforms=(platform,))
            selected_countries = tuple(
                sorted(
                    {
                        capability.country_code
                        for capability in capabilities
                        if capability.available and capability.origin_platform == platform.upper()
                    }
                )
            )
        else:
            selected_countries = tuple(
                sorted({value.strip().upper() for value in countries.split(",") if value.strip()})
            )
        if not selected_countries:
            typer.echo(
                json.dumps(
                    {
                        "status": "NO_MARKETS",
                        "provider": "CHARTMETRIC",
                        "platform": platform.upper(),
                    }
                )
            )
            return
        if (from_date is None) != (to_date is None):
            raise ValueError("--from and --to must be supplied together")
        if from_date is None or to_date is None:
            if not all_dates:
                raise ValueError("--from/--to are required unless --all-dates is used")
            start, end = date.min, date.max
        else:
            start = date.fromisoformat(from_date)
            end = date.fromisoformat(to_date)
        available_dates_by_country = None
        if all_dates:
            dates_type = streaming_type or _chartmetric_streaming_type(platform)
            try:
                available_dates_by_country = {
                    country: client.chart_dates(
                        dates_type,
                        from_days_ago=from_days_ago,
                        country=country,
                    )
                    for country in selected_countries
                }
            except ChartmetricError as error:
                typer.echo(
                    json.dumps(
                        {
                            "status": "DATES_UNAVAILABLE",
                            "provider": "CHARTMETRIC",
                            "platform": platform.upper(),
                            "streaming_type": dates_type,
                            "from_days_ago": from_days_ago,
                            "countries": len(selected_countries),
                            "status_code": error.status_code,
                            "hint": (
                                "The credential or account does not expose the provider date "
                                "catalog; use an explicit --from/--to window."
                            ),
                        }
                    )
                )
                return
            discovered_dates = [
                value
                for values in available_dates_by_country.values()
                for value in values
            ]
            if not discovered_dates:
                typer.echo(
                    json.dumps(
                        {
                            "status": "NO_DATES",
                            "provider": "CHARTMETRIC",
                            "platform": platform.upper(),
                        }
                    )
                )
                return
            if start == date.min:
                start = min(discovered_dates)
            if end == date.max:
                end = max(discovered_dates)
        summary = ChartmetricBackfillRunner(client, output_dir, state_dir).run(
            BackfillRequest(
                platform=platform,
                countries=selected_countries,
                interval=interval,
                chart_type=chart_type,
                start_date=start,
                end_date=end,
                page_size=page_size,
                available_dates_by_country=available_dates_by_country,
            ),
            resume=resume,
        )
        catalog_rows = consolidate_backfill_observations(output_dir, output)
        typer.echo(
            json.dumps(
                {
                    "status": "PARTIAL" if summary.failed_tasks else "COMPLETED",
                    "provider": "CHARTMETRIC",
                    "countries": len(selected_countries),
                    "output": str(output),
                    "catalog_rows": catalog_rows,
                    **asdict(summary),
                },
                default=str,
            )
        )
    except ValueError as error:
        typer.echo(
            json.dumps(
                {"status": "INVALID_WINDOW", "provider": "CHARTMETRIC", "error": str(error)}
            )
        )
    except ChartmetricError as error:
        typer.echo(
            json.dumps(
                {
                    "status": "FAILED",
                    "provider": "CHARTMETRIC",
                    "status_code": error.status_code,
                }
            )
        )
    finally:
        transport.close()


@promusica_app.command("discover")
def sources_promusica_discover(
    output: Path = typer.Option(Path("research/pro_musica_inventory.csv")),
    allow_network: bool = typer.Option(
        False,
        help="Opt in to public-domain discovery on the Pro-Música Brasil website.",
    ),
) -> None:
    if not allow_network:
        typer.echo(json.dumps({"status": "NETWORK_DISABLED", "provider": "PRO_MUSICA_BRASIL"}))
        return
    import httpx

    source = ProMusicaBrasilSource()
    response = httpx.get(source.base_url, timeout=30.0)
    response.raise_for_status()
    items = source.inventory_from_html(response.text)
    source.write_inventory(items, output)
    typer.echo(
        json.dumps(
            {
                "status": "DISCOVERED",
                "provider": source.provider,
                "items": len(items),
                "output": str(output),
            }
        )
    )


@youtube_app.command("discover")
def sources_youtube_discover(
    output: Path = typer.Option(Path("research/youtube_regions.json")),
    region: str | None = typer.Option(
        None, help="Also inspect assignable video categories for one region."
    ),
    allow_network: bool = typer.Option(
        False,
        help="Opt in to bounded official region/category discovery.",
    ),
) -> None:
    """Discover official YouTube regions; optionally inspect one region's categories."""
    settings = Settings.load(Path.cwd())
    if not settings.youtube_data_api_key:
        typer.echo(json.dumps({"status": "NOT_CONFIGURED", "provider": "YOUTUBE_DATA_API"}))
        return
    if not allow_network:
        typer.echo(json.dumps({"status": "NETWORK_DISABLED", "provider": "YOUTUBE_DATA_API"}))
        return
    transport = HttpxTransport("https://www.googleapis.com")
    try:
        discovery = YouTubeMarketDiscovery(settings.youtube_data_api_key, transport)
        regions = discovery.discover_regions()
        payload: dict[str, object] = {
            "provider": "YOUTUBE_DATA_API",
            "endpoint": "i18nRegions.list",
            "regions": [asdict(item) for item in regions],
        }
        if region:
            categories = discovery.discover_categories(region.upper())
            payload["categories"] = [asdict(item) for item in categories]
            payload["category_region"] = region.upper()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        categories_value = payload.get("categories")
        category_count = len(categories_value) if isinstance(categories_value, list) else 0
        typer.echo(
            json.dumps(
                {
                    "status": "DISCOVERED",
                    "provider": "YOUTUBE_DATA_API",
                    "regions": len(regions),
                    "categories": category_count,
                    "output": str(output),
                }
            )
        )
    except RuntimeError as error:
        typer.echo(
            json.dumps({"status": "FAILED", "provider": "YOUTUBE_DATA_API", "error": str(error)})
        )
    finally:
        transport.close()


@youtube_app.command("collect-current")
def sources_youtube_collect_current(
    regions_file: Path = typer.Option(Path("research/youtube_regions.json"), "--regions-file"),
    region: str | None = typer.Option(
        None, help="Comma-separated region codes; defaults to all discovered regions."
    ),
    category_id: str = typer.Option("10", help="YouTube video category; 10 is Music."),
    output: Path = typer.Option(Path("data/normalized/youtube_video_most_popular.parquet")),
    raw_root: Path = typer.Option(Path("data/raw/youtube_data")),
    failure_output: Path = typer.Option(Path("research/youtube_collection_failures.json")),
    allow_network: bool = typer.Option(
        False,
        help="Opt in to current YouTube Data API video collection.",
    ),
) -> None:
    """Collect current YouTube Video Most Popular rankings, never YouTube Music charts."""
    settings = Settings.load(Path.cwd())
    if not settings.youtube_data_api_key:
        typer.echo(json.dumps({"status": "NOT_CONFIGURED", "provider": "YOUTUBE_DATA_API"}))
        return
    if not allow_network:
        typer.echo(json.dumps({"status": "NETWORK_DISABLED", "provider": "YOUTUBE_DATA_API"}))
        return

    transport = HttpxTransport("https://www.googleapis.com")
    source_id = uuid4()
    occurred_at = datetime.now(UTC)
    profile = RightsProfile(
        source_id=source_id,
        status=RightsProfileStatus.APPROVED,
        valid_from=occurred_at - timedelta(minutes=1),
        valid_until=None,
        grants=(RightsGrant(uuid4(), RightsOperation.FETCH, True),),
        id=uuid4(),
    )
    try:
        if region:
            regions = tuple(value.strip().upper() for value in region.split(",") if value.strip())
        else:
            if not regions_file.exists():
                discovery = YouTubeMarketDiscovery(settings.youtube_data_api_key, transport)
                discovered = discovery.discover_regions()
                regions = tuple(item.code for item in discovered)
            else:
                payload = json.loads(regions_file.read_text(encoding="utf-8"))
                regions = tuple(item["code"] for item in payload.get("regions", []))
        source = YouTubeMostPopularSource(
            source_id,
            transport=transport,
            network_enabled=True,
            rights_gate=RightsGate(InMemoryRightsRepository([profile])),
            api_key_provider=_ConfiguredYouTubeKey(settings.youtube_data_api_key),
        )
        summary = collect_youtube_current(
            source,
            regions,
            category_id=category_id,
            observed_at=occurred_at,
            output=output,
            raw_root=raw_root,
            failure_output=failure_output,
        )
        typer.echo(json.dumps(asdict(summary), default=str))
    finally:
        transport.close()


@promusica_app.command("collect-current")
def sources_promusica_collect_current(
    output: Path = typer.Option(Path("research/promusica_top50_current.csv")),
    raw_root: Path = typer.Option(Path("data/raw/pro_musica")),
    allow_network: bool = typer.Option(
        False,
        help="Opt in to one bounded public current-chart request.",
    ),
) -> None:
    if not allow_network:
        typer.echo(json.dumps({"status": "NETWORK_DISABLED", "provider": "PRO_MUSICA_BRASIL"}))
        return
    import csv
    from datetime import date

    import httpx

    from chart_observatory.sources.promusica import ProMusicaHtmlParser, period_from_html

    source = ProMusicaBrasilSource()
    response = httpx.get(f"{source.base_url}home-2/top-50-streaming/", timeout=30.0)
    response.raise_for_status()
    retrieved_at = datetime.now(UTC)
    raw_path = source.store_artifact(response.content, str(response.url), raw_root, retrieved_at)
    period = period_from_html(response.text, date(retrieved_at.year, retrieved_at.month, 1))
    rows = ProMusicaHtmlParser().parse(
        response.text,
        period=period,
        source_document=str(raw_path),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "provider",
        "origin_platform",
        "country_code",
        "chart_name",
        "period_start",
        "rank",
        "track_title",
        "artist",
        "source_artifact",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "provider": row.provider,
                    "origin_platform": row.origin_platform,
                    "country_code": row.country_code,
                    "chart_name": row.chart_name,
                    "period_start": row.period_start,
                    "rank": row.rank,
                    "track_title": row.track_title,
                    "artist": row.artist,
                    "source_artifact": row.source_artifact,
                }
            )
    typer.echo(
        json.dumps(
            {
                "status": "IMPORTED",
                "rows": len(rows),
                "raw_artifact": str(raw_path),
                "output": str(output),
            }
        )
    )


if __name__ == "__main__":
    app()
