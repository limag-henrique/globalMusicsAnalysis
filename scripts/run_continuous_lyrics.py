"""Exclusive local coordinator; paid generation remains in Vertex Batch."""

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from chart_observatory.config import Settings
from chart_observatory.db.models.corpus import LyricClassificationSnapshot
from chart_observatory.db.models.lyrics_batch import (
    LyricClassificationBatchItem,
    LyricClassificationBatchRun,
)
from chart_observatory.lyrics.batch_repository import BatchRepository
from chart_observatory.lyrics.batch_service import (
    BatchClassificationService,
)
from chart_observatory.lyrics.batch_storage import BatchStorageAdapter
from chart_observatory.lyrics.batch_vertex import VertexBatchAdapter
from chart_observatory.lyrics.brl_budget import BrlBudgetPolicy
from chart_observatory.lyrics.classification import PROMPT_VERSION, TAXONOMY_VERSION
from chart_observatory.lyrics.classification_queue import (
    ClassificationSignature,
    iter_remaining_candidates,
    local_classification_status,
)
from chart_observatory.lyrics.continuous import (
    TECHNICAL_RESPONSE_ERRORS,
    ContinuityError,
    ContinuousBatchController,
    ContinuousRun,
    exclusive_controller_lock,
)
from chart_observatory.lyrics.gemini_pipeline import GeminiLyricsClassifier

# Canonical USD ledger estimates are converted by account SKU prices in the BRL guard.
# This argument is retained for the batch API; it does not authorize any USD ceiling.
CAP = Decimal("3500")
CODES = TECHNICAL_RESPONSE_ERRORS


