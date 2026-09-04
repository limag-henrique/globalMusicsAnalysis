import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from chart_observatory.application import LocalResearchApplication
from chart_observatory.charts.registry import AdapterRegistry
from chart_observatory.domain.enums import RightsOperation
from chart_observatory.domain.errors import SourceDisabled

app = typer.Typer(help="Rights-gated cross-platform chart research tools.")
collect_app = typer.Typer()
import_app = typer.Typer()
coverage_app = typer.Typer()
metrics_app = typer.Typer()
export_app = typer.Typer()
app.add_typer(collect_app, name="collect")
app.add_typer(import_app, name="import-chart")
app.add_typer(coverage_app, name="coverage")
app.add_typer(metrics_app, name="metrics")
app.add_typer(export_app, name="export")


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


if __name__ == "__main__":
    app()
