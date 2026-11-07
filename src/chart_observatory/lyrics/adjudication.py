"""Transactional decisions on existing lyric documents, preserving every prior decision."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.db.models.corpus import LyricDocument
from chart_observatory.lyrics.classification_gate import (
    ADJUDICATION_KEY,
    ClassificationAdjudication,
    ClassificationEligibilityError,
    ClassificationGate,
)


def record_adjudication(
    session: Session,
    document_id: UUID,
    *,
    expected_hash: str,
    expected_previous_id: str | None,
    decision_id: str,
    actor: str,
    decision: Literal["approved", "rejected", "quarantined", "manual_review", "preserved"],
    reason: str,
    approval: ClassificationAdjudication | None = None,
) -> LyricDocument:
    """Lock and append one explicit decision; caller owns commit/rollback.

    This never repairs text or manufactures an approval. A replacement is a new
    lyric document followed by a separate evidence-bound decision, not an UPDATE
    of the original text. PostgreSQL locks serialize reviewers; the expected ID
    rejects a stale second decision after the first transaction commits.
    """
    if decision not in {"approved", "rejected", "quarantined", "manual_review", "preserved"}:
        raise ValueError("unsupported adjudication decision")
    if not all(isinstance(value, str) and value.strip() for value in (decision_id, actor, reason)):
        raise ValueError("decision id, actor and reason are required")
    with session.begin_nested():
        document = session.scalar(
            select(LyricDocument)
            .where(LyricDocument.id == document_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if document is None:
            raise ClassificationEligibilityError("document_unavailable")
        if document.content_sha256 != expected_hash:
            raise ClassificationEligibilityError("adjudication_stale_hash")
        metadata = dict(document.metadata_json or {})
        history = list(metadata.get("adjudication_history", []))
        current = metadata.get(ADJUDICATION_KEY)
        previous_id = (
            history[-1]["decision_id"]
            if history
            else (current.get("adjudication_id") if isinstance(current, dict) else None)
        )
        if previous_id != expected_previous_id:
            raise ClassificationEligibilityError("adjudication_stale_decision")
        if any(row["decision_id"] == decision_id for row in history):
            raise ValueError("adjudication decision id already used")
        if decision == "approved":
            if (
                approval is None
                or approval.adjudication_id != decision_id
                or approval.adjudicator != actor
            ):
                raise ValueError("explicit approval and decision actor/id must match")
            metadata[ADJUDICATION_KEY] = approval.model_dump(mode="json")
        elif decision != "preserved":
            metadata.pop(ADJUDICATION_KEY, None)
        event = dict(
            decision_id=decision_id,
            decision=decision,
            actor=actor,
            reason=reason,
            document_id=str(document.id),
            recording_id=str(document.canonical_track_id),
            lyrics_hash=expected_hash,
            recorded_at=datetime.now(UTC).isoformat(),
            previous_approval=current,
            approval=metadata.get(ADJUDICATION_KEY),
        )
        metadata["adjudication_history"] = [*history, event]
        document.metadata_json = metadata
        if decision == "approved":
            ClassificationGate.load().require(document)
        session.flush()
    return document