class VertexContinuousBackend:
    def __init__(self, session: Session, settings: Settings, state: dict[str, Any]) -> None:
        self.session = session
        self.state = state
        evidence = json.loads(
            Path("data/derived/lyrics/budget-20261008/billing-policy.json").read_text(
                encoding="utf-8"
            )
        )
        if datetime.now(UTC) >= datetime.fromisoformat(evidence["pricing_valid_before_utc"]):
            raise ContinuityError("account BRL prices require monthly revalidation")
        self.policy = BrlBudgetPolicy(
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
        if (
            settings.google_cloud_project != self.policy.project_id
            or settings.gemini_batch_input_usd_per_million_tokens != Decimal("0.375")
            or settings.gemini_batch_output_usd_per_million_tokens != Decimal("1.875")
        ):
            raise ContinuityError("billing policy and canonical rate card differ")
        if (
            not settings.google_cloud_project
            or not settings.gemini_batch_bucket
            or not settings.gemini_model
        ):
            raise ContinuityError("missing batch configuration")
        self.service = BatchClassificationService(
            session,
            settings,
            BatchStorageAdapter.from_adc(
                settings.google_cloud_project, settings.gemini_batch_bucket
            ),
            VertexBatchAdapter(settings.google_cloud_project, settings.google_cloud_location),
            token_counter=GeminiLyricsClassifier(
                settings.google_cloud_project,
                settings.google_cloud_location,
                settings.gemini_model,
                thinking_level=settings.gemini_thinking_level,
                max_output_tokens=1024,
            ),
            cost_guard=self.policy.guard,
            include_identity_holds=True,
        )
        self.repository = BatchRepository(session)

    def runs(self, ids: list[str]) -> list[ContinuousRun]:
        self.session.expire_all()
        result = []
        for value in ids:
            run = self.repository.get_run(UUID(value))
            result.append(
                ContinuousRun(
                    value,
                    run.state,
                    run.request_count,
                    (run.provider_successful_count or 0) + (run.provider_failed_count or 0)
                    if run.provider_successful_count is not None
                    or run.provider_failed_count is not None
                    else None,
                    run.provider_job_name,
                )
            )
        return result

    def refresh(self, run_id: str) -> ContinuousRun:
        report = self.service.status(UUID(run_id))
        if self.state.get("latest_run_id") == run_id:
            self.state.update(
                retry_run_state=report.state,
                completed_count=report.completed_count,
                progress_percent=str(report.progress_percent)
                if report.progress_percent is not None
                else None,
            )
        return ContinuousRun(
            run_id,
            report.state,
            report.request_count,
            report.completed_count,
            report.provider_job_name,
        )

    def reconcile(self, run_id: str) -> None:
        self.service.import_results(UUID(run_id))
        if self.repository.get_run(UUID(run_id)).state != "imported":
            self.service.finalize(UUID(run_id))
        counts = {
            status: count
            for status, count in self.session.execute(
                select(LyricClassificationSnapshot.classification_status, func.count())
                .where(LyricClassificationSnapshot.batch_run_id == UUID(run_id))
                .group_by(LyricClassificationSnapshot.classification_status)
            )
        }
        summary = self.state.setdefault("run_summaries", {}).setdefault(run_id, {})
        run = self.repository.get_run(UUID(run_id))
        summary.update(
            state=run.state,
            classified=counts.get("classified", 0),
            errors=counts.get("error", 0),
            known_cost_usd=str(run.known_cost_usd),
            status_counts=counts,
        )
        if self.state.get("latest_run_id") == run_id:
            self.state.update(
                retry_run_state=run.state,
                completed_count=sum(counts.values()),
                progress_percent="100" if sum(counts.values()) == run.request_count else None,
            )

    def budget(self) -> tuple[Decimal, Decimal]:
        remaining = self.policy.remaining_ledger_usd(self.session)
        total_brl, account_new_brl = self.policy.commitments(self.session)
        ids = [UUID(value) for value in self.state["retry_run_ids"]]
        costs = [
            Decimal(run.conservative_cost_usd) / run.request_count
            for run in self.session.scalars(
                select(LyricClassificationBatchRun).where(LyricClassificationBatchRun.id.in_(ids))
            )
            if run.request_count and run.conservative_cost_usd and run.conservative_cost_usd > 0
        ]
        if not costs:
            costs = [Decimal("0.004")]
        known = self.session.scalar(select(func.sum(LyricClassificationBatchRun.known_cost_usd)))
        counts = Counter(
            {
                status: count
                for status, count in self.session.execute(
                    select(LyricClassificationSnapshot.classification_status, func.count())
                    .where(LyricClassificationSnapshot.batch_run_id.in_(ids))
                    .group_by(LyricClassificationSnapshot.classification_status)
                )
            }
        )
        submitted_count = self.session.scalar(
            select(func.sum(LyricClassificationBatchRun.request_count)).where(
                LyricClassificationBatchRun.id.in_(ids),
                LyricClassificationBatchRun.provider_job_name.is_not(None),
            )
        )
        self.state.update(
            committed_conservative_brl=str(total_brl),
            current_account_new_commitment_brl=str(account_new_brl),
            conservative_remaining_brl=str(remaining * self.policy.brl_per_ledger_usd),
            financial_currency="BRL",
            absolute_cap_brl="3500",
            known_batch_usd=str(known or 0),
            remaining_ledger_usd=str(remaining),
            night_status_counts=dict(counts),
            night_submitted_count=submitted_count or 0,
            night_imported_classified_count=counts["classified"],
            night_imported_error_count=counts["error"],
            imported_classified_count=counts["classified"],
            imported_errors=counts["error"],
        )
        return remaining, max(costs)

    def candidate_prefix(self, baseline: str, excluded_runs: list[str]) -> int:
        if baseline == "bounded_reanalysis":
            reanalysis_runs = set(self.state.get("reanalysis_run_ids", []))
            for prior in excluded_runs:
                if prior in reanalysis_runs:
                    continue
                candidates = self.repository.error_retry_candidates(
                    UUID(prior),
                    CODES,
                    include_identity_holds=True,
                )
                if candidates:
                    self.state["reanalysis_prior_run_id"] = prior
                    return len(candidates)
            return 0
        if baseline == "remaining_corpus":
            signature = ClassificationSignature(
                "gemini-3.8-flash", TAXONOMY_VERSION, PROMPT_VERSION
            )
            return sum(
                local_classification_status(candidate) is None
                for candidate in iter_remaining_candidates(
                    self.session, signature, include_identity_holds=True
                )
            )
        attempted = set(
            self.session.scalars(
                select(LyricClassificationBatchItem.lyric_document_id).where(
                    LyricClassificationBatchItem.batch_run_id.in_(
                        [UUID(value) for value in excluded_runs]
                    )
                )
            )
        )
        candidates = self.repository.error_retry_candidates(
            UUID(baseline), CODES, include_identity_holds=True
        )
        prefix = 0
        for item in candidates:
            if item.lyric_document_id in attempted:
                break
            prefix += 1
        return prefix

    def prepare(self, baseline: str, limit: int) -> list[ContinuousRun]:
        attempted = set(
            self.session.scalars(
                select(LyricClassificationBatchItem.lyric_document_id).where(
                    LyricClassificationBatchItem.batch_run_id.in_(
                        [UUID(value) for value in self.state["retry_run_ids"]]
                    )
                )
            )
        )
        prior = (
            self.state.get("reanalysis_prior_run_id")
            if baseline == "bounded_reanalysis"
            else baseline
        )
        prepared = (
            self.service.prepare_main(CAP, limit)
            if baseline == "remaining_corpus"
            else self.service.prepare_retry_errors(UUID(prior), CAP, CODES, limit, False)
        )
        documents = list(
            self.session.scalars(
                select(LyricClassificationBatchItem.lyric_document_id).where(
                    LyricClassificationBatchItem.batch_run_id.in_([run.run_id for run in prepared])
                )
            )
        )
        if len(documents) != len(set(documents)) or (
            baseline != "bounded_reanalysis" and attempted.intersection(documents)
        ):
            raise ContinuityError("candidate overlap detected before submission")
        if baseline == "bounded_reanalysis":
            counts = {
                document: count
                for document, count in self.session.execute(
                    select(LyricClassificationBatchItem.lyric_document_id, func.count())
                    .where(
                        LyricClassificationBatchItem.batch_run_id.in_(
                            [UUID(value) for value in self.state["retry_run_ids"]]
                        ),
                        LyricClassificationBatchItem.lyric_document_id.in_(documents),
                    )
                    .group_by(LyricClassificationBatchItem.lyric_document_id)
                ).all()
            }
            if any(counts.get(document, 0) != 1 for document in documents):
                raise ContinuityError("bounded reanalysis requires exactly one preceding attempt")
            self.state.setdefault("reanalysis_run_ids", []).extend(
                str(run.run_id) for run in prepared
            )
        return [ContinuousRun(str(run.run_id), "uploaded", run.request_count) for run in prepared]

    def submit(self, run_id: str) -> ContinuousRun:
        job = self.service.submit(UUID(run_id), CAP)
        run = self.repository.get_run(UUID(run_id))
        return ContinuousRun(run_id, job.state.value, run.request_count, provider_job_name=job.name)


def write_state(path: Path, state: dict[str, Any]) -> None:
    # An independent stop marker survives concurrent checkpoint replacement.
    if path.with_name("controller.stop").exists():
        state["controller_stop_requested"] = True
    state.update(
        timestamp_utc=datetime.now(UTC).isoformat(),
        controller_heartbeat_utc=datetime.now(UTC).isoformat(),
    )
    temporary = path.with_suffix(".continuous.tmp")
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    # Windows readers may briefly omit FILE_SHARE_DELETE. Retry only the local
    # atomic replacement; never replay preparation or submission on this error.
    for attempt in range(6):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.1 * (2**attempt))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one coordinator tick")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--max-inflight", type=int, default=4)
    args = parser.parse_args()
    if args.poll_seconds < 15 or not 1 <= args.max_inflight <= 4:
        parser.error("poll-seconds >= 15 and max-inflight between 1 and 4 required")
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    path = root / "data/derived/lyrics/overnight-20261007/status.json"
    settings = Settings.load(root)
    url = make_url(settings.database_url)
    if url.host != "127.0.0.1" or url.port != 56433:
        raise ContinuityError("unexpected database endpoint")
    with exclusive_controller_lock(path.with_name("continuous.lock")) as acquired:
        if not acquired:
            print("Continuous coordinator already running")
            return
        coordinate(
            path,
            settings,
            poll_seconds=args.poll_seconds,
            max_inflight=args.max_inflight,
            once=args.once,
        )


