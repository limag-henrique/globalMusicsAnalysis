"""Bounded, resumable native MGD evidence campaign; never adjudicates research."""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from chart_observatory import research_flow as flow
from chart_observatory import research_rankings, research_source_projection

VERSION = "native-mgd-evidence-campaign-v1"


def _now():
    return datetime.now(UTC).isoformat()


def _save(path, value):
    temporary = path.with_suffix(path.suffix + ".part")
    flow.write_json(temporary, value)
    temporary.replace(path)


@contextmanager
def _exclusive(root):
    """OS releases SQLite locking on crashes; no PID guess or stale-file deletion."""
    conn = sqlite3.connect(root / "ownership.sqlite", timeout=1)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS owner(marker INTEGER)")
        conn.commit()
        conn.execute("BEGIN EXCLUSIVE")
    except sqlite3.OperationalError as exc:
        conn.close()
        raise ValueError("native evidence campaign is already active") from exc
    try:
        yield
    finally:
        conn.rollback()
        conn.close()


def verify_evidence(path, selection_sha256):
    path = Path(path).resolve()
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["artifacts"].items():
        artifact = (path / name).resolve()
        if not artifact.is_relative_to(path) or flow.file_hash(artifact) != digest:
            raise ValueError("native evidence artifact changed")
    for name, digest in manifest["input_hashes"].items():
        if flow.file_hash(name) != digest:
            raise ValueError("native evidence input changed")
    report = json.loads((path / "report.json").read_text(encoding="utf-8"))
    if report["selection_sha256"] != selection_sha256 or report["scientific_approval"] is not False:
        raise ValueError("native evidence belongs to another selection or claims approval")
    return report


def plan_cells(cells, members, inventory):
    """One primary provider/platform per country/year, original positions retained."""
    grouped = {}
    for row in members:
        if (row["provider"], row["platform"]) == ("MGD", "SPOTIFY"):
            key = row["country_code"], row["year"]
            grouped.setdefault(key, []).append(row)
    quota = {(r["country_code"], r["year"]): r["quota"] for r in cells}
    result = []
    for (country, year), rows in grouped.items():
        sources = [
            r
            for r in inventory["files"]
            if r.get("provider") == "MGD"
            and r.get("origin_platform") == "SPOTIFY"
            and country in r.get("countries", [])
            and "Top 200" in r.get("chart_types", [])
        ]
        result.append(
            {
                "country_code": country,
                "year": year,
                "quota": quota[country, year],
                "selected_positions": len(rows),
                "raw_source": sources[0]["path"] if len(sources) == 1 else None,
                "source_resolution": "exact_inventory"
                if len(sources) == 1
                else "source_missing_or_ambiguous",
            }
        )
    return sorted(
        result, key=lambda r: (r["country_code"] not in {"BR", "PT"}, r["country_code"], r["year"])
    )


def _record(path, report, *, reused=False):
    keys = (
        "country_code",
        "year",
        "selected_positions",
        "observations",
        "reconstruction_approved",
        "rank_and_metric_matches",
        "metadata_exact_matches",
        "all_fields_match",
        "missing_display_metadata_observations",
        "reconstruction_reasons",
    )
    return {
        **{key: report[key] for key in keys},
        "state": "completed",
        "evidence": str(path),
        "report_sha256": flow.file_hash(Path(path) / "report.json"),
        "scientific_approval": False,
        "reused": reused,
    }


def summarize(plan, records, requested_positions, observed_positions):
    completed = [r for r in records.values() if r["state"] == "completed"]
    selected = sum(r["selected_positions"] for r in completed)
    return {
        "eligible_mgd_cells": len(plan),
        "eligible_mgd_positions": sum(r["selected_positions"] for r in plan),
        "processed_cells": len(completed),
        "failed_cells": sum(r["state"] == "failed" for r in records.values()),
        "structurally_complete_cells": sum(r["reconstruction_approved"] for r in completed),
        "processed_selected_positions": selected,
        "matched_rank_metric_positions": sum(r["rank_and_metric_matches"] for r in completed),
        "matched_rank_metric_positions_in_structurally_complete_cells": sum(
            r["rank_and_metric_matches"] for r in completed if r["reconstruction_approved"]
        ),
        "metadata_exact_matches": sum(r["metadata_exact_matches"] for r in completed),
        "observations_examined": sum(r["observations"] for r in completed),
        "original_requested_positions": requested_positions,
        "original_observed_positions": observed_positions,
        "processed_share_of_observed_percent": 100 * selected / observed_positions
        if observed_positions
        else None,
        "processed_share_of_requested_percent": 100 * selected / requested_positions
        if requested_positions
        else None,
        "scientifically_approved_positions": 0,
        "scientific_approval": False,
        "production_writes": 0,
        "network_calls": 0,
        "paid_calls": 0,
    }


