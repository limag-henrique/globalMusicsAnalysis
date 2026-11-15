"""Build an exploratory annual overlay without promoting pending source evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from chart_observatory.ingestion.source_coverage import normalize_source_coverage
from chart_observatory.research_flow import load_selection
from chart_observatory.research_rankings import verify_published_annual

STATUS = "PROVISIONAL_SOURCE_PERIOD_BINDING_REVIEW_REQUIRED"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf8").splitlines()]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def lines(rows):
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf8")


def inspect_cell_semantics(cells, memberships):
    selected = Counter((r["country_code"], r["year"]) for r in memberships)
    provisional = Counter(
        (r["country_code"], r["year"])
        for r in memberships
        if str(r.get("selection_status", "")).startswith("PROVISIONAL_")
    )
    audit = []
    for cell in cells:
        key, quota = (cell["country_code"], cell["year"]), cell["quota"]
        complete = selected[key] - provisional[key] if cell["year"] < 2026 else 0
        expected = dict(
            selected_positions=selected[key],
            provisional_positions=provisional[key],
            complete_calendar_year_positions=complete,
            missing_positions=quota - selected[key] if quota is not None else None,
            missing_complete_annual_positions=quota - complete if quota is not None else None,
        )
        mismatches = {
            k: {"stored": cell.get(k), "expected": v}
            for k, v in expected.items()
            if cell.get(k) != v
        }
        audit.append(
            dict(country_code=key[0], year=key[1], passed=not mismatches, mismatches=mismatches)
        )
    if any(not r["passed"] for r in audit):
        raise ValueError("country/year counters differ from actual membership semantics")
    return audit


def validate_published_delta(cells, memberships, observations, selected, declared_checks):
    """Require whole native annual lists and full quotas in previously empty cells."""
    cell_map = {(r["country_code"], r["year"]): r for r in cells}
    occupied = {(r["country_code"], r["year"]) for r in memberships}
    by_cell, selected_by_cell = defaultdict(list), defaultdict(list)
    for row in observations:
        by_cell[row["country_code"], row["year"]].append(row)
    for row in selected:
        selected_by_cell[row["country_code"], row["year"]].append(row)
    if not by_cell or set(by_cell) != set(selected_by_cell):
        raise ValueError("observations and quota selection have different cells")
    checks = {(r["country_code"], r["year"]): r for r in declared_checks}
    if set(checks) != set(by_cell) or len(checks) != len(declared_checks):
        raise ValueError("one declared verification per supplemental cell required")
    accepted, result_checks = [], []
    required_fields = ("candidate_id", "source_native_id", "title", "artist")
    for key, rows in sorted(by_cell.items()):
        if key not in cell_map or cell_map[key]["quota"] is None or key in occupied:
            raise ValueError("supplement collides with occupied or undefined/outside cell")
        quota, scope = cell_map[key]["quota"], checks[key]
        for row in rows:
            if row.get("ranking_kind") != "published_annual" or row.get("metric_value") is not None:
                raise ValueError("published rank cannot synthesize or mix a stream/view metric")
            if any(not isinstance(row.get(k), str) or not row[k].strip() for k in required_fields):
                raise ValueError("published chart identity missing")
            if row.get("scientifically_verified") or row.get("classification_ready"):
                raise ValueError("pending supplement cannot carry scientific/paid approval")
        result = verify_published_annual(
            rows,
            country_code=key[0],
            year=key[1],
            platform=scope["platform"],
            provider=scope["provider"],
            quota=quota,
            expected_depth=scope["expected_depth"],
            period_start=scope["period_start"],
            period_end=scope["ranking_period_end"],
        )
        if not result["approved"]:
            raise ValueError(f"supplement native list invalid: {key}: {result['reasons']}")
        chosen = sorted(selected_by_cell[key], key=lambda r: r["position"])
        if [r["position"] for r in chosen] != list(range(1, quota + 1)):
            raise ValueError("supplement does not provide the entire contiguous quota")
        native = {r["position"]: r for r in rows}
        if any(row != native[row["position"]] for row in chosen):
            raise ValueError("quota row differs from preserved full annual publication")
        for row in chosen:
            accepted.append(
                {
                    **row,
                    "quota_main": quota,
                    "selection_status": STATUS,
                    "coverage_status": "PENDING_SOURCE_PERIOD_BINDING",
                    "identity_status": "chart_entry_pending_recording_review",
                    "identity_entity_type": "native_published_chart_entry",
                    "not_for_paid_submission": True,
                    "classification_ready": False,
                    "scientifically_verified": False,
                }
            )
        result_checks.append({**result, "rows": [], "scientific_approval": False})
    return accepted, result_checks


def build_published_overlay(parent, supplement, output, *, project):
    parent, supplement, output, project = map(Path, (parent, supplement, output, project))
    parent, supplement, output, project = (
        p.resolve() for p in (parent, supplement, output, project)
    )
    if not all(p.is_relative_to(project) for p in (parent, supplement, output)):
        raise ValueError("overlay paths must stay inside the project")
    if output.exists():
        raise FileExistsError("immutable overlay output already exists")
    manifest, cells, members, _ = load_selection(parent)
    supplementary = read_json(supplement / "manifest.json")
    dependency_inputs = {}
    for key, hash_key in (
        ("source", "source_manifest_sha256"),
        ("period_evidence", "period_evidence_manifest_sha256"),
    ):
        if key not in supplementary:
            continue
        folder = Path(supplementary[key]).resolve()
        reference = folder / "manifest.json"
        if not folder.is_relative_to(project) or sha(reference) != supplementary[hash_key]:
            raise ValueError("supplement primary evidence manifest changed")
        dependency_inputs[reference.relative_to(project).as_posix()] = sha(reference)
        evidence_manifest = read_json(reference)
        for capture in evidence_manifest.get("captures", []):
            path = (folder / capture["path"]).resolve()
            if not path.is_relative_to(folder) or sha(path) != capture["sha256"]:
                raise ValueError("primary evidence capture changed")
            dependency_inputs[path.relative_to(project).as_posix()] = capture["sha256"]
    for name, expected in supplementary["output_hashes"].items():
        path = (supplement / name).resolve()
        if not path.is_relative_to(supplement) or sha(path) != expected:
            raise ValueError("supplement output missing or hash changed")
    if supplementary.get("parent_manifest_sha256") != sha(parent / "manifest.json"):
        raise ValueError("supplement is bound to a different parent selection")
    observations = read_rows(supplement / "observations.jsonl")
    selected = read_rows(supplement / "quota-candidates.jsonl")
    accepted, checks = validate_published_delta(
        cells, members, observations, selected, read_json(supplement / "verification.json")
    )
    counts = Counter((r["country_code"], r["year"]) for r in accepted)
    new_coverage = []
    for check in checks:
        new_coverage.append(
            dict(
                country_code=check["country_code"],
                year=check["year"],
                platform=check["platform"],
                provider=check["provider"],
                frequency="PUBLISHED_ANNUAL",
                expected_periods=1,
                collected_periods=1,
                expected_depth=check["expected_depth"],
                minimum_depth=check["counts"]["published_rows"],
                coverage_status="PENDING_SOURCE_PERIOD_BINDING",
                metric_type="NATIVE_PUBLISHED_RANK",
                metric_value=None,
                source_period_binding="documentary_inference_pending_review",
                period_start=check["period_start"],
                period_end=check["ranking_period_end"],
                native_list_structure_verified=True,
                scientifically_verified=False,
                identity_status="chart_entry_pending_recording_review",
            )
        )
    coverage = normalize_source_coverage(read_json(parent / "source_coverage.json"), new_coverage)
    updated_cells = {}
    for cell in cells:
        key = cell["country_code"], cell["year"]
        if not counts[key]:
            continue
        records = [r for r in accepted if (r["country_code"], r["year"]) == key]
        updated_cells[key] = {
            **cell,
            "selected_positions": counts[key],
            "provisional_positions": counts[key],
            "complete_calendar_year_positions": 0,
            "missing_positions": cell["quota"] - counts[key],
            "missing_complete_annual_positions": cell["quota"],
            "missing_position_numbers": [],
            "platforms": sorted({r["platform"] for r in records}),
            "selection_statuses": {STATUS: counts[key]},
            "status": STATUS,
            "classification_ready": False,
        }
    changed = {
        "combined.jsonl",
        "ranked_titles.jsonl",
        "country_years.jsonl",
        "source_coverage.json",
        "new_market_rankings.parquet",
    }
    output.mkdir(parents=True)
    for name in manifest["output_hashes"]:
        if name not in changed:
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(parent / name, destination)
    (output / "combined.jsonl").write_bytes(
        (parent / "combined.jsonl").read_bytes() + lines(accepted)
    )
    title_fields = list(read_rows(parent / "ranked_titles.jsonl")[0])
    (output / "ranked_titles.jsonl").write_bytes(
        (parent / "ranked_titles.jsonl").read_bytes()
        + lines([{k: r.get(k) for k in title_fields} for r in accepted])
    )
    with (output / "country_years.jsonl").open("wb") as stream:
        for raw in (parent / "country_years.jsonl").read_bytes().splitlines(keepends=True):
            cell = json.loads(raw)
            replacement = updated_cells.get((cell["country_code"], cell["year"]))
            stream.write(lines([replacement]) if replacement else raw)
    write_json(output / "source_coverage.json", coverage)
    ranking_extras = [
        {
            **r,
            "selection_status": STATUS,
            "not_for_paid_submission": True,
            "classification_ready": False,
            "identity_status": "chart_entry_pending_recording_review",
        }
        for r in observations
    ]
    pl.concat(
        [pl.read_parquet(parent / "new_market_rankings.parquet"), pl.DataFrame(ranking_extras)],
        how="diagonal_relaxed",
    ).write_parquet(output / "new_market_rankings.parquet")
    write_json(output / "published_annual_overlay_verification.json", checks)
    combined, new_cells = (
        members + accepted,
        [updated_cells.get((c["country_code"], c["year"]), c) for c in cells],
    )
    cell_audit = inspect_cell_semantics(new_cells, combined)
    write_json(output / "cell_semantics_audit.json", cell_audit)
    review_queue = [
        {
            "country_code": r["country_code"],
            "year": r["year"],
            "position": r["position"],
            "candidate_id": r["candidate_id"],
            "source_native_id": r["source_native_id"],
            "status": STATUS,
            "ranking_kind": "published_annual",
            "period_start": r["period_start"],
            "period_end": r["period_end"],
            "source_period_evidence": r.get("source_period_evidence"),
            "required_reviews": [
                "documentary_source_period_binding",
                "source_stratum_protocol",
                "chart_entry_recording_identity",
            ],
            "scientifically_verified": False,
            "not_for_paid_submission": True,
        }
        for r in accepted
    ]
    (output / "published_annual_review_queue.jsonl").write_bytes(lines(review_queue))
    preserved = {
        name: sha(output / name) == digest
        for name, digest in manifest["output_hashes"].items()
        if name not in changed
    }
    if not all(preserved.values()):
        raise ValueError("unmodified parent artifact did not retain its bytes")
    write_json(
        output / "overlay_audit_report.json",
        dict(
            parent_memberships=len(members),
            additional_provisional_memberships=len(accepted),
            resulting_memberships=len(combined),
            unchanged_parent_artifacts=preserved,
            original_membership_bytes_preserved_as_prefix=(output / "combined.jsonl")
            .read_bytes()
            .startswith((parent / "combined.jsonl").read_bytes()),
            parent_cells=len(cells),
            unchanged_cells=len(cells) - len(updated_cells),
            updated_cells=len(updated_cells),
            quota_denominator_unchanged=True,
            cell_semantics_checks=len(cell_audit),
            cell_semantics_failures=0,
            source_coverage_objects=len(coverage),
            scientific_approved_positions_added=0,
            g1_approved=False,
        ),
    )
    with (output / "country_years.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(new_cells[0]))
        writer.writeheader()
        writer.writerows(
            {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()}
            for r in new_cells
        )
    historical = {
        k: manifest.get(k, {}) for k in ("source_hashes", "input_hashes", "implementation_hashes")
    }
    current_inputs = {
        str(p.relative_to(project)).replace("\\", "/"): sha(p)
        for p in (
            parent / "manifest.json",
            supplement / "manifest.json",
            supplement / "observations.jsonl",
            supplement / "quota-candidates.jsonl",
            supplement / "verification.json",
        )
    }
    current_inputs.update(dependency_inputs)
    code = Path(__file__).resolve()
    result = {
        **manifest,
        "selection_revision": output.name,
        "created_at": datetime.now(UTC).isoformat(),
        "parent_selection": parent.relative_to(project).as_posix(),
        "parent_selection_manifest_sha256": sha(parent / "manifest.json"),
        "supplement_selection": supplement.relative_to(project).as_posix(),
        "supplement_manifest_sha256": sha(supplement / "manifest.json"),
        "memberships": len(combined),
        "candidate_identities": len({r["candidate_id"] for r in combined}),
        "countries_with_memberships": len({r["country_code"] for r in combined}),
        "cells_with_memberships": len({(r["country_code"], r["year"]) for r in combined}),
        "new_provisional_memberships": manifest.get("new_provisional_memberships", 0)
        + len(accepted),
        "missing_positions": sum(c["missing_positions"] or 0 for c in new_cells),
        "missing_complete_annual_positions": sum(
            c["missing_complete_annual_positions"] or 0 for c in new_cells
        ),
        "raw_membership_coverage_pct": len(combined) / manifest["requested_positions"] * 100,
        "published_annual_provisional_added_positions": len(accepted),
        "published_annual_added_cells": [f"{c}/{y}" for c, y in sorted(counts)],
        "published_annual_admission_status": STATUS,
        "source_coverage_rows": len(coverage),
        "source_coverage_invalid_rows": 0,
        "cell_semantics_checks_failed": 0,
        "cell_semantics_audit_report": (output / "cell_semantics_audit.json")
        .relative_to(project)
        .as_posix(),
        "scientifically_verified": False,
        "scientifically_verified_positions_added": 0,
        "g1_approved": False,
        "classification_ready": False,
        "lyrics_acquisition_ready": False,
        "paid_calls": 0,
        "network_calls": 0,
        "database_write": False,
        "historical_parent_inputs": historical,
        "source_hashes": current_inputs,
        "input_hashes": current_inputs,
        "implementation_hashes": {code.relative_to(project).as_posix(): sha(code)},
        "output_hashes": {
            p.relative_to(output).as_posix(): sha(p) for p in output.rglob("*") if p.is_file()
        },
    }
    write_json(output / "manifest.json", result)
    load_selection(output)
    return result
