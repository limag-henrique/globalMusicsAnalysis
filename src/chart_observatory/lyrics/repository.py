"""Persistence boundary for authorized lyric documents and annotations."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.db.models.corpus import (
    LyricClassificationSnapshot,
    LyricDocument,
    SemanticAnnotation,
)
from chart_observatory.lyrics.annotations import SemanticAnnotationInput, validate_annotation
from chart_observatory.lyrics.classification import (
    CostRateCard,
    LyricsClassification,
    UsageTelemetry,
)

AUTHORIZED_RIGHTS = {"LICENSED", "RESEARCH_AUTHORIZED", "PUBLIC_DOMAIN", "AUTHORIZED"}


@dataclass(frozen=True)
class LyricDocumentInput:
    canonical_track_id: UUID
    source: str
    source_version: str
    rights_status: str
    language_code: str | None = None
    text: str | None = None
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ClassificationSnapshotInput:
    """All data required to append one immutable automatic classification outcome."""

    lyric_document_id: UUID
    canonical_track_id: UUID
    lyrics_hash: str
    model_id: str
    taxonomy_version: str
    prompt_version: str
    classification_status: str
    result: LyricsClassification | None = None
    error: str | None = None
    confidence: float | None = None
    classified_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    usage: UsageTelemetry | None = None
    rate_card: CostRateCard | None = None
    forced_from_snapshot_id: UUID | None = None


def find_matching_snapshot(
    session: Session, snapshot: ClassificationSnapshotInput
) -> LyricClassificationSnapshot | None:
    """Return the most recently appended outcome for a reproducibility signature."""
    return session.scalar(
        select(LyricClassificationSnapshot)
        .where(
            LyricClassificationSnapshot.canonical_track_id == snapshot.canonical_track_id,
            LyricClassificationSnapshot.lyrics_hash == snapshot.lyrics_hash,
            LyricClassificationSnapshot.model_id == snapshot.model_id,
            LyricClassificationSnapshot.taxonomy_version == snapshot.taxonomy_version,
            LyricClassificationSnapshot.prompt_version == snapshot.prompt_version,
        )
        .order_by(
            LyricClassificationSnapshot.append_order.desc(),
        )
    )


def append_classification_snapshot(
    session: Session, snapshot: ClassificationSnapshotInput
) -> LyricClassificationSnapshot:
    """Append an outcome after verifying its document and explicit track agree."""
    document = session.get(LyricDocument, snapshot.lyric_document_id)
    if document is None:
        raise ValueError(f"lyric_document_id does not exist: {snapshot.lyric_document_id}")
    if document.canonical_track_id != snapshot.canonical_track_id:
        raise ValueError("canonical_track_id does not match lyric document")
    if snapshot.forced_from_snapshot_id is not None:
        forced_from = session.get(LyricClassificationSnapshot, snapshot.forced_from_snapshot_id)
        if forced_from is None:
            raise ValueError(
                f"forced_from_snapshot_id does not exist: {snapshot.forced_from_snapshot_id}"
            )
        if (
            forced_from.canonical_track_id != snapshot.canonical_track_id
            or forced_from.lyrics_hash != snapshot.lyrics_hash
            or forced_from.model_id != snapshot.model_id
            or forced_from.taxonomy_version != snapshot.taxonomy_version
            or forced_from.prompt_version != snapshot.prompt_version
        ):
            raise ValueError("forced_from_snapshot_id does not match snapshot signature")

    result_json = snapshot.result.model_dump(mode="json") if snapshot.result is not None else None
    usage = snapshot.usage
    confidence = snapshot.confidence
    if confidence is None and snapshot.result is not None:
        confidence = snapshot.result.confidence
    row = LyricClassificationSnapshot(
        lyric_document_id=snapshot.lyric_document_id,
        canonical_track_id=snapshot.canonical_track_id,
        lyrics_hash=snapshot.lyrics_hash,
        model_id=snapshot.model_id,
        taxonomy_version=snapshot.taxonomy_version,
        prompt_version=snapshot.prompt_version,
        classification_status=snapshot.classification_status,
        confidence=confidence,
        result_json=result_json,
        error=snapshot.error,
        classified_at=snapshot.classified_at,
        input_tokens=usage.input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        thought_tokens=usage.thought_tokens if usage is not None else None,
        total_tokens=usage.total_tokens if usage is not None else None,
        estimated_cost_usd=snapshot.rate_card.calculate(usage) if snapshot.rate_card else None,
        forced_from_snapshot_id=snapshot.forced_from_snapshot_id,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    return row


def ingest_lyric_document(session: Session, document: LyricDocumentInput) -> LyricDocument:
    """Insert an authorized document once, preserving content provenance."""
    rights_status = document.rights_status.upper()
    if rights_status not in AUTHORIZED_RIGHTS:
        raise ValueError(f"lyric document rights_status is not authorized: {rights_status}")
    text = document.text
    digest = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
    existing = session.scalar(
        select(LyricDocument).where(
            LyricDocument.canonical_track_id == document.canonical_track_id,
            LyricDocument.source == document.source,
            LyricDocument.content_sha256 == digest,
        )
    )
    if existing is not None:
        return existing
    row = LyricDocument(
        canonical_track_id=document.canonical_track_id,
        language_code=document.language_code,
        source=document.source,
        source_version=document.source_version,
        rights_status=rights_status,
        content_sha256=digest,
        text=text,
        retrieved_at=document.retrieved_at,
        metadata_json=document.metadata,
    )
    session.add(row)
    session.flush()
    return row


def annotate_document(
    session: Session,
    document_id: UUID,
    annotations: Iterable[SemanticAnnotationInput],
) -> list[SemanticAnnotation]:
    """Upsert category/model annotations while retaining review status."""
    rows: list[SemanticAnnotation] = []
    for input_annotation in annotations:
        annotation = validate_annotation(input_annotation)
        existing = session.scalar(
            select(SemanticAnnotation).where(
                SemanticAnnotation.lyric_document_id == document_id,
                SemanticAnnotation.category == annotation.category,
                SemanticAnnotation.model_version == annotation.model_version,
            )
        )
        values = {
            "value": annotation.value,
            "confidence": annotation.confidence,
            "method": annotation.method,
            "source": annotation.source,
            "review_status": annotation.review_status,
        }
        if existing is None:
            existing = SemanticAnnotation(
                lyric_document_id=document_id,
                category=annotation.category,
                model_version=annotation.model_version,
                **values,
            )
            session.add(existing)
        else:
            for key, value in values.items():
                setattr(existing, key, value)
        rows.append(existing)
    session.flush()
    return rows


def annotation_input_from_dict(payload: dict[str, Any]) -> SemanticAnnotationInput:
    return SemanticAnnotationInput(
        category=str(payload["category"]),
        value=float(payload["value"]),
        confidence=(
            float(payload["confidence"]) if payload.get("confidence") is not None else None
        ),
        method=str(payload.get("method", "LLM_REVIEW")),
        model_version=str(payload.get("model_version", "pending-validation")),
        source=str(payload.get("source", "LLM_VALIDATION")),
        review_status=str(payload.get("review_status", "UNREVIEWED")),
    )
