"""Provider-independent contracts and state machine for lyric batch work."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from chart_observatory.lyrics.classification_queue import ClassificationSignature


class BatchRunKind(StrEnum):
    CANARY = "canary"
    PILOT = "pilot"
    MAIN = "main"
    ERROR_RETRY = "error_retry"


class BatchRunState(StrEnum):
    PREPARED = "prepared"
    UPLOADED = "uploaded"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    IMPORTED = "imported"
    CLEANED = "cleaned"


class BatchItemState(StrEnum):
    RESERVED = "reserved"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    ERROR = "error"
    MISSING = "missing"
    IMPORTED = "imported"


class InvalidBatchTransition(ValueError):
    """Raised when an operation attempts to skip a required durable state."""


_RUN_TRANSITIONS = {
    BatchRunState.PREPARED: {BatchRunState.UPLOADED, BatchRunState.FAILED},
    BatchRunState.UPLOADED: {BatchRunState.SUBMITTED, BatchRunState.FAILED},
    BatchRunState.SUBMITTED: {
        BatchRunState.RUNNING,
        BatchRunState.SUCCEEDED,
        BatchRunState.FAILED,
        BatchRunState.CANCELLED,
        BatchRunState.EXPIRED,
    },
    BatchRunState.RUNNING: {
        BatchRunState.SUCCEEDED,
        BatchRunState.FAILED,
        BatchRunState.CANCELLED,
        BatchRunState.EXPIRED,
    },
    BatchRunState.SUCCEEDED: {BatchRunState.IMPORTED},
    BatchRunState.FAILED: {BatchRunState.IMPORTED},
    BatchRunState.CANCELLED: {BatchRunState.IMPORTED},
    BatchRunState.EXPIRED: {BatchRunState.IMPORTED},
    BatchRunState.IMPORTED: {BatchRunState.CLEANED},
    BatchRunState.CLEANED: set(),
}


def validate_run_transition(current: BatchRunState | str, target: BatchRunState | str) -> None:
    current_state = BatchRunState(current)
    target_state = BatchRunState(target)
    if target_state not in _RUN_TRANSITIONS[current_state]:
        raise InvalidBatchTransition(
            f"invalid batch run transition: {current_state}->{target_state}"
        )


@dataclass(frozen=True, slots=True)
class BatchPreparationRequest:
    kind: BatchRunKind
    signature: ClassificationSignature
    project_id: str
    location: str
    bucket_name: str
    limit: int | None = None
    thinking_level: str = "LOW"
    include_identity_holds: bool = False


@dataclass(frozen=True, slots=True)
class BatchPreparation:
    run_id: UUID
    request_count: int
    source_uri: str | None = None
    expected_cost_usd: Decimal | None = None
    conservative_cost_usd: Decimal | None = None


@dataclass(frozen=True, slots=True)
class BatchRetryCandidate:
    lyric_document_id: UUID
    prior_snapshot_id: UUID
