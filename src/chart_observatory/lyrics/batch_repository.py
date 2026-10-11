"""Transactional database adapter for batch run and item reservations."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from uuid import UUID, uuid4

from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session, aliased

from chart_observatory.db.models.corpus import LyricClassificationSnapshot, LyricDocument
from chart_observatory.db.models.lyrics_batch import (
    LyricClassificationBatchItem,
    LyricClassificationBatchRun,
)
from chart_observatory.lyrics.batch_contract import (
    BatchPreparationRequest,
    BatchRetryCandidate,
    BatchRunState,
    validate_run_transition,
)
from chart_observatory.lyrics.classification_queue import (
    ACTIVE_BATCH_ITEM_STATES,
    HANDLED_CLASSIFICATION_STATUSES,
    classification_queue_lock,
    iter_remaining_candidates,
    local_classification_status,
)
from chart_observatory.lyrics.identity_quarantine import (
    excluded_document_ids,
    load_quarantine_entries,
    load_suspended_sources,
)
from chart_observatory.lyrics.repository import (
    AUTHORIZED_RIGHTS,
    ClassificationSnapshotInput,
    append_classification_snapshot,
)


class BatchRepository:
    """Own atomic reservation and explicit run-state transitions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def prepare_run(self, request: BatchPreparationRequest) -> LyricClassificationBatchRun:
        if not request.project_id.strip() or not request.bucket_name.strip():
            raise ValueError("project and bucket are required")
        try:
            with classification_queue_lock(self._session):
                run = LyricClassificationBatchRun(
                    kind=request.kind.value,
                    state=BatchRunState.PREPARED.value,
                    model_id=request.signature.model_id,
                    taxonomy_version=request.signature.taxonomy_version,
                    prompt_version=request.signature.prompt_version,
                    thinking_level=request.thinking_level,
                    project_id=request.project_id,
                    location=request.location,
                    bucket_name=request.bucket_name,
                    request_count=0,
                )
                self._session.add(run)
                self._session.flush()
                provider_count = 0
                for candidate in iter_remaining_candidates(
                    self._session,
                    request.signature,
                    include_identity_holds=request.include_identity_holds,
                ):
                    local_status = local_classification_status(candidate)
                    if local_status is not None:
                        append_classification_snapshot(
                            self._session,
                            ClassificationSnapshotInput(
                                lyric_document_id=candidate.lyric_document_id,
                                canonical_track_id=candidate.canonical_track_id,
                                lyrics_hash=candidate.lyrics_hash,
                                model_id=request.signature.model_id,
                                taxonomy_version=request.signature.taxonomy_version,
                                prompt_version=request.signature.prompt_version,
                                classification_status=local_status,
                            ),
                        )
                        continue
                    provider_count += 1
                    self._session.add(
                        LyricClassificationBatchItem(
                            opaque_key=uuid4(),
                            batch_run_id=run.id,
                            line_number=provider_count,
                            lyric_document_id=candidate.lyric_document_id,
                            canonical_track_id=candidate.canonical_track_id,
                            lyrics_hash=candidate.lyrics_hash,
                            model_id=request.signature.model_id,
                            taxonomy_version=request.signature.taxonomy_version,
                            prompt_version=request.signature.prompt_version,
                            state="reserved",
                        )
                    )
                    if provider_count % 1_000 == 0:
                        self._session.flush()
                    if request.limit is not None and provider_count >= request.limit:
                        break
                if not provider_count:
                    self._session.delete(run)
                    self._session.commit()
                    raise ValueError("no provider-eligible lyrics remain")
                run.request_count = provider_count
                self._session.commit()
                return run
        except Exception:
            self._session.rollback()
            raise

    def get_run(self, run_id: UUID) -> LyricClassificationBatchRun:
        run = self._session.get(LyricClassificationBatchRun, run_id)
        if run is None:
            raise LookupError(f"batch run does not exist: {run_id}")
        return run

    def items(self, run_id: UUID) -> list[LyricClassificationBatchItem]:
        return list(self.iter_items(run_id))

    def iter_items(self, run_id: UUID) -> Iterator[LyricClassificationBatchItem]:
        yield from self._session.scalars(
            select(LyricClassificationBatchItem)
            .where(LyricClassificationBatchItem.batch_run_id == run_id)
            .order_by(LyricClassificationBatchItem.line_number)
        ).yield_per(1_000)

    def record_request_hashes(self, run_id: UUID, hashes: Iterable[tuple[UUID, str]]) -> None:
        batch: list[dict[str, object]] = []
        for key, request_hash in hashes:
            batch.append({"opaque_key": key, "request_sha256": request_hash})
            if len(batch) == 1_000:
                self._session.execute(update(LyricClassificationBatchItem), batch)
                batch.clear()
        if batch:
            self._session.execute(update(LyricClassificationBatchItem), batch)
        missing = self._session.scalar(
            select(LyricClassificationBatchItem.opaque_key)
            .where(
                LyricClassificationBatchItem.batch_run_id == run_id,
                LyricClassificationBatchItem.request_sha256.is_(None),
            )
            .limit(1)
        )
        if missing is not None:
            raise ValueError("not every reserved batch item received a request hash")

    def mark_items(self, run_id: UUID, state: str, error_code: str | None = None) -> None:
        self._session.execute(
            update(LyricClassificationBatchItem)
            .where(LyricClassificationBatchItem.batch_run_id == run_id)
            .values(state=state, error_code=error_code)
        )

    def shard_run(
        self, run_id: UUID, shard_keys: list[list[UUID]]
    ) -> list[LyricClassificationBatchRun]:
        run = self.get_run(run_id)
        if run.state != BatchRunState.PREPARED.value:
            raise ValueError("only a prepared run can be split")
        if not shard_keys or any(not keys for keys in shard_keys):
            raise ValueError("every batch shard must contain at least one key")
        flattened = [key for keys in shard_keys for key in keys]
        current = list(
            self._session.scalars(
                select(LyricClassificationBatchItem.opaque_key)
                .where(LyricClassificationBatchItem.batch_run_id == run_id)
                .order_by(LyricClassificationBatchItem.line_number)
            )
        )
        if flattened != current or len(set(flattened)) != len(flattened):
            raise ValueError("artifact shards do not exactly match the reserved item order")
        runs = [run]
        for keys in shard_keys[1:]:
            child = LyricClassificationBatchRun(
                kind=run.kind,
                state=BatchRunState.PREPARED.value,
                model_id=run.model_id,
                taxonomy_version=run.taxonomy_version,
                prompt_version=run.prompt_version,
                thinking_level=run.thinking_level,
                project_id=run.project_id,
                location=run.location,
                bucket_name=run.bucket_name,
                request_count=len(keys),
            )
            self._session.add(child)
            self._session.flush()
            runs.append(child)
        run.request_count = len(shard_keys[0])
        for target_run, keys in zip(runs, shard_keys, strict=True):
            updates = [
                {
                    "opaque_key": key,
                    "batch_run_id": target_run.id,
                    "line_number": line_number,
                }
                for line_number, key in enumerate(keys, start=1)
            ]
            for start in range(0, len(updates), 1_000):
                self._session.execute(
                    update(LyricClassificationBatchItem), updates[start : start + 1_000]
                )
        self._session.commit()
        return runs

    def transition(self, run_id: UUID, target: BatchRunState) -> LyricClassificationBatchRun:
        run = self.get_run(run_id)
        validate_run_transition(run.state, target)
        run.state = target.value
        self._session.commit()
        return run

    def error_retry_candidates(
        self,
        prior_run_id: UUID,
        allowed_error_codes: frozenset[str] | None = None,
        *,
        require_missing_usage: bool = False,
        include_identity_holds: bool = False,
    ) -> list[BatchRetryCandidate]:
        handled = aliased(LyricClassificationSnapshot)
        active = aliased(LyricClassificationBatchItem)
        statement = (
            select(LyricClassificationBatchItem, LyricClassificationSnapshot)
            .join(
                LyricClassificationSnapshot,
                LyricClassificationSnapshot.id == LyricClassificationBatchItem.snapshot_id,
            )
            .join(
                LyricDocument,
                LyricDocument.id == LyricClassificationBatchItem.lyric_document_id,
            )
            .where(
                LyricClassificationBatchItem.batch_run_id == prior_run_id,
                LyricClassificationSnapshot.classification_status == "error",
                LyricDocument.rights_status.in_(sorted(AUTHORIZED_RIGHTS)),
                ~exists(
                    select(handled.id).where(
                        handled.canonical_track_id
                        == LyricClassificationBatchItem.canonical_track_id,
                        handled.lyrics_hash == LyricClassificationBatchItem.lyrics_hash,
                        handled.model_id == LyricClassificationBatchItem.model_id,
                        handled.taxonomy_version == LyricClassificationBatchItem.taxonomy_version,
                        handled.prompt_version == LyricClassificationBatchItem.prompt_version,
                        handled.classification_status.in_(
                            [s for s in HANDLED_CLASSIFICATION_STATUSES if s != "error"]
                        ),
                    )
                ),
                ~exists(
                    select(active.opaque_key).where(
                        active.canonical_track_id
                        == LyricClassificationBatchItem.canonical_track_id,
                        active.lyrics_hash == LyricClassificationBatchItem.lyrics_hash,
                        active.model_id == LyricClassificationBatchItem.model_id,
                        active.taxonomy_version == LyricClassificationBatchItem.taxonomy_version,
                        active.prompt_version == LyricClassificationBatchItem.prompt_version,
                        active.state.in_(ACTIVE_BATCH_ITEM_STATES),
                    )
                ),
                ~exists(
                    select(1)
                    .select_from(LyricClassificationBatchItem)
                    .join(
                        LyricClassificationBatchRun,
                        LyricClassificationBatchRun.id == LyricClassificationBatchItem.batch_run_id,
                    )
                    .where(
                        LyricClassificationBatchItem.retry_of_snapshot_id
                        == LyricClassificationSnapshot.id,
                        LyricClassificationBatchRun.job_error_code.is_distinct_from(
                            "batch_preparation_failed"
                        ),
                    )
                ),
            )
            .order_by(LyricClassificationBatchItem.line_number)
        )
        excluded_ids = excluded_document_ids(load_quarantine_entries())
        if excluded_ids and not include_identity_holds:
            statement = statement.where(LyricDocument.id.not_in(excluded_ids))
        if allowed_error_codes is not None:
            if not allowed_error_codes:
                return []
            statement = statement.where(
                LyricClassificationSnapshot.error.in_(sorted(allowed_error_codes))
            )
        if require_missing_usage:
            statement = statement.where(LyricClassificationSnapshot.input_tokens.is_(None))
        suspended_sources = load_suspended_sources()
        if suspended_sources and not include_identity_holds:
            statement = statement.where(
                func.upper(LyricDocument.source).not_in(sorted(suspended_sources))
            )
        rows = self._session.execute(statement)
        return [BatchRetryCandidate(item.lyric_document_id, snapshot.id) for item, snapshot in rows]

    def prepare_retry_run(
        self,
        prior_run_id: UUID,
        request: BatchPreparationRequest,
        allowed_error_codes: frozenset[str] | None = None,
        limit: int | None = None,
        require_missing_usage: bool = False,
    ) -> LyricClassificationBatchRun:
        candidates = self.error_retry_candidates(
            prior_run_id,
            allowed_error_codes,
            require_missing_usage=require_missing_usage,
            include_identity_holds=request.include_identity_holds,
        )
        if limit is not None:
            if limit < 1:
                raise ValueError("retry limit must be positive")
            candidates = candidates[:limit]
        if not candidates:
            raise ValueError("the prior run has no error snapshots to retry")
        try:
            with classification_queue_lock(self._session):
                run = LyricClassificationBatchRun(
                    kind=request.kind.value,
                    state=BatchRunState.PREPARED.value,
                    model_id=request.signature.model_id,
                    taxonomy_version=request.signature.taxonomy_version,
                    prompt_version=request.signature.prompt_version,
                    thinking_level=request.thinking_level,
                    project_id=request.project_id,
                    location=request.location,
                    bucket_name=request.bucket_name,
                    request_count=len(candidates),
                )
                self._session.add(run)
                self._session.flush()
                for line_number, candidate in enumerate(candidates, start=1):
                    document = self._session.get(LyricDocument, candidate.lyric_document_id)
                    if document is None:
                        raise ValueError("retry lyric document no longer exists")
                    self._session.add(
                        LyricClassificationBatchItem(
                            opaque_key=uuid4(),
                            batch_run_id=run.id,
                            line_number=line_number,
                            lyric_document_id=document.id,
                            canonical_track_id=document.canonical_track_id,
                            lyrics_hash=document.content_sha256,
                            model_id=request.signature.model_id,
                            taxonomy_version=request.signature.taxonomy_version,
                            prompt_version=request.signature.prompt_version,
                            state="reserved",
                            retry_of_snapshot_id=candidate.prior_snapshot_id,
                        )
                    )
                self._session.commit()
                return run
        except Exception:
            self._session.rollback()
            raise
