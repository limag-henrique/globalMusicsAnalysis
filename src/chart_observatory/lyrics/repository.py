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

from chart_observatory.db.models.corpus import LyricDocument, SemanticAnnotation
from chart_observatory.lyrics.annotations import SemanticAnnotationInput, validate_annotation

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