def run_campaign(
    *, project, selection, output, limit=20, workers=3, reuse_roots=(), source_manifest=None
):
    project, selection, output = (Path(p).resolve() for p in (project, selection, output))
    if type(limit) is not int or limit < 1 or type(workers) is not int or not 1 <= workers <= 3:
        raise ValueError("positive cell limit and one to three workers required")
    if not output.is_relative_to(project / "data/runtime"):
        raise ValueError("native campaign must remain in project private runtime")
    manifest, cells, members, selection_inputs = flow.load_selection(selection)
    source_manifest = Path(
        source_manifest or project / "research/mgd_source_manifest.json"
    ).resolve()
    inventory = json.loads(source_manifest.read_text(encoding="utf-8"))
    plan = plan_cells(cells, members, inventory)
    selection_sha = flow.file_hash(selection / "manifest.json")
    descriptor = {
        "version": VERSION,
        "selection_sha256": selection_sha,
        "selection": str(selection),
        "source_manifest": str(source_manifest),
        "source_manifest_sha256": flow.file_hash(source_manifest),
        "worker_sha256": flow.file_hash(__file__),
        "projection_sha256": flow.file_hash(research_source_projection.__file__),
        "rankings_sha256": flow.file_hash(research_rankings.__file__),
        "flow_sha256": flow.file_hash(flow.__file__),
        "planned_cells": plan,
    }
    output.mkdir(parents=True, exist_ok=True)
    with _exclusive(output):
        campaign_path = output / "campaign.json"
        if campaign_path.exists():
            if json.loads(campaign_path.read_text(encoding="utf-8")) != descriptor:
                raise ValueError("campaign inputs/code changed; use a new campaign directory")
        else:
            flow.write_json(campaign_path, descriptor)
        status_path = output / "status.json"
        previous = (
            json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
        )
        records = previous.get("cells", {})
        for key, record in records.items():
            if record["state"] == "completed":
                verified = verify_evidence(record["evidence"], selection_sha)
                if (
                    flow.file_hash(Path(record["evidence"]) / "report.json")
                    != record["report_sha256"]
                ):
                    raise ValueError("campaign evidence reference changed")
                if key != f"{verified['country_code']}-{verified['year']}":
                    raise ValueError("campaign cell/evidence identity mismatch")
        started = previous.get("started_at", _now())

        def checkpoint(state):
            report = {
                "version": VERSION,
                "state": state,
                "started_at": started,
                "updated_at": _now(),
                "selection_sha256": selection_sha,
                "cell_limit": limit,
                "workers": workers,
                "cells": records,
                "summary": summarize(plan, records, manifest["requested_positions"], len(members)),
            }
            _save(status_path, report)
            return report

        def acquire(cell):
            key = f"{cell['country_code']}-{cell['year']}"
            try:
                if cell["raw_source"] is None:
                    raise ValueError("source is missing or ambiguous")
                for reuse in reuse_roots:
                    candidate = Path(reuse).resolve() / key
                    if (candidate / "manifest.json").is_file():
                        report = verify_evidence(candidate, selection_sha)
                        return key, _record(candidate, report, reused=True)
                target = output / "cells" / key / ("attempt-" + uuid4().hex[:12])
                report = research_source_projection.project_mgd_cell(
                    project=project,
                    selection=selection,
                    raw_source=project / cell["raw_source"],
                    output=target,
                    country=cell["country_code"],
                    year=cell["year"],
                    source_manifest=source_manifest,
                )
                return key, _record(target, report)
            except Exception as exc:
                return key, {
                    "state": "failed",
                    "country_code": cell["country_code"],
                    "year": cell["year"],
                    "error_type": type(exc).__name__,
                    "reason": str(exc) if isinstance(exc, ValueError) else None,
                    "scientific_approval": False,
                }

        checkpoint("running")
        pending = [
            c
            for c in plan[:limit]
            if records.get(f"{c['country_code']}-{c['year']}", {}).get("state") != "completed"
        ]
        with ThreadPoolExecutor(workers) as executor:
            for future in as_completed([executor.submit(acquire, cell) for cell in pending]):
                key, record = future.result()
                records[key] = record
                checkpoint("running")
        for name, digest in selection_inputs.items():
            if flow.file_hash(name) != digest:
                raise ValueError("frozen selection changed during campaign")
        final = checkpoint("completed_with_deficits")
        flow.write_rows(output / "cells.jsonl", [records[k] for k in sorted(records)])
        return final