def coordinate(
    path: Path, settings: Settings, *, poll_seconds: int, max_inflight: int, once: bool
) -> None:
    engine = create_engine(settings.database_url)
    try:
        while True:
            state = json.loads(path.read_text(encoding="utf-8"))
            if state.get("status") in {"failed", "stopped", "budget_exhausted", "completed"}:
                raise SystemExit("Saved execution is stopped; inspect before resuming")
            if state.get("controller_stop_requested"):
                state.update(status="stopped", stop_reason="controller_stop_requested")
                write_state(path, state)
                break
            state.update(
                controller_pid=os.getpid(),
                execution_mode="continuous",
                controller_poll_seconds=poll_seconds,
                max_inflight_jobs=max_inflight,
            )
            with Session(engine) as session:
                try:
                    backend = VertexContinuousBackend(session, settings, state)
                    controller = ContinuousBatchController(
                        backend,
                        lambda value: write_state(path, value),
                        max_inflight=max_inflight,
                    )
                    keep_running = controller.tick(state)
                    backend.budget()
                    write_state(path, state)
                except Exception as error:
                    session.rollback()
                    state.update(
                        status="failed",
                        stop_reason="continuous_controller_requires_inspection",
                        controller_error_type=type(error).__name__,
                    )
                    write_state(path, state)
                    raise SystemExit(
                        "Continuous coordinator stopped; inspect durable state"
                    ) from None
            if once or not keep_running:
                break
            time.sleep(poll_seconds)
        if not once:
            audit_directory = "data/derived/research_quality/" + datetime.now(UTC).strftime(
                "%Y%m%d-%H%M%S"
            )
            subprocess.run(
                [
                    sys.executable,
                    "scripts/audit_research_quality.py",
                    "--output-dir",
                    audit_directory,
                ],
                check=True,
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
