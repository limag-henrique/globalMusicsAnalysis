"""Streaming reconciliation of Vertex batch output into immutable snapshots."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from chart_observatory.db.models.corpus import LyricClassificationSnapshot
from chart_observatory.db.models.lyrics_batch import (
    LyricClassificationBatchItem,
    LyricClassificationBatchRun,
)
from chart_observatory.lyrics.batch_contract import BatchRunState
from chart_observatory.lyrics.batch_jsonl import canonical_request_sha256
from chart_observatory.lyrics.classification import (
    ClassificationStatus,
    CostRateCard,
    LyricsClassification,
    UsageTelemetry,
)
from chart_observatory.lyrics.repository import (
    ClassificationSnapshotInput,
    append_classification_snapshot,
)


class BatchIntegrityError(RuntimeError):
    """Raised when output cannot be safely associated with the recorded input."""


@dataclass(slots=True)
class BatchImportSummary:
    processed: int = 0
    classified: int = 0
    ambiguous: int = 0
    blocked: int = 0
    language_unsupported: int = 0
    insufficient_text: int = 0
    instrumental: int = 0
    errors: int = 0
    duplicates: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thought_tokens: int = 0
    total_tokens: int = 0
    known_cost_usd: Decimal | None = None


class BatchImporter:
    """Import one row at a time; item failures are durable and do not stop siblings."""

    def __init__(self, session: Session, rate_card: CostRateCard) -> None:
        self._session = session
        self._rate_card = rate_card

    def import_available(self, run_id: UUID, lines: Iterable[bytes]) -> BatchImportSummary:
        run = self._run(run_id)
        summary = BatchImportSummary()
        seen: set[UUID] = set()
        pending_rows = 0
        for raw_line in lines:
            try:
                payload = json.loads(raw_line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._fail_run(run, "batch_malformed_output_line")
                raise BatchIntegrityError("malformed output line") from exc
            if not isinstance(payload, dict):
                self._fail_run(run, "batch_malformed_output_line")
                raise BatchIntegrityError("malformed output line")
            key = self._parse_key(payload, run)
            if key in seen:
                self._fail_run(run, "batch_duplicate_output_key")
                raise BatchIntegrityError("duplicate output key")
            seen.add(key)
            item = self._session.get(LyricClassificationBatchItem, key)
            if item is None or item.batch_run_id != run_id:
                self._fail_run(run, "batch_unknown_output_key")
                raise BatchIntegrityError("unknown output key")
            if item.snapshot_id is not None:
                summary.duplicates += 1
                continue
            request = payload.get("request")
            envelope: dict[str, object] = {"request": request}
            if (
                not isinstance(request, dict)
                or item.request_sha256 is None
                or canonical_request_sha256(envelope) != item.request_sha256
            ):
                self._persist_error(run, item, "batch_request_fingerprint_mismatch")
                self._fail_run(run, "batch_request_fingerprint_mismatch")
                raise BatchIntegrityError("request fingerprint mismatch")
            try:
                self._import_row(run, item, payload, summary)
                pending_rows += 1
                if pending_rows == 100:
                    self._session.commit()
                    pending_rows = 0
            except BatchIntegrityError:
                self._session.rollback()
                raise
            except Exception:
                self._session.rollback()
                raise
        if pending_rows:
            self._session.commit()
        return summary

    def finalize_missing(self, run_id: UUID) -> BatchImportSummary:
        run = self._run(run_id)
        if BatchRunState(run.state) is BatchRunState.IMPORTED:
            return BatchImportSummary()
        if BatchRunState(run.state) not in {
            BatchRunState.SUCCEEDED,
            BatchRunState.FAILED,
            BatchRunState.CANCELLED,
            BatchRunState.EXPIRED,
        }:
            raise BatchIntegrityError("missing output can only be finalized for terminal jobs")
        summary = BatchImportSummary()
        for item in self._items(run_id):
            if item.snapshot_id is not None:
                continue
            self._persist_error(run, item, "batch_missing_output", state="missing")
            summary.processed += 1
            summary.errors += 1
            self._session.commit()
        run.state = BatchRunState.IMPORTED.value
        self._session.commit()
        return summary

    def assert_canary_contract(self, run_id: UUID) -> None:
        run = self._run(run_id)
        items = self._items(run_id)
        if run.kind != "canary" or run.request_count != 1 or len(items) != 1:
            raise BatchIntegrityError("canary must contain exactly one request")
        item = items[0]
        snapshot = (
            self._session.get(LyricClassificationSnapshot, item.snapshot_id)
            if item.snapshot_id
            else None
        )
        if (
            item.request_sha256 is None
            or snapshot is None
            or snapshot.classification_status == "error"
            or snapshot.batch_item_key != item.opaque_key
            or not (snapshot.provider_model_version or "").startswith(run.model_id)
        ):
            raise BatchIntegrityError("canary contract was not satisfied")

    def _import_row(
        self,
        run: LyricClassificationBatchRun,
        item: LyricClassificationBatchItem,
        payload: dict[str, Any],
        summary: BatchImportSummary,
    ) -> None:
        status = payload.get("status")
        if status:
            self._persist_error(run, item, "batch_provider_error")
            summary.processed += 1
            summary.errors += 1
            return
        response = payload.get("response")
        if not isinstance(response, dict):
            self._record_validation_error(run, item, summary, "batch_malformed_response")
            return
        usage = _usage_from_response(response)
        if usage is None:
            self._record_validation_error(run, item, summary, "batch_missing_usage")
            return
        candidates = response.get("candidates")
        candidate = candidates[0] if isinstance(candidates, list) and len(candidates) == 1 else None
        if not isinstance(candidate, dict):
            self._record_validation_error(run, item, summary, "batch_malformed_response", usage)
            return
        finish_reason = str(candidate.get("finishReason", "")).upper()
        if finish_reason in {
            "SAFETY",
            "RECITATION",
            "BLOCKLIST",
            "PROHIBITED_CONTENT",
            "SPII",
        }:
            self._persist_snapshot(run, item, "blocked", None, usage, "batch_safety_block")
            _add_summary(summary, "blocked", usage, self._rate_card)
            return
        if finish_reason != "STOP":
            self._record_validation_error(run, item, summary, "batch_incomplete_response", usage)
            return
        text_value = _candidate_text(candidate)
        if text_value is None:
            self._record_validation_error(run, item, summary, "batch_malformed_response", usage)
            return
        try:
            result = LyricsClassification.model_validate_json(text_value)
        except ValidationError:
            self._record_validation_error(
                run, item, summary, "batch_schema_validation_error", usage
            )
            return
        status_value = result.classification_status.value
        allowed_statuses = {
            status.value
            for status in ClassificationStatus
            if status is not ClassificationStatus.ERROR
        }
        if status_value not in allowed_statuses:
            self._record_validation_error(
                run, item, summary, "batch_invalid_provider_status", usage
            )
            return
        model_version = response.get("modelVersion")
        self._persist_snapshot(
            run,
            item,
            status_value,
            result,
            usage,
            None,
            str(model_version) if model_version else None,
        )
        _add_summary(summary, status_value, usage, self._rate_card)

    def _record_validation_error(
        self,
        run: LyricClassificationBatchRun,
        item: LyricClassificationBatchItem,
        summary: BatchImportSummary,
        code: str,
        usage: UsageTelemetry | None = None,
    ) -> None:
        self._persist_snapshot(run, item, "error", None, usage, code)
        _add_summary(summary, "error", usage, self._rate_card)

    def _persist_error(
        self,
        run: LyricClassificationBatchRun,
        item: LyricClassificationBatchItem,
        code: str,
        *,
        state: str = "error",
    ) -> None:
        self._persist_snapshot(run, item, "error", None, None, code, item_state=state)

    def _persist_snapshot(
        self,
        run: LyricClassificationBatchRun,
        item: LyricClassificationBatchItem,
        status: str,
        result: LyricsClassification | None,
        usage: UsageTelemetry | None,
        error: str | None,
        provider_model_version: str | None = None,
        *,
        item_state: str = "imported",
    ) -> LyricClassificationSnapshot:
        row = append_classification_snapshot(
            self._session,
            ClassificationSnapshotInput(
                lyric_document_id=item.lyric_document_id,
                canonical_track_id=item.canonical_track_id,
                lyrics_hash=item.lyrics_hash,
                model_id=item.model_id,
                taxonomy_version=item.taxonomy_version,
                prompt_version=item.prompt_version,
                classification_status=status,
                result=result,
                error=error,
                usage=usage,
                rate_card=self._rate_card,
                forced_from_snapshot_id=item.retry_of_snapshot_id,
                provider_model_version=provider_model_version,
                execution_mode="batch",
                batch_run_id=run.id,
                batch_item_key=item.opaque_key,
            ),
        )
        item.snapshot_id = row.id
        item.state = item_state
        item.error_code = error
        run.imported_count += 1
        if status == "error":
            run.error_count += 1
        if provider_model_version:
            run.provider_model_version = provider_model_version
        return row

    def _parse_key(self, payload: dict[str, Any], run: LyricClassificationBatchRun) -> UUID:
        try:
            return UUID(str(payload.get("key")))
        except (TypeError, ValueError) as exc:
            self._fail_run(run, "batch_malformed_output_key")
            raise BatchIntegrityError("malformed output key") from exc

    def _run(self, run_id: UUID) -> LyricClassificationBatchRun:
        run = self._session.get(LyricClassificationBatchRun, run_id)
        if run is None:
            raise LookupError(f"batch run does not exist: {run_id}")
        return run

    def _items(self, run_id: UUID) -> list[LyricClassificationBatchItem]:
        from sqlalchemy import select

        return list(
            self._session.scalars(
                select(LyricClassificationBatchItem)
                .where(LyricClassificationBatchItem.batch_run_id == run_id)
                .order_by(LyricClassificationBatchItem.line_number)
            )
        )

    def _fail_run(self, run: LyricClassificationBatchRun, code: str) -> None:
        run.job_error_code = code
        run.state = BatchRunState.FAILED.value
        self._session.commit()


def _candidate_text(candidate: dict[str, Any]) -> str | None:
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list) or len(parts) != 1 or not isinstance(parts[0], dict):
        return None
    value = parts[0].get("text")
    return value if isinstance(value, str) and value.strip() else None


def _usage_from_response(response: dict[str, Any]) -> UsageTelemetry | None:
    metadata = response.get("usageMetadata")
    if not isinstance(metadata, dict):
        return None
    values = {
        "input_tokens": metadata.get("promptTokenCount"),
        "output_tokens": metadata.get("candidatesTokenCount"),
        "thought_tokens": metadata.get("thoughtsTokenCount", 0),
        "total_tokens": metadata.get("totalTokenCount"),
    }
    if any(not isinstance(value, int) or value < 0 for value in values.values()):
        return None
    return UsageTelemetry(**values)


def _add_summary(
    summary: BatchImportSummary,
    status: str,
    usage: UsageTelemetry | None,
    rate_card: CostRateCard,
) -> None:
    summary.processed += 1
    if hasattr(summary, status):
        setattr(summary, status, getattr(summary, status) + 1)
    elif status == "error":
        summary.errors += 1
    if usage is None:
        return
    summary.input_tokens += usage.input_tokens or 0
    summary.output_tokens += usage.output_tokens or 0
    summary.thought_tokens += usage.thought_tokens or 0
    summary.total_tokens += usage.total_tokens or 0
    cost = rate_card.calculate(usage)
    if cost is not None:
        summary.known_cost_usd = (summary.known_cost_usd or Decimal(0)) + cost
