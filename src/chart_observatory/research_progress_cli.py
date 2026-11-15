# ruff: noqa: B008
"""CLI function registered by the research app without changing its audit controller."""

import json
from pathlib import Path

import typer

from chart_observatory.research_progress import build_progress, write_progress


def progress_command(
    audit: Path = typer.Option(..., help="Frozen audit directory."),
    staging_status: Path | None = typer.Option(None, help="Explicit selection-bound local status."),
    output: Path | None = typer.Option(None, help="New immutable progress directory."),
    live_database: bool = typer.Option(False, help="Read the current PostgreSQL inventory."),
    selection: Path | None = typer.Option(None, help="Frozen selection for live database check."),
    project: Path = typer.Option(Path.cwd(), help="Project root for configured PostgreSQL."),
):
    try:
        report = build_progress(audit, staging_status)
        if live_database:
            if selection is None:
                raise ValueError("--selection is required with --live-database")
            from chart_observatory.research_database_health import current_inventory

            live = current_inventory(project, selection)
            if live["selection_sha256"] != report["selection_sha256"]:
                raise ValueError("live database inventory belongs to a different audit selection")
            report["live_database_inventory"] = live
            report["current_database_certified"] = live["current_database_certified"]
            report["scientific_progress_evidence"] = (
                "frozen_scientific_gates_plus_current_read_only_inventory"
            )
            if live["staging"] is not None:
                from chart_observatory.research_progress import fraction

                stage = live["staging"]
                report["historical_lyrics_availability"] = report["lyrics_availability"]
                report["lyrics_availability"] = {
                    **fraction(stage["text_candidates"], stage["candidates"]),
                    "run_id": stage["run_id"],
                    "observed_at": live["observed_at"],
                    "unit": "candidate_identity",
                    "evidence_status": "current_postgresql_inventory",
                    "current_database_certified": live["current_database_certified"],
                    "scientific_approval": False,
                }
        if output is not None:
            write_progress(output, report)
        typer.echo(json.dumps(report, ensure_ascii=False))
    except Exception as exc:
        detail = str(exc) if isinstance(exc, (ValueError, OSError)) else type(exc).__name__
        typer.echo(json.dumps({"error": detail}, ensure_ascii=False), err=True)
        raise typer.Exit(code=1) from exc
