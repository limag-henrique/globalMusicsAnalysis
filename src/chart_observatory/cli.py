# ruff: noqa: B008

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

import typer

from chart_observatory.application import LocalResearchApplication
from chart_observatory.charts.registry import AdapterRegistry
from chart_observatory.config import Settings
from chart_observatory.domain.enums import RightsOperation
from chart_observatory.domain.errors import SourceDisabled
from chart_observatory.procurement.schema_profiler import profile_sample
from chart_observatory.sources.chartmetric import ChartmetricClient, ChartmetricError
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


def _service(authorized: bool = False) -> LocalResearchApplication:
    return LocalResearchApplication(Path("data/runtime"), manual_authorized=authorized)


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
) -> None:
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
                {
                    key: value
                    for key, value in asdict(row).items()
                    if key != "raw_fields"
                }
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


@promusica_app.command("discover")
def sources_promusica_discover(
    output: Path = typer.Option(Path("research/pro_musica_inventory.csv")),
) -> None:
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
) -> None:
    """Discover official YouTube regions; optionally inspect one region's categories."""
    settings = Settings.load(Path.cwd())
    if not settings.youtube_data_api_key:
        typer.echo(json.dumps({"status": "NOT_CONFIGURED", "provider": "YOUTUBE_DATA_API"}))
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
) -> None:
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
