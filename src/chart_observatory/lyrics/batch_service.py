"""High-level, human-gated orchestration for Gemini lyric batch classification."""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

import google.auth
from google.auth.transport.requests import AuthorizedSession, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import exists, func, inspect, select
from sqlalchemy.orm import Session

from chart_observatory.db.models.corpus import LyricClassificationSnapshot, LyricDocument
from chart_observatory.db.models.lyrics_batch import (
    LyricClassificationBatchItem,
    LyricClassificationBatchRun,
)
from chart_observatory.lyrics.batch_contract import (
    BatchPreparation,
    BatchPreparationRequest,
    BatchRunKind,
    BatchRunState,
)
from chart_observatory.lyrics.batch_importer import BatchImporter, BatchImportSummary
from chart_observatory.lyrics.batch_jsonl import (
    BatchExportItem,
    PilotUsage,
    estimate_batch_cost,
    iter_batch_request_hashes,
    write_batch_jsonl,
)
from chart_observatory.lyrics.batch_quality import (
    HumanPilotReview,
    PilotQualityReport,
    build_pilot_quality_report,
)
from chart_observatory.lyrics.batch_repository import BatchRepository
from chart_observatory.lyrics.batch_storage import BatchStorageAdapter, StoredObject
from chart_observatory.lyrics.batch_vertex import (
    VertexBatchAdapter,
    VertexBatchJob,
    assert_adc_only_environment,
)
from chart_observatory.lyrics.classification import (
    PROMPT_VERSION,
    TAXONOMY_VERSION,
    CostRateCard,
)
from chart_observatory.lyrics.classification_queue import (
    ClassificationCandidate,
    ClassificationSignature,
    classification_queue_lock,
)
from chart_observatory.lyrics.gemini_pipeline import build_lyrics_generation_config

MAX_TOTAL_BATCH_COST_USD = Decimal("600")
BATCH_MAX_OUTPUT_TOKENS = 1024


class BatchSettings(Protocol):
    gemini_model: str | None
    google_cloud_project: str | None
    google_cloud_location: str
    gemini_thinking_level: Any
    gemini_batch_bucket: str | None
    gemini_batch_input_usd_per_million_tokens: Decimal | None
    gemini_batch_output_usd_per_million_tokens: Decimal | None


class TokenCounter(Protocol):
    def estimate_input_tokens(self, lyrics: str, language: str | None = None) -> int | None: ...


class CostBudgetExceeded(ValueError):
    """Raised before upload/submission when the cumulative budget cannot be honored."""


class PilotNotAccepted(RuntimeError):
    """Raised when main-corpus work is attempted before durable human acceptance."""


class BatchPreflightReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_id: str
    location: str
    thinking_level: str
    bucket_name: str
    adc_available: bool
    migration_ready: bool
    absolute_cost_cap_usd: Decimal


class BatchCleanupSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID
    deleted_objects: int
    state: str


class BatchRunStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID
    provider_job_name: str
    state: str
    request_count: int
    successful_count: int | None
    failed_count: int | None
    completed_count: int | None
    progress_percent: Decimal | None
    provider_error: str | None


