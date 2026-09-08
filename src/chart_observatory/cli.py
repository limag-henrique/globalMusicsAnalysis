# ruff: noqa: B008

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

import typer

from chart_observatory.application import ResearchApplication
from chart_observatory.charts.registry import AdapterRegistry
from chart_observatory.config import Settings
from chart_observatory.corpus.eligibility import EligibilityRules
from chart_observatory.corpus.freeze import freeze_source_artifacts
from chart_observatory.corpus.repository import (
    CorpusFreezeRequest,
    freeze_corpus,
    reconcile_entries,
)
from chart_observatory.db.models.charts import ChartSnapshot
from chart_observatory.domain.enums import RightsOperation
from chart_observatory.domain.errors import SourceDisabled
from chart_observatory.exports.analytical import write_mgd_analytical_datasets
from chart_observatory.ingestion.corpus import ingest_mgd_parquet, write_mgd_coverage
from chart_observatory.procurement.schema_profiler import profile_sample
from chart_observatory.sources.chartmetric import ChartmetricClient, ChartmetricError
from chart_observatory.sources.chartmetric_backfill import (
    BackfillRequest,
    ChartmetricBackfillRunner,
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
    typer.echo(
        json.dumps(
            {
                "status": "PROFILED",
                "cells": frame.height,
                "eligible_cells": int(frame.filter(frame["eligible"] == True).height),  # noqa: E712
                "output": str(output),
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
                "eligible_cells": sum(result.eligible for result in summary.profiles),
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
    dataset_names = (
        "track_master.parquet",
        "turnover_by_market_period.parquet",
        "genre_claims.parquet",
        "genre_diversity_by_market_period.parquet",
    )
    datasets = tuple(
        datasets_dir / name for name in dataset_names if (datasets_dir / name).is_file()
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
def import_preview(path: Path, schema: str = "manual_generic_v1") -> None:
    typer.echo(json.dumps(_service().preview_import(path, schema), default=str))


@import_app.command("apply")
def import_apply(
    path: Path,
    schema: str = "manual_generic_v1",
    authorize_local_file: bool = typer.Option(False, help="Explicitly authorize this local run"),
) -> None:
    service = _service(authorize_local_file)
    preview = service.preview_import(path, schema)
    typer.echo(json.dumps(service.apply_import(str(preview["token"])), default=str))


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
) -> None:
    summary = KaggleSpotifyChartsSource(root).import_to(output, chart=chart)
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
        ..., help="Chartmetric streaming type, for example spotify_tracks."
    ),
    from_days_ago: int = typer.Option(
        28, min=1, max=28, help="Bounded look-back window in days (API maximum: 28)."
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
            from_days_ago=from_days_ago,
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
    interval: str = typer.Option(..., help="Provider interval, for example daily."),
    chart_type: str = typer.Option(..., help="Provider chart type."),
    from_date: str = typer.Option(..., "--from", help="Inclusive period in YYYY-MM-DD format."),
    to_date: str = typer.Option(..., "--to", help="Inclusive period in YYYY-MM-DD format."),
    output_dir: Path = typer.Option(Path("data/normalized/chartmetric-backfill")),
    state_dir: Path = typer.Option(Path("data/interim/chartmetric-backfill")),
    page_size: int = typer.Option(200, min=1, max=200),
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
    try:
        start = date.fromisoformat(from_date)
        end = date.fromisoformat(to_date)
    except ValueError as error:
        typer.echo(
            json.dumps({"status": "INVALID_WINDOW", "provider": "CHARTMETRIC", "error": str(error)})
        )
        return
    transport = HttpxTransport("https://api.chartmetric.com")
    try:
        client = ChartmetricClient(settings.chartmetric_refresh_token, transport=transport)
        if countries.casefold() == "discovered":
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
        summary = ChartmetricBackfillRunner(client, output_dir, state_dir).run(
            BackfillRequest(
                platform=platform,
                countries=selected_countries,
                interval=interval,
                chart_type=chart_type,
                start_date=start,
                end_date=end,
                page_size=page_size,
            )
        )
        typer.echo(
            json.dumps(
                {
                    "status": "PARTIAL" if summary.failed_tasks else "COMPLETED",
                    "provider": "CHARTMETRIC",
                    "countries": len(selected_countries),
                    **asdict(summary),
                },
                default=str,
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
