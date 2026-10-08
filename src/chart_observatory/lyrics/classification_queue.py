"""Shared, rights-gated queue selection for online and batch classification."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import exists, func, select, text
from sqlalchemy.orm import Session

from chart_observatory.db.models.corpus import LyricClassificationSnapshot, LyricDocument
from chart_observatory.db.models.lyrics_batch import LyricClassificationBatchItem
from chart_observatory.lyrics.identity_quarantine import (
    excluded_document_ids,
    load_quarantine_entries,
    load_suspended_sources,
)
from chart_observatory.lyrics.repository import AUTHORIZED_RIGHTS

MIN_CLASSIFIABLE_TEXT_CHARS = 20
HANDLED_CLASSIFICATION_STATUSES = (
    "classified",
    "ambiguous",
    "instrumental",
    "insufficient_text",
    "language_unsupported",
    "blocked",
    "error",
)
ACTIVE_BATCH_ITEM_STATES = ("reserved", "submitted", "running")
_QUEUE_LOCK_KEY = 4_826_793_114_301_001


class ClassificationQueueBusy(RuntimeError):
    """Raised when online or batch selection already owns the shared lock."""


@dataclass(frozen=True, slots=True)
class ClassificationSignature:
    model_id: str
    taxonomy_version: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class ClassificationCandidate:
    lyric_document_id: UUID
    canonical_track_id: UUID
    lyrics_hash: str
    text: str | None
    language: str | None
    instrumental: bool


def local_classification_status(candidate: ClassificationCandidate) -> str | None:
    if candidate.instrumental:
        return "instrumental"
    if len(" ".join((candidate.text or "").split())) < MIN_CLASSIFIABLE_TEXT_CHARS:
        return "insufficient_text"
    return None


def select_remaining_candidates(
    session: Session,
    signature: ClassificationSignature,
    limit: int | None,
    exclude_active_batch: bool = True,
    quarantine_manifest_path: Path | None = None,
) -> list[ClassificationCandidate]:
    """Select each remaining authorized lyric signature once in stable order."""

    if limit is not None and limit < 1:
        raise ValueError("candidate limit must be positive")
    candidates: list[ClassificationCandidate] = []
    for candidate in iter_remaining_candidates(
        session,
        signature,
        exclude_active_batch,
        quarantine_manifest_path=quarantine_manifest_path,
    ):
        candidates.append(candidate)
        if limit is not None and len(candidates) >= limit:
            break
    return candidates


def iter_remaining_candidates(
    session: Session,
    signature: ClassificationSignature,
    exclude_active_batch: bool = True,
    *,
    quarantine_manifest_path: Path | None = None,
) -> Iterator[ClassificationCandidate]:
    """Stream remaining candidates so local outcomes do not consume provider limits."""

    handled = exists(
        select(LyricClassificationSnapshot.id).where(
            LyricClassificationSnapshot.canonical_track_id == LyricDocument.canonical_track_id,
            LyricClassificationSnapshot.lyrics_hash == LyricDocument.content_sha256,
            LyricClassificationSnapshot.model_id == signature.model_id,
            LyricClassificationSnapshot.taxonomy_version == signature.taxonomy_version,
            LyricClassificationSnapshot.prompt_version == signature.prompt_version,
            LyricClassificationSnapshot.classification_status.in_(HANDLED_CLASSIFICATION_STATUSES),
        )
    )
    statement = select(LyricDocument).where(
        LyricDocument.rights_status.in_(sorted(AUTHORIZED_RIGHTS)), ~handled
    )
    excluded_ids = excluded_document_ids(load_quarantine_entries(quarantine_manifest_path))
    if excluded_ids:
        statement = statement.where(LyricDocument.id.not_in(excluded_ids))
    suspended_sources = load_suspended_sources(quarantine_manifest_path)
    if suspended_sources:
        statement = statement.where(
            func.upper(LyricDocument.source).not_in(sorted(suspended_sources))
        )
    if exclude_active_batch:
        active = exists(
            select(LyricClassificationBatchItem.opaque_key).where(
                LyricClassificationBatchItem.canonical_track_id == LyricDocument.canonical_track_id,
                LyricClassificationBatchItem.lyrics_hash == LyricDocument.content_sha256,
                LyricClassificationBatchItem.model_id == signature.model_id,
                LyricClassificationBatchItem.taxonomy_version == signature.taxonomy_version,
                LyricClassificationBatchItem.prompt_version == signature.prompt_version,
                LyricClassificationBatchItem.state.in_(ACTIVE_BATCH_ITEM_STATES),
            )
        )
        statement = statement.where(~active)
    statement = statement.order_by(LyricDocument.created_at, LyricDocument.id)

    seen: set[tuple[UUID, str]] = set()
    for document in session.scalars(statement).yield_per(100):
        local_signature = (document.canonical_track_id, document.content_sha256)
        if local_signature in seen:
            continue
        seen.add(local_signature)
        yield ClassificationCandidate(
            lyric_document_id=document.id,
            canonical_track_id=document.canonical_track_id,
            lyrics_hash=document.content_sha256,
            text=document.text,
            language=document.language_code,
            instrumental=(document.metadata_json or {}).get("instrumental") is True,
        )


@contextmanager
def classification_queue_lock(session: Session) -> Iterator[None]:
    """Acquire one shared PostgreSQL session lock; SQLite tests need no lock."""

    if session.bind is None or session.bind.dialect.name != "postgresql":
        yield
        return
    acquired = session.scalar(
        text("SELECT pg_try_advisory_lock(:lock_key)"), {"lock_key": _QUEUE_LOCK_KEY}
    )
    if acquired is not True:
        raise ClassificationQueueBusy("lyric classification queue is already active")
    try:
        yield
    finally:
        session.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": _QUEUE_LOCK_KEY})