def enforce_cumulative_cost_cap(
    session: Session,
    new_conservative_cost: Decimal,
    operator_cap: Decimal,
    *,
    exclude_run_id: UUID | None = None,
) -> Decimal:
    """Reserve against all known spend/active estimates under an absolute US$600 ceiling."""

    if operator_cap <= 0:
        raise CostBudgetExceeded("--max-cost-usd must be positive")
    if operator_cap > MAX_TOTAL_BATCH_COST_USD:
        raise CostBudgetExceeded("--max-cost-usd cannot exceed the absolute US$600 ceiling")
    if new_conservative_cost <= 0:
        raise CostBudgetExceeded("a positive conservative cost estimate is required")
    committed = Decimal(0)
    statement = select(LyricClassificationBatchRun)
    if exclude_run_id is not None:
        statement = statement.where(LyricClassificationBatchRun.id != exclude_run_id)
    for run in session.scalars(statement):
        known = Decimal(run.known_cost_usd or 0)
        conservative = Decimal(run.conservative_cost_usd or 0)
        finalized = run.state in {
            BatchRunState.SUCCEEDED.value,
            BatchRunState.IMPORTED.value,
            BatchRunState.CLEANED.value,
        } and run.summary_written
        if finalized:
            item_count = session.scalar(
                select(func.count())
                .select_from(LyricClassificationBatchItem)
                .where(LyricClassificationBatchItem.batch_run_id == run.id)
            )
            unreconciled_item = session.scalar(
                select(
                    exists().where(
                        LyricClassificationBatchItem.batch_run_id == run.id,
                        LyricClassificationBatchItem.snapshot_id.is_(None),
                    )
                )
            )
            unknown_cost_snapshot = session.scalar(
                select(
                    exists().where(
                        LyricClassificationBatchItem.batch_run_id == run.id,
                        LyricClassificationBatchItem.snapshot_id
                        == LyricClassificationSnapshot.id,
                        LyricClassificationSnapshot.batch_run_id == run.id,
                        LyricClassificationSnapshot.estimated_cost_usd.is_(None),
                    )
                )
            )
            if (
                item_count == run.request_count
                and not unreconciled_item
                and not unknown_cost_snapshot
            ):
                committed += known
                continue
        committed += max(known, conservative)
    total = committed + new_conservative_cost
    if total > operator_cap or total > MAX_TOTAL_BATCH_COST_USD:
        raise CostBudgetExceeded(
            f"cumulative conservative batch cost {total} exceeds the allowed ceiling"
        )
    return total


