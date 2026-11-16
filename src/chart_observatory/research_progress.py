"""Progress facts with explicit denominators; availability is not scientific approval."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory import research_flow as flow
from chart_observatory.pipeline_state import file_hash, process_alive

VERSION = "research-progress-v2"
STAGING_STATUS_CONTRACT = "research-staging-status-v2"


def _staging_candidate_total(value):
    """Return a validated candidate total from current or recovery status."""
    for field in ("unique_candidates", "candidate_count"):
        candidate_total = value.get(field)
        if type(candidate_total) is int and candidate_total >= 0:
            return candidate_total, field
    raise ValueError("staging status requires unique_candidates or candidate_count")


def _staging_ready_count(value):
    ready = value.get("paid_ready_candidates")
    if ready is None:
        return None
    if type(ready) is not int or ready < 0:
        raise ValueError("paid_ready_candidates must be a non-negative integer")
    return ready


def fraction(numerator, denominator):
    if (
        type(numerator) is not int
        or numerator < 0
        or type(denominator) is not int
        or denominator < 0
        or numerator > denominator
    ):
        raise ValueError("progress requires integer counts with 0 <= numerator <= denominator")
    return {
        "numerator": numerator,
        "denominator": denominator,
        "percent": 100 * numerator / denominator if denominator else None,
    }


def _timestamp(raw):
    if not isinstance(raw, str):
        raise ValueError("status requires an explicit aware timestamp")
    value = datetime.fromisoformat(raw)
    if value.tzinfo is None:
        raise ValueError("status requires an explicit aware timestamp")
    return value


def build_progress(audit, staging_status=None, *, now=None):
    """Read a verified audit and an optional selection-bound local inventory.

    A stale input invalidates current gate claims, but an intact historical audit
    can still be described as historical. Tampered audit outputs are never used.
    """
    audit = Path(audit).resolve()
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("aware observation time required")
    try:
        report = flow.verify_audit(audit)
        current = True
    except (ValueError, FileNotFoundError):
        report = flow.verify_audit(audit, check_inputs=False)
        current = False
    expected = report["scope"]["requested_positions"]
    inventory = report["inventory"]
    observed = fraction(inventory["observed_positions"], expected)
    observed.update(
        unit="country_year_position",
        evidence_status=(
            "verified_frozen_inventory" if current else "historical_audit_inputs_changed"
        ),
    )
    gates = report["gates"]
    if len(gates) != 5 or {g["gate"] for g in gates} != {"G1", "G2", "G3", "G4", "G5"}:
        raise ValueError("a complete five-gate audit is required")
    scientific = []
    for gate in gates:
        count = None
        if "numerator" in gate and "denominator" in gate:
            count = fraction(gate["numerator"], gate["denominator"])
        scientific.append(
            {
                "gate": gate["gate"],
                "recorded_state": gate["state"],
                "current_state": gate["state"] if current else "audit_stale",
                "coverage": count,
                "current_percent": count["percent"] if current and count else None,
                "approved_cells": gate.get("approved_cells"),
                "total_cells": gate.get("total_cells"),
                "unknown_denominators": gate.get("unknown_denominators"),
            }
        )
    complete = sum(g["state"] == "aprovado" for g in gates)
    output = {
        "version": VERSION,
        "observed_at": now.isoformat(),
        "audit": str(audit),
        "audit_evaluated_at": report["evaluated_at"],
        "gate_policy_version": report.get("gate_policy_version", "legacy80-v4"),
        "gate_targets": report.get("gate_targets"),
        "selection_sha256": report["selection_sha256"],
        "audit_current_inputs_verified": current,
        "current_database_certified": False,
        "scientific_progress_evidence": "frozen_audit_not_live_database_revalidation",
        "rankings_observed": observed,
        "scientific_gates": scientific,
        "scientific_gate_completion": fraction(complete, 5) if current else None,
        "recorded_scientific_gate_completion": fraction(complete, 5),
        "overall_software_completion_percent": None,
        "overall_percent_explanation": (
            "No average combines chart positions, candidate texts, "
            "implementation or scientific gates."
        ),
        "research_ready": report["research_ready"] if current else False,
        "country_year_cells": None,
        "lyrics_availability": None,
        "warnings": [] if current else ["audit_inputs_changed_rerun_audit"],
        "input_hashes": {str(audit / "manifest.json"): file_hash(audit / "manifest.json")},
        "paid_calls": 0,
        "uploads": 0,
    }
    # Use only the exact country/year table whose hash was bound by this audit.
    matches = [
        (Path(name), digest)
        for name, digest in report.get("input_hashes", {}).items()
        if Path(name).name == "country_years.jsonl"
    ]
    if len(matches) == 1:
        path, digest = matches[0]
        if file_hash(path) == digest:
            cells = list(flow.rows(path))
            if len(cells) != report["scope"]["country_year_cells"]:
                raise ValueError("country/year inventory differs from audit")
            statuses = Counter(c["status"] for c in cells)
            available = sum(c["selected_positions"] > 0 for c in cells)
            known_quota = [c for c in cells if type(c.get("quota")) is int and c["quota"] > 0]
            observed_threshold = sum(
                c["selected_positions"] * 5 >= c["quota"] * 4 for c in known_quota
            )
            output["country_year_cells"] = {
                "with_observed_positions": fraction(available, len(cells)),
                "at_least_80_percent_observed_of_known_quota": fraction(
                    observed_threshold, len(known_quota)
                ),
                "unresolved_quota_cells": fraction(len(cells) - len(known_quota), len(cells)),
                "quota_filled_complete_calendar": fraction(
                    statuses["QUOTA_FILLED_COMPLETE_CALENDAR"], len(cells)
                ),
                "statuses": dict(statuses),
                "scientific_approval": False,
            }
            output["input_hashes"][str(path)] = digest
    if staging_status is not None:
        path = Path(staging_status).resolve()
        digest = file_hash(path)
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if file_hash(path) != digest:
            raise ValueError("staging status changed while reading")
        if value.get("global_manifest_sha256") != report["selection_sha256"]:
            raise ValueError("staging inventory belongs to another selection")
        total, total_field = _staging_candidate_total(value)
        if total != inventory["candidate_identities"]:
            raise ValueError("staging candidate denominator differs from audit")
        text = value.get("text_candidates")
        if type(text) is not int or text < 0:
            raise ValueError("text_candidates must be a non-negative integer")
        availability = fraction(text, total)
        ready_count = _staging_ready_count(value)
        ready = fraction(ready_count, total) if ready_count is not None else None
        if ready is not None and ready["numerator"] > availability["numerator"]:
            raise ValueError("ready candidates cannot exceed candidates with text")
        timestamp = _timestamp(value.get("updated_at"))
        age = (now - timestamp).total_seconds()
        if age < 0:
            raise ValueError("staging status timestamp is in the future")
        availability.update(
            {
                "unit": "candidate_identity",
                "source": str(path),
                "run_id": value.get("run_id"),
                "updated_at": timestamp.isoformat(),
                "age_hours": age / 3600,
                "older_than_24_hours": age > 86400,
                "evidence_status": "local_historical_snapshot",
                "current_database_certified": False,
                "scientific_approval": False,
                "recorded_paid_ready": ready,
                "status_contract": value.get("status_contract", "legacy"),
                "candidate_count_field": total_field,
            }
        )
        if value.get("pid") is not None:
            pid = value["pid"]
            if type(pid) is not int or pid <= 0:
                raise ValueError("invalid process identifier in staging status")
            exists = process_alive(pid)
            availability["process"] = {
                "pid": pid,
                "pid_exists": exists,
                "identity_verified": False,
                "state": "identity_unverified" if exists else "not_found",
            }
        output["lyrics_availability"] = availability
        output["input_hashes"][str(path)] = digest
        if age > 86400:
            output["warnings"].append("staging_status_older_than_24_hours")
    return output


def write_progress(output, report):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("progress output already exists; use a new version")
    for path, digest in report["input_hashes"].items():
        if file_hash(path) != digest:
            raise ValueError("progress input changed before export; refresh the report")
    output.mkdir(parents=True, exist_ok=False)
    flow.write_json(output / "progress.json", report)
    metrics = [{"metric": "rankings_observed", **report["rankings_observed"]}]
    cell_progress = report.get("country_year_cells")
    if cell_progress:
        for key in (
            "at_least_80_percent_observed_of_known_quota",
            "unresolved_quota_cells",
            "quota_filled_complete_calendar",
        ):
            metrics.append({"metric": key, **cell_progress[key]})
    for key in ("lyrics_availability", "scientific_gate_completion"):
        if report.get(key):
            metrics.append({"metric": key, **report[key]})
    for gate in report["scientific_gates"]:
        if gate["coverage"]:
            metrics.append(
                {
                    "metric": gate["gate"],
                    **gate["coverage"],
                    "evidence_status": gate["current_state"],
                }
            )
    flow.write_csv(
        output / "progress.csv",
        metrics,
        ["metric", "numerator", "denominator", "percent", "evidence_status"],
    )
    flow.write_json(
        output / "manifest.json",
        {
            "version": VERSION,
            "input_hashes": report["input_hashes"],
            "artifacts": {p.name: file_hash(p) for p in output.iterdir() if p.is_file()},
            "producer_sha256": file_hash(Path(__file__)),
        },
    )
