# ruff: noqa: B008
"""Native source reconstruction for the frozen research selection."""

import json
from pathlib import Path

import typer

from chart_observatory.research_source_projection import project_mgd_cell


def project_mgd_command(
    selection: Path = typer.Option(...),
    raw_source: Path = typer.Option(...),
    output: Path = typer.Option(...),
    country: str = typer.Option(...),
    year: int = typer.Option(...),
    project: Path = typer.Option(Path.cwd()),
    source_manifest: Path | None = typer.Option(None),
):
    """Reconstruct a primary MGD cell directly from its native tab-separated file."""
    try:
        report = project_mgd_cell(
            project=project,
            selection=selection,
            raw_source=raw_source,
            output=output,
            country=country,
            year=year,
            source_manifest=source_manifest,
        )
        fields = (
            "country_code",
            "year",
            "observations",
            "selected_positions",
            "reconstruction_approved",
            "rank_and_metric_matches",
            "metadata_exact_matches",
            "all_fields_match",
            "missing_display_metadata_observations",
            "scientific_approval",
            "paid_calls",
        )
        typer.echo(
            json.dumps(
                {"output": str(output.resolve()), **{key: report[key] for key in fields}},
                ensure_ascii=False,
            )
        )
    except (ValueError, OSError) as exc:
        typer.echo(json.dumps({"error": str(exc)}, ensure_ascii=False), err=True)
        raise typer.Exit(code=1) from exc