class BatchClassificationService:
    """Compose database, JSONL, GCS, Vertex, import, and quality gates."""

    def __init__(
        self,
        session: Session,
        settings: BatchSettings,
        storage: BatchStorageAdapter,
        vertex: VertexBatchAdapter,
        *,
        token_counter: TokenCounter | None = None,
        adc_check: Callable[[], None] | None = None,
        project_number_resolver: Callable[[str], str] | None = None,
        temporary_root: Path | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._vertex = vertex
        self._token_counter = token_counter
        self._adc_check = adc_check or _refresh_adc
        self._project_number_resolver = project_number_resolver or _resolve_project_number
        self._temporary_root = temporary_root
        self._repository = BatchRepository(session)

    def preflight(self) -> BatchPreflightReport:
        model_id, project_id, bucket_name, input_rate, output_rate = self._validated_settings()
        del input_rate, output_rate
        assert_adc_only_environment()
        self._adc_check()
        tables = set(inspect(self._session.get_bind()).get_table_names())
        required = {
            "lyric_classification_batch_runs",
            "lyric_classification_batch_items",
            "lyric_classification_snapshots",
        }
        if not required <= tables:
            raise RuntimeError("batch database migration 0015 is not applied")
        with classification_queue_lock(self._session):
            pass
        project_number = self._project_number_resolver(project_id)
        if not project_number.isdigit():
            raise RuntimeError("Google Cloud project number could not be resolved")
        vertex_service_agent = f"service-{project_number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
        self._storage.preflight(vertex_service_agent)
        return BatchPreflightReport(
            model_id=model_id,
            location=self._settings.google_cloud_location,
            thinking_level=str(
                getattr(
                    self._settings.gemini_thinking_level,
                    "value",
                    self._settings.gemini_thinking_level,
                )
            ),
            bucket_name=bucket_name,
            adc_available=True,
            migration_ready=True,
            absolute_cost_cap_usd=MAX_TOTAL_BATCH_COST_USD,
        )

    def prepare_canary(self, max_cost_usd: Decimal) -> list[BatchPreparation]:
        return self._prepare(BatchRunKind.CANARY, 1, max_cost_usd)

    def prepare_pilot(self, max_cost_usd: Decimal, total_size: int = 100) -> list[BatchPreparation]:
        if total_size != 100:
            raise ValueError("the scientific pilot total size is fixed at 100")
        canary = self._latest_imported_run(BatchRunKind.CANARY)
        if canary is None:
            raise PilotNotAccepted("a successfully imported canary is required")
        BatchImporter(self._session, self._rate_card()).assert_canary_contract(canary.id)
        return self._prepare(BatchRunKind.PILOT, total_size - 1, max_cost_usd)

    def prepare_main(self, max_cost_usd: Decimal) -> list[BatchPreparation]:
        if self._accepted_pilot() is None:
            raise PilotNotAccepted("the 100-item pilot has not been durably accepted")
        return self._prepare(BatchRunKind.MAIN, 190_000, max_cost_usd)

    def prepare_retry_errors(
        self,
        prior_run_id: UUID,
        max_cost_usd: Decimal,
        error_codes: frozenset[str] | None = None,
        limit: int | None = None,
        require_missing_usage: bool = False,
    ) -> list[BatchPreparation]:
        return self._prepare(
            BatchRunKind.ERROR_RETRY,
            limit,
            max_cost_usd,
            prior_run_id=prior_run_id,
            retry_error_codes=error_codes,
            retry_missing_usage=require_missing_usage,
        )

    def submit(self, run_id: UUID, max_cost_usd: Decimal) -> VertexBatchJob:
        run = self._repository.get_run(run_id)
        if run.state == BatchRunState.SUBMITTED.value and run.provider_job_name:
            return self._vertex.get(run.provider_job_name)
        if run.state != BatchRunState.UPLOADED.value:
            raise RuntimeError("only an uploaded run can be submitted")
        if run.conservative_cost_usd is None:
            raise CostBudgetExceeded("run has no conservative cost reservation")
        enforce_cumulative_cost_cap(
            self._session,
            Decimal(run.conservative_cost_usd),
            max_cost_usd,
            exclude_run_id=run.id,
        )
        self._storage.verify(self._stored_source(run))
        job = self._vertex.submit(run)
        run.provider_job_name = job.name
        run.state = job.state.value
        run.submitted_at = datetime.now(UTC)
        self._repository.mark_items(run.id, "submitted")
        self._session.commit()
        return job

    def status(self, run_id: UUID) -> BatchRunStatus:
        run = self._repository.get_run(run_id)
        if not run.provider_job_name:
            raise RuntimeError("run has not been submitted")
        job = self._vertex.get(run.provider_job_name)
        run.state = job.state.value
        run.provider_successful_count = job.successful_count
        run.provider_failed_count = job.failed_count
        run.job_error_message = job.provider_error
        if job.state in {
            BatchRunState.SUCCEEDED,
            BatchRunState.FAILED,
            BatchRunState.CANCELLED,
            BatchRunState.EXPIRED,
        }:
            run.terminal_at = datetime.now(UTC)
        self._session.commit()
        completed_count = None
        progress_percent = None
        if job.successful_count is not None or job.failed_count is not None:
            completed_count = min(
                run.request_count,
                (job.successful_count or 0) + (job.failed_count or 0),
            )
            progress_percent = (
                Decimal(completed_count) * Decimal(100) / Decimal(run.request_count)
                if run.request_count > 0
                else None
            )
        return BatchRunStatus(
            run_id=run.id,
            provider_job_name=job.name,
            state=job.state.value,
            request_count=run.request_count,
            successful_count=job.successful_count,
            failed_count=job.failed_count,
            completed_count=completed_count,
            progress_percent=progress_percent,
            provider_error=job.provider_error,
        )

    def import_results(self, run_id: UUID) -> BatchImportSummary:
        run = self._repository.get_run(run_id)
        if not run.output_uri_prefix:
            raise RuntimeError("run has no output prefix")
        prefix = _object_name(run.output_uri_prefix, run.bucket_name)
        output_objects = self._storage.object_names(prefix)
        if any(not name.startswith(prefix) for name in output_objects):
            raise RuntimeError("provider output escaped the recorded run prefix")
        run.output_object_names = sorted(output_objects)
        self._session.commit()
        summary = BatchImporter(self._session, self._rate_card()).import_available(
            run_id, self._storage.iter_lines(prefix)
        )
        durable_cost = self._session.scalar(
            select(func.sum(LyricClassificationSnapshot.estimated_cost_usd)).where(
                LyricClassificationSnapshot.batch_run_id == run_id
            )
        )
        run.known_cost_usd = Decimal(durable_cost) if durable_cost is not None else None
        if self._all_reconciled(run_id) and BatchRunState(run.state) in {
            BatchRunState.SUCCEEDED,
            BatchRunState.FAILED,
            BatchRunState.CANCELLED,
            BatchRunState.EXPIRED,
        }:
            run.state = BatchRunState.IMPORTED.value
            run.imported_at = datetime.now(UTC)
            run.summary_written = True
        self._session.commit()
        return summary

    def finalize(self, run_id: UUID) -> BatchImportSummary:
        summary = BatchImporter(self._session, self._rate_card()).finalize_missing(run_id)
        run = self._repository.get_run(run_id)
        run.imported_at = datetime.now(UTC)
        run.summary_written = True
        self._session.commit()
        return summary

    def quality_report(
        self,
        run_id: UUID,
        reviews: Sequence[HumanPilotReview] = (),
    ) -> PilotQualityReport:
        run = self._repository.get_run(run_id)
        canary = self._latest_imported_run(BatchRunKind.CANARY)
        run_ids = [run.id] if canary is None or run.kind == "canary" else [canary.id, run.id]
        return build_pilot_quality_report(self._session, run_ids, reviews)

    def accept_pilot(self, run_id: UUID, reviewer: str) -> PilotQualityReport:
        if not reviewer.strip():
            raise ValueError("pilot reviewer is required")
        run = self._repository.get_run(run_id)
        if run.kind != BatchRunKind.PILOT.value or run.state != BatchRunState.IMPORTED.value:
            raise PilotNotAccepted("only a fully imported pilot can be accepted")
        report = self.quality_report(run_id)
        if report.total_items != 100:
            raise PilotNotAccepted("canary plus pilot must contain exactly 100 snapshots")
        if report.validation_error_rate > Decimal("0.05"):
            raise PilotNotAccepted("pilot validation error rate exceeds 5%")
        run.pilot_accepted_at = datetime.now(UTC)
        run.pilot_accepted_by = reviewer.strip()
        self._session.commit()
        return report

    def cleanup(self, run_id: UUID) -> BatchCleanupSummary:
        run = self._repository.get_run(run_id)
        if run.state != BatchRunState.IMPORTED.value or not run.summary_written:
            raise RuntimeError("cleanup requires a reconciled imported run summary")
        if not self._all_reconciled(run_id):
            raise RuntimeError("cleanup cannot remove unreconciled artifacts")
        prefix = f"runs/{run.id}/"
        source_name = _object_name(run.source_uri or "", run.bucket_name)
        if run.output_object_names is None:
            raise RuntimeError("cleanup requires a recorded provider output object set")
        expected_objects = {source_name, *run.output_object_names}
        if any(
            not (name == source_name or name.startswith(f"{prefix}output/"))
            for name in expected_objects
        ):
            raise RuntimeError("recorded run prefix contains an unexpected object set")
        deleted = self._storage.cleanup_prefix(prefix, expected_objects)
        run.state = BatchRunState.CLEANED.value
        run.cleaned_at = datetime.now(UTC)
        self._session.commit()
        return BatchCleanupSummary(run_id=run.id, deleted_objects=deleted, state=run.state)

    def _prepare(
        self,
        kind: BatchRunKind,
        limit: int | None,
        max_cost_usd: Decimal,
        *,
        prior_run_id: UUID | None = None,
        retry_error_codes: frozenset[str] | None = None,
        retry_missing_usage: bool = False,
    ) -> list[BatchPreparation]:
        self.preflight()
        model_id, project_id, bucket_name, _, _ = self._validated_settings()
        request = BatchPreparationRequest(
            kind=kind,
            signature=ClassificationSignature(model_id, TAXONOMY_VERSION, PROMPT_VERSION),
            project_id=project_id,
            location="global",
            bucket_name=bucket_name,
            limit=limit,
            thinking_level="LOW",
        )
        with classification_queue_lock(self._session):
            run = (
                self._repository.prepare_retry_run(
                    prior_run_id,
                    request,
                    retry_error_codes,
                    request.limit,
                    retry_missing_usage,
                )
                if prior_run_id is not None
                else self._repository.prepare_run(request)
            )
            prepared_runs = [run]
            uploaded_objects: list[StoredObject] = []
            try:
                export_stream = self._iter_export_items(run.id)
                exact_exports: list[BatchExportItem] | None = None
                if kind in {BatchRunKind.CANARY, BatchRunKind.PILOT}:
                    exact_exports = list(export_stream)
                    exports: Sequence[BatchExportItem] | Iterator[BatchExportItem] = exact_exports
                else:
                    exports = export_stream
                with tempfile.TemporaryDirectory(
                    dir=str(self._temporary_root) if self._temporary_root else None
                ) as temporary:
                    artifacts = write_batch_jsonl(run.id, exports, Path(temporary))
                    exact_tokens = (
                        self._exact_tokens(exact_exports) if exact_exports is not None else None
                    )
                    shard_hashes = [
                        list(iter_batch_request_hashes(artifact.path)) for artifact in artifacts
                    ]
                    prepared_runs = self._repository.shard_run(
                        run.id,
                        [[key for key, _ in hashes] for hashes in shard_hashes],
                    )
                    pilot_usage = self._pilot_usage()
                    estimates = []
                    token_offset = 0
                    for artifact in artifacts:
                        artifact_tokens = None
                        if exact_tokens is not None:
                            artifact_tokens = exact_tokens[
                                token_offset : token_offset + artifact.request_count
                            ]
                            token_offset += artifact.request_count
                        estimates.append(
                            estimate_batch_cost(
                                [artifact],
                                artifact_tokens,
                                pilot_usage,
                                self._rate_card(),
                                BATCH_MAX_OUTPUT_TOKENS,
                            )
                        )
                    total_conservative = sum(
                        (value.conservative_cost_usd for value in estimates),
                        Decimal(0),
                    )
                    enforce_cumulative_cost_cap(
                        self._session,
                        total_conservative,
                        max_cost_usd,
                    )
                    preparations = []
                    for shard_run, artifact, hashes, estimate in zip(
                        prepared_runs, artifacts, shard_hashes, estimates, strict=True
                    ):
                        self._repository.record_request_hashes(shard_run.id, iter(hashes))
                        object_name = f"runs/{shard_run.id}/input.jsonl"
                        stored = self._storage.upload(artifact.path, object_name)
                        uploaded_objects.append(stored)
                        shard_run.source_uri = stored.uri
                        shard_run.source_generation = stored.generation
                        shard_run.source_sha256 = stored.sha256
                        shard_run.source_byte_count = stored.byte_count
                        shard_run.output_uri_prefix = (
                            f"gs://{bucket_name}/runs/{shard_run.id}/output/"
                        )
                        shard_run.expected_cost_usd = estimate.expected_cost_usd
                        shard_run.conservative_cost_usd = estimate.conservative_cost_usd
                        shard_run.state = BatchRunState.UPLOADED.value
                        preparations.append(
                            BatchPreparation(
                                run_id=shard_run.id,
                                request_count=shard_run.request_count,
                                source_uri=shard_run.source_uri,
                                expected_cost_usd=estimate.expected_cost_usd,
                                conservative_cost_usd=estimate.conservative_cost_usd,
                            )
                        )
                self._session.commit()
                return preparations
            except Exception:
                self._session.rollback()
                cleanup_errors = []
                for stored in uploaded_objects:
                    try:
                        self._storage.delete(stored)
                    except Exception as cleanup_error:
                        cleanup_errors.append(cleanup_error)
                for prepared_run in prepared_runs:
                    failed = self._repository.get_run(prepared_run.id)
                    failed.state = BatchRunState.FAILED.value
                    failed.job_error_code = "batch_preparation_failed"
                    self._repository.mark_items(
                        prepared_run.id,
                        "error",
                        "batch_preparation_failed_orphaned_object"
                        if cleanup_errors
                        else "batch_preparation_failed",
                    )
                if cleanup_errors:
                    prepared_runs[0].job_error_message = (
                        f"Uploaded input cleanup failed for {len(cleanup_errors)} object(s); "
                        "inspect this run prefix before retrying."
                    )
                self._session.commit()
                raise

    def _iter_export_items(self, run_id: UUID) -> Iterator[BatchExportItem]:
        rows = self._session.execute(
            select(LyricClassificationBatchItem, LyricDocument)
            .join(
                LyricDocument,
                LyricDocument.id == LyricClassificationBatchItem.lyric_document_id,
            )
            .where(LyricClassificationBatchItem.batch_run_id == run_id)
            .order_by(LyricClassificationBatchItem.line_number)
            .execution_options(yield_per=100)
        )
        config = build_lyrics_generation_config("gemini-3.8-flash", "LOW", BATCH_MAX_OUTPUT_TOKENS)
        for item, document in rows:
            if document.text is None:
                raise RuntimeError("reserved lyric document is unavailable")
            yield BatchExportItem(
                item=item,
                candidate=ClassificationCandidate(
                    lyric_document_id=document.id,
                    canonical_track_id=document.canonical_track_id,
                    lyrics_hash=document.content_sha256,
                    text=document.text,
                    language=document.language_code,
                    instrumental=(document.metadata_json or {}).get("instrumental") is True,
                ),
                config=config,
            )

    def _exact_tokens(self, exports: Sequence[BatchExportItem]) -> list[int]:
        if self._token_counter is None:
            raise RuntimeError("exact canary/pilot token counter is unavailable")
        values: list[int] = []
        for export in exports:
            value = self._token_counter.estimate_input_tokens(
                export.candidate.text or "", export.candidate.language
            )
            if value is None or value <= 0:
                raise RuntimeError("exact token estimate is unavailable")
            values.append(value)
        return values

    def _pilot_usage(self) -> list[PilotUsage]:
        rows = self._session.execute(
            select(LyricClassificationSnapshot, LyricClassificationBatchRun.source_byte_count)
            .join(
                LyricClassificationBatchRun,
                LyricClassificationBatchRun.id == LyricClassificationSnapshot.batch_run_id,
            )
            .where(
                LyricClassificationBatchRun.kind.in_(["canary", "pilot"]),
                LyricClassificationSnapshot.input_tokens.is_not(None),
                LyricClassificationSnapshot.output_tokens.is_not(None),
                LyricClassificationSnapshot.thought_tokens.is_not(None),
            )
        )
        values: list[PilotUsage] = []
        for snapshot, source_bytes in rows:
            run = self._session.get(LyricClassificationBatchRun, snapshot.batch_run_id)
            per_request_bytes = max(
                1, int(source_bytes or 0) // max(1, run.request_count if run else 1)
            )
            values.append(
                PilotUsage(
                    request_bytes=per_request_bytes,
                    input_tokens=int(snapshot.input_tokens or 0),
                    output_tokens=int(snapshot.output_tokens or 0),
                    thought_tokens=int(snapshot.thought_tokens or 0),
                )
            )
        return values

    def _validated_settings(self) -> tuple[str, str, str, Decimal, Decimal]:
        model_id = self._settings.gemini_model
        if model_id != "gemini-3.8-flash":
            raise ValueError("GEMINI_MODEL must be gemini-3.8-flash")
        if self._settings.google_cloud_location != "global":
            raise ValueError("GOOGLE_CLOUD_LOCATION must be global")
        thinking = str(
            getattr(
                self._settings.gemini_thinking_level, "value", self._settings.gemini_thinking_level
            )
        )
        if thinking != "LOW":
            raise ValueError("GEMINI_THINKING_LEVEL must be LOW")
        project_id = self._settings.google_cloud_project
        bucket_name = self._settings.gemini_batch_bucket
        input_rate = self._settings.gemini_batch_input_usd_per_million_tokens
        output_rate = self._settings.gemini_batch_output_usd_per_million_tokens
        if not project_id or not bucket_name:
            raise ValueError("Google Cloud project and GEMINI_BATCH_BUCKET are required")
        if input_rate is None or output_rate is None or input_rate <= 0 or output_rate <= 0:
            raise ValueError("positive Gemini batch rates are required")
        return model_id, project_id, bucket_name, input_rate, output_rate

    def _rate_card(self) -> CostRateCard:
        _, _, _, input_rate, output_rate = self._validated_settings()
        return CostRateCard(
            input_usd_per_million_tokens=input_rate,
            output_usd_per_million_tokens=output_rate,
            thought_usd_per_million_tokens=output_rate,
        )

    def _accepted_pilot(self) -> LyricClassificationBatchRun | None:
        return self._session.scalar(
            select(LyricClassificationBatchRun)
            .where(
                LyricClassificationBatchRun.kind == BatchRunKind.PILOT.value,
                LyricClassificationBatchRun.pilot_accepted_at.is_not(None),
                LyricClassificationBatchRun.pilot_accepted_by.is_not(None),
                LyricClassificationBatchRun.model_id == "gemini-3.8-flash",
                LyricClassificationBatchRun.taxonomy_version == TAXONOMY_VERSION,
                LyricClassificationBatchRun.prompt_version == PROMPT_VERSION,
            )
            .order_by(LyricClassificationBatchRun.pilot_accepted_at.desc())
        )

    def _latest_imported_run(self, kind: BatchRunKind) -> LyricClassificationBatchRun | None:
        return self._session.scalar(
            select(LyricClassificationBatchRun)
            .where(
                LyricClassificationBatchRun.kind == kind.value,
                LyricClassificationBatchRun.state.in_(
                    [BatchRunState.IMPORTED.value, BatchRunState.CLEANED.value]
                ),
                LyricClassificationBatchRun.model_id == "gemini-3.8-flash",
                LyricClassificationBatchRun.taxonomy_version == TAXONOMY_VERSION,
                LyricClassificationBatchRun.prompt_version == PROMPT_VERSION,
            )
            .order_by(LyricClassificationBatchRun.created_at.desc())
        )

    def _all_reconciled(self, run_id: UUID) -> bool:
        total = self._session.scalar(
            select(LyricClassificationBatchItem.opaque_key)
            .where(LyricClassificationBatchItem.batch_run_id == run_id)
            .limit(1)
        )
        if total is None:
            return False
        unresolved = self._session.scalar(
            select(LyricClassificationBatchItem.opaque_key)
            .where(
                LyricClassificationBatchItem.batch_run_id == run_id,
                LyricClassificationBatchItem.snapshot_id.is_(None),
            )
            .limit(1)
        )
        return unresolved is None

    @staticmethod
    def _stored_source(run: LyricClassificationBatchRun) -> StoredObject:
        if (
            not run.source_uri
            or run.source_generation is None
            or not run.source_sha256
            or run.source_byte_count is None
        ):
            raise RuntimeError("run source identity is incomplete")
        return StoredObject(
            uri=run.source_uri,
            name=_object_name(run.source_uri, run.bucket_name),
            generation=run.source_generation,
            sha256=run.source_sha256,
            byte_count=run.source_byte_count,
        )


def _object_name(uri: str, bucket_name: str) -> str:
    prefix = f"gs://{bucket_name}/"
    if not uri.startswith(prefix):
        raise RuntimeError("GCS URI is outside the configured private bucket")
    return uri.removeprefix(prefix)


def _refresh_adc() -> None:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())  # type: ignore[no-untyped-call]


def _resolve_project_number(project_id: str) -> str:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
    response = session.get(
        f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}",
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Google Cloud project-number lookup failed (HTTP {response.status_code})"
        )
    payload = response.json()
    project_number = payload.get("projectNumber") if isinstance(payload, dict) else None
    if not isinstance(project_number, str) or not project_number.isdigit():
        raise RuntimeError("Google Cloud project-number response was invalid")
    return project_number
