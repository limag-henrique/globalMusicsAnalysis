"""Stage private local Gemini requests for a later, reconciled BRL-controlled handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from chart_observatory.config import Settings
from chart_observatory.db.models.lyrics_batch import LyricClassificationBatchItem
from chart_observatory.lyrics.batch_jsonl import (
    build_batch_request,
    canonical_request_sha256,
    validate_batch_jsonl,
)
from chart_observatory.lyrics.batch_service import CostBudgetExceeded
from chart_observatory.lyrics.brl_budget import BrlBudgetPolicy
from chart_observatory.lyrics.classification import (
    PROMPT_VERSION,
    TAXONOMY_VERSION,
    LyricsClassification,
)
from chart_observatory.lyrics.classification_queue import ClassificationCandidate
from chart_observatory.lyrics.continuous import TECHNICAL_RESPONSE_ERRORS
from chart_observatory.lyrics.gemini_pipeline import build_lyrics_generation_config
from chart_observatory.lyrics.identity_quarantine import EXCLUDED_DECISIONS, load_quarantine_entries
from chart_observatory.lyrics.repository import AUTHORIZED_RIGHTS
from chart_observatory.lyrics.text_quality import TEXT_QUALITY_VERSION, prepare_lyric_derivative

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data/derived/lyrics/overnight-20261007/status.json"
POLICY_PATH = ROOT / "data/derived/lyrics/budget-20261008/billing-policy.json"
MODEL = "gemini-3.8-flash"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def policy_from_evidence(evidence: dict[str, Any]) -> BrlBudgetPolicy:
    return BrlBudgetPolicy(
        cap_brl=Decimal(evidence["cap_brl"]),
        ancillary_brl=Decimal(evidence["ancillary_reserve_brl"]),
        retry_reserve_brl=Decimal(evidence["retry_reserve_brl"]),
        billing_anchor_brl=Decimal(evidence["settled_cost_brl"]),
        covered_run_ids=frozenset(UUID(value) for value in evidence["settled_run_ids"]),
        billing_cutoff=datetime.fromisoformat(evidence["settled_cutoff_utc"]),
        project_id=evidence["project_id"],
        brl_per_ledger_usd=max(
            Decimal(evidence["input_brl_per_million"]) / Decimal("0.375"),
            Decimal(evidence["output_brl_per_million"]) / Decimal("1.875"),
        ),
        account_remaining_brl=Decimal(evidence["current_account_usable_credit_brl"]),
        account_baseline_run_ids=frozenset(
            UUID(value) for value in evidence["account_baseline_run_ids"]
        ),
    )


def windows_controller(pid: int | None) -> dict[str, Any] | None:
    if not pid:
        return None
    if os.name != "nt":
        raise RuntimeError("production handoff observation requires Windows")
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f'Get-CimInstance Win32_Process -Filter "ProcessId = {int(pid)}" | '
            "Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress",
        ],
        capture_output=True,
        text=True,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def live_rows(context: dict[str, Any], output: Path) -> Iterator[dict[str, Any]]:
    state_bytes = STATE_PATH.read_bytes()
    evidence_bytes = POLICY_PATH.read_bytes()
    state = json.loads(state_bytes)
    evidence = json.loads(evidence_bytes)
    (output / "observed-controller-state.json").write_bytes(state_bytes)
    (output / "observed-billing-policy.json").write_bytes(evidence_bytes)
    process = windows_controller(state.get("controller_pid"))
    context.update(
        {
            key: state.get(key)
            for key in (
                "execution_id",
                "status",
                "quality_hold",
                "controller_stop_requested",
                "preparation_in_progress",
                "controller_pid",
                "reanalysis_run_ids",
            )
        }
    )
    context.update(
        controller_alive=process is not None,
        windows_controller=process,
        input_brl_per_million=evidence["input_brl_per_million"],
        output_brl_per_million=evidence["output_brl_per_million"],
        pricing_valid_before_utc=evidence["pricing_valid_before_utc"],
        billing_observed_utc=evidence["observed_utc"],
        second_account_credit_verified=False,
    )
    settings = Settings.load(ROOT)
    if settings.gemini_model != MODEL or settings.google_cloud_project != evidence["project_id"]:
        raise ValueError("model or authenticated billing project mismatch")
    engine = create_engine(settings.database_url)
    if engine.url.host != "127.0.0.1" or engine.url.port != 56433:
        raise ValueError("requires PostgreSQL 16 at 127.0.0.1:56433")
    run_ids = state["retry_run_ids"]
    reanalysis_ids = state.get("reanalysis_run_ids", [])
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            if (
                not 160000
                <= int(connection.execute(text("SHOW server_version_num")).scalar_one())
                < 170000
            ):
                raise ValueError("requires PostgreSQL 16")
            context["snapshot_utc"] = str(
                connection.execute(text("SELECT transaction_timestamp()")).scalar()
            )
            ledger = list(
                connection.execute(
                    text("""
                SELECT id,state,request_count,imported_count,summary_written,
                  provider_job_name,job_error_code FROM lyric_classification_batch_runs
            """)
                ).mappings()
            )
            context["unreconciled_run_ids"] = [
                str(r["id"])
                for r in ledger
                if r["provider_job_name"]
                and (
                    not r["summary_written"]
                    or r["state"] in ("submitted", "running", "prepared", "uploaded")
                )
            ]
            context["failed_preparation_run_ids"] = [
                str(r["id"])
                for r in ledger
                if r["state"] == "failed"
                and not r["provider_job_name"]
                and not r["summary_written"]
            ]
            context["import_reconciliation_mismatches"] = [
                str(r["id"])
                for r in ledger
                if str(r["id"]) in run_ids
                and r["state"] in ("imported", "cleaned")
                and (not r["summary_written"] or r["imported_count"] != r["request_count"])
            ]
            context["pending_run_count"] = len(context["unreconciled_run_ids"])
            context["ambiguous_prepared_run_ids"] = [
                str(r["id"]) for r in ledger if r["state"] in ("prepared", "uploaded")
            ]
            query = text("""
                WITH latest AS (
                  SELECT DISTINCT ON (lyric_document_id) id,lyric_document_id,
                    canonical_track_id,lyrics_hash,classification_status,result_json,error,batch_run_id
                  FROM lyric_classification_snapshots WHERE model_id=:model
                    AND taxonomy_version=:taxonomy AND prompt_version=:prompt
                  ORDER BY lyric_document_id,append_order DESC
                ), attempts AS (
                  SELECT i.lyric_document_id,
                    count(*) FILTER (WHERE i.batch_run_id=ANY(CAST(:runs AS uuid[]))) AS attempts,
                    bool_or(i.batch_run_id=ANY(CAST(:reanalysis AS uuid[]))) AS prior_reanalysis,
                    bool_or(i.state IN ('reserved','submitted','running')
                      OR r.state IN ('prepared','uploaded','submitted','running'))
                      AS active_reservation,
                    bool_or(r.state IN ('prepared','uploaded')) AS ambiguous_submission
                  FROM lyric_classification_batch_items i
                  JOIN lyric_classification_batch_runs r ON r.id=i.batch_run_id
                  GROUP BY i.lyric_document_id
                )
                SELECT d.id AS document_id,d.canonical_track_id AS document_track_id,d.text,
                  d.content_sha256,d.source,d.rights_status,d.language_code,
                  s.id AS prior_snapshot_id,s.canonical_track_id,s.lyrics_hash,
                  s.classification_status,s.result_json,s.error,
                  coalesce(a.attempts,0) AS execution_attempts,
                  coalesce(a.prior_reanalysis,false) AS prior_reanalysis,
                  coalesce(a.active_reservation,false) AS active_reservation,
                  coalesce(a.ambiguous_submission,false) AS ambiguous_submission,
                  (r.job_error_code IS NOT NULL OR
                    (r.state IN ('failed','expired','cancelled') AND NOT r.summary_written))
                    AS global_job_failure
                FROM lyric_documents d LEFT JOIN latest s ON s.lyric_document_id=d.id
                LEFT JOIN attempts a ON a.lyric_document_id=d.id
                LEFT JOIN lyric_classification_batch_runs r ON r.id=s.batch_run_id
                ORDER BY d.id
            """)
            rows = (
                connection.execution_options(stream_results=True)
                .execute(
                    query,
                    {
                        "model": MODEL,
                        "taxonomy": TAXONOMY_VERSION,
                        "prompt": PROMPT_VERSION,
                        "runs": run_ids,
                        "reanalysis": reanalysis_ids,
                    },
                )
                .mappings()
            )
            for record in rows:
                row = dict(record)
                row["valid_result"] = False
                if row["classification_status"] == "classified":
                    try:
                        classified = LyricsClassification.model_validate(row["result_json"])
                        row["valid_result"] = (
                            classified.classification_status == "classified"
                            and row["canonical_track_id"] == row["document_track_id"]
                            and row["lyrics_hash"] == row["content_sha256"]
                        )
                    except ValidationError:
                        pass
                yield row
            rows.close()
            policy = policy_from_evidence(evidence)
            with Session(bind=connection) as session:
                total, account = policy.commitments(session)
                context.update(
                    committed_conservative_brl=str(total),
                    account_new_commitment_brl=str(account),
                    available_brl=str(
                        min(
                            policy.cap_brl
                            - total
                            - policy.ancillary_brl
                            - policy.retry_reserve_brl,
                            policy.account_remaining_brl
                            - account
                            - policy.ancillary_brl
                            - policy.retry_reserve_brl,
                        )
                    ),
                    retained_reserves_brl=str(policy.ancillary_brl + policy.retry_reserve_brl),
                )
                projected = Decimal(context["projected_pending_brl"])
                if projected > 0:
                    try:
                        policy.guard(
                            session, projected / policy.brl_per_ledger_usd, Decimal("3500")
                        )
                        context["brl_guard_observation"] = "passed_against_observed_policy_only"
                    except CostBudgetExceeded as error:
                        context["brl_guard_observation"] = str(error)
            after = json.loads(STATE_PATH.read_bytes())
            context["execution_state_changed"] = after.get("retry_run_ids") != run_ids or bool(
                after.get("preparation_in_progress")
            )
    finally:
        engine.dispose()


def run(input_path: Path | None, fixture_context: Path | None, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    reproduction = output / "reproducibility"
    reproduction.mkdir()
    code_hashes = {}
    for source_path in (
        Path(__file__),
        ROOT / "src/chart_observatory/lyrics/text_quality.py",
        ROOT / "src/chart_observatory/lyrics/batch_jsonl.py",
        ROOT / "src/chart_observatory/lyrics/brl_budget.py",
        ROOT / "src/chart_observatory/lyrics/classification.py",
        ROOT / "src/chart_observatory/lyrics/continuous.py",
        ROOT / "config/lyrics_identity_quarantine.json",
    ):
        content = source_path.read_bytes()
        (reproduction / source_path.name).write_bytes(content)
        code_hashes[source_path.name] = hashlib.sha256(content).hexdigest()
    context: dict[str, Any] = (
        json.loads(fixture_context.read_text(encoding="utf-8")) if fixture_context else {}
    )
    if bool(input_path) != bool(fixture_context):
        raise ValueError("local fixtures require both input-jsonl and fixture-context")
    if input_path:

        def fixture_rows() -> Iterator[dict[str, Any]]:
            with input_path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield json.loads(line)

        rows = fixture_rows()
    else:
        rows = live_rows(context, output)
    exclusions = {str(entry.lyric_document_id): entry for entry in load_quarantine_entries()}
    config = build_lyrics_generation_config(MODEL, "LOW", 1024)
    counts: Counter[str] = Counter()
    reasons_count: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    group_bytes: Counter[str] = Counter()
    expected: dict[str, dict[UUID, str]] = {"pending": {}, "corrected_reanalysis": {}}
    handles = {name: (output / f"{name}.requests.jsonl").open("xb") for name in expected}
    prices: dict[str, Decimal] = {}
    plan_id = uuid4()
    planned_run_ids = {name: str(uuid4()) for name in expected}
    started = datetime.now(UTC)
    try:
        with (output / "selection.jsonl").open("x", encoding="utf-8") as manifest:
            for row in rows:
                if not prices:
                    prices = {
                        "input": Decimal(context["input_brl_per_million"]),
                        "output": Decimal(context["output_brl_per_million"]),
                    }
                    if any(not value.is_finite() or value <= 0 for value in prices.values()):
                        raise ValueError("authenticated positive BRL SKU prices required")
                counts["documents_examined"] += 1
                doc = str(row["document_id"])
                derivative = prepare_lyric_derivative(row.get("text") or "", row["source"])
                reasons = []
                if derivative.original_sha256 != row["content_sha256"]:
                    reasons.append("stored_hash_mismatch")
                if row["rights_status"] not in AUTHORIZED_RIGHTS:
                    reasons.append("rights_unauthorized")
                entry = exclusions.get(doc)
                if entry and entry.decision in EXCLUDED_DECISIONS:
                    reasons.append("known_identity_exclusion")
                reasons.extend(flag for flag in derivative.flags if flag != "short_text")
                if row.get("active_reservation"):
                    reasons.append("active_reservation")
                if row.get("ambiguous_submission"):
                    reasons.append("ambiguous_submission")
                if row.get("global_job_failure"):
                    reasons.append("global_job_failure")
                group = None
                if row.get("valid_result"):
                    if derivative.changed:
                        group = "corrected_reanalysis"
                    else:
                        reasons.append("valid_result_reused")
                else:
                    if row.get("prior_reanalysis"):
                        reasons.append("prior_reanalysis_not_repeatable")
                    if int(row.get("execution_attempts", 0)) >= 2:
                        reasons.append("execution_attempt_limit")
                    if row.get("classification_status") not in (None, "error"):
                        reasons.append("nontechnical_outcome")
                    elif (
                        row.get("classification_status") == "error"
                        and row.get("error") not in TECHNICAL_RESPONSE_ERRORS
                    ):
                        reasons.append("error_not_in_technical_whitelist")
                    group = "pending"
                key = None
                future_document = (
                    UUID(doc)
                    if not derivative.changed
                    else uuid5(UUID(doc), TEXT_QUALITY_VERSION + ":" + derivative.derivative_sha256)
                )
                if group and not reasons:
                    key = uuid4()
                    item = LyricClassificationBatchItem(
                        opaque_key=key, lyric_document_id=future_document
                    )
                    candidate = ClassificationCandidate(
                        future_document,
                        UUID(str(row["document_track_id"])),
                        derivative.derivative_sha256,
                        derivative.text,
                        row.get("language_code"),
                        False,
                    )
                    payload = build_batch_request(item, candidate, config)
                    wire = (
                        json.dumps(
                            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                        ).encode("utf-8")
                        + b"\n"
                    )
                    handles[group].write(wire)
                    expected[group][key] = canonical_request_sha256(payload)
                    group_bytes[group] += len(wire)
                    group_counts[group] += 1
                    counts["corrected_requests"] += derivative.changed
                manifest.write(
                    json.dumps(
                        {
                            "original_document_id": doc,
                            "track_id": str(row["document_track_id"]),
                            "original_sha256": derivative.original_sha256,
                            "request_lyrics_sha256": derivative.derivative_sha256,
                            "planned_document_id": str(future_document),
                            "text_changed": derivative.changed,
                            "source": row["source"],
                            "rights_status": row["rights_status"],
                            "prior_snapshot_id": str(row["prior_snapshot_id"])
                            if row.get("prior_snapshot_id")
                            else None,
                            "execution_attempts": row.get("execution_attempts", 0),
                            "text_flags": derivative.flags,
                            "group": group if key else None,
                            "requested_group": group,
                            "opaque_key": str(key) if key else None,
                            "request_sha256": expected[group][key] if key and group else None,
                            "planned_run_id": planned_run_ids[group] if key and group else None,
                            "group_line_number": group_counts[group] if key and group else None,
                            "current_retry_policy_permits_spending": bool(
                                key and group == "pending"
                            ),
                            "reasons": sorted(set(reasons)),
                            "registered_in_ledger": False,
                            "submission_attempted": False,
                            "identity_verified": False,
                            "scientific_eligible": False,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                reasons_count.update(set(reasons))
                if prices:
                    context["projected_pending_brl"] = str(
                        (
                            Decimal(group_bytes["pending"]) * prices["input"]
                            + Decimal(group_counts["pending"] * 1024) * prices["output"]
                        )
                        / Decimal(1000000)
                    )
    finally:
        for handle in handles.values():
            handle.close()
    groups = {}
    for name in expected:
        path = output / f"{name}.requests.jsonl"
        content_hash = file_sha256(path)
        if group_counts[name]:
            artifact = validate_batch_jsonl(path, expected[name])
            if artifact.byte_count != group_bytes[name]:
                raise ValueError("verified JSONL bytes differ")
        reservation = (
            Decimal(group_bytes[name]) * prices.get("input", Decimal(0))
            + Decimal(group_counts[name] * 1024) * prices.get("output", Decimal(0))
        ) / Decimal(1000000)
        groups[name] = {
            "request_count": group_counts[name],
            "planned_run_id": planned_run_ids[name],
            "jsonl_bytes": group_bytes[name],
            "jsonl_sha256": content_hash,
            "conservative_reservation_brl": str(
                reservation.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
            ),
            "spending_authorized": False,
            "registered_or_uploaded": False,
            "purpose": name,
        }
    blockers = [
        "authenticated_credit_revalidation_required",
        "refresh_selection_after_current_run",
        "ledger_registration_required",
        "exclusive_controller_submission_required",
    ]
    if context.get("controller_alive"):
        blockers.append("controller_alive")
    if context.get("status") not in ("completed", "budget_exhausted"):
        blockers.append("current_execution_not_safely_completed")
    if context.get("quality_hold") or context.get("controller_stop_requested"):
        blockers.append("quality_or_stop_hold")
    if context.get("preparation_in_progress") or context.get("ambiguous_prepared_run_ids"):
        blockers.append("ambiguous_preparation_or_submission")
    if context.get("pending_run_count"):
        blockers.append("unreconciled_jobs")
    if context.get("failed_preparation_run_ids"):
        blockers.append("failed_preparation_history_requires_audit")
    if context.get("import_reconciliation_mismatches"):
        blockers.append("import_reconciliation_mismatch")
    if context.get("execution_state_changed"):
        blockers.append("execution_changed_during_planning")
    if datetime.now(UTC) >= datetime.fromisoformat(context["pricing_valid_before_utc"]):
        blockers.append("monthly_pricing_expired")
    if Decimal(context.get("available_brl", "0")) < Decimal(
        context.get("projected_pending_brl", "0")
    ):
        blockers.append("current_credit_reservation_insufficient")
    plan = {
        "plan_id": str(plan_id),
        "version": "lyrics-followup-plan-v1",
        "text_quality_version": TEXT_QUALITY_VERSION,
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(UTC).isoformat(),
        "groups": groups,
        "counts": dict(counts),
        "exclusion_counts": dict(reasons_count),
        "context": context,
        "ready_to_submit": False,
        "handoff_blockers": blockers,
        "model": MODEL,
        "thinking_level": "LOW",
        "max_output_tokens": 1024,
        "taxonomy_version": TAXONOMY_VERSION,
        "prompt_version": PROMPT_VERSION,
        "provider_calls": 0,
        "additional_api_cost_brl": "0",
        "second_account_counted_as_credit": False,
        "reauthorization_required_for_corrected_reanalysis": True,
        "requires_original_lineage_attempt_guard": True,
        "submission_attempted": False,
        "reproducibility_sha256": code_hashes,
        "selection_manifest_sha256": file_sha256(output / "selection.jsonl"),
    }
    (output / "plan.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path)
    parser.add_argument("--fixture-context", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    plan = run(args.input_jsonl, args.fixture_context, args.output_dir)
    print(
        json.dumps(
            {
                name: plan[name]
                for name in (
                    "plan_id",
                    "groups",
                    "counts",
                    "exclusion_counts",
                    "ready_to_submit",
                    "handoff_blockers",
                    "additional_api_cost_brl",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
