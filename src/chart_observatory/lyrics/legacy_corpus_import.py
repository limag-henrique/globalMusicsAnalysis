"""Import the API-downloaded lyric JSONL corpus into the rights-gated database."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from chart_observatory.db.models.corpus import LyricDocument
from chart_observatory.db.models.tracks import Artist, CanonicalTrack, track_artists
from chart_observatory.lyrics.identity_quarantine import (
    load_quarantined_source_signatures,
    load_suspended_sources,
)
from chart_observatory.lyrics.repository import AUTHORIZED_RIGHTS

_BATCH_SIZE = 1_000
_SOURCE_VERSION = "legacy-api-import-v1"
_TRACK_NAMESPACE = "chart-observatory:api-lyrics:track:v1:"
_ARTIST_NAMESPACE = "chart-observatory:api-lyrics:artist:v1:"


@dataclass(frozen=True)
class LegacyLyricCandidate:
    line_number: int
    canonical_track_id: UUID
    artist_id: UUID
    title: str
    artist_name: str
    source: str
    lyrics_hash: str
    text: str
    retrieved_at: datetime
    rights_status: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class LegacyLyricImportSummary:
    records_seen: int
    eligible_rows: int
    malformed_records: int
    noneligible_records: int
    documents_inserted: int
    documents_already_present: int
    tracks_inserted: int
    artists_inserted: int


@dataclass(frozen=True)
class LegacyLyricPreview:
    records_seen: int
    eligible_rows: int
    distinct_documents: int
    distinct_tracks: int
    malformed_records: int
    noneligible_records: int
    lyric_text_bytes: int


def _normalize_identity(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def legacy_annotation_candidate(
    payload: dict[str, object],
    line_number: int,
    retrieved_at: datetime,
    rights_status: str = "RESEARCH_AUTHORIZED",
    *,
    quarantined_source_signatures: frozenset[tuple[str, str]] | None = None,
    suspended_sources: frozenset[str] | None = None,
) -> LegacyLyricCandidate | None:
    """Translate one API-backfill row without consulting its provider track ID."""

    authorized_status = rights_status.strip().upper()
    if authorized_status not in AUTHORIZED_RIGHTS:
        raise ValueError(f"unsupported authorization status: {authorized_status}")
    text_value = payload.get("original_lyrics")
    if (
        str(payload.get("lyrics_status") or "").strip().upper() != "FOUND"
        or not isinstance(text_value, str)
        or not text_value.strip()
    ):
        return None

    raw_title = str(payload.get("title") or "").strip()
    raw_artist = str(payload.get("artist") or "").strip()
    title = raw_title or f"Untitled imported lyric {line_number}"
    artist_name = raw_artist or f"Unknown artist {line_number}"
    normalized_title = _normalize_identity(title)
    normalized_artist = _normalize_identity(artist_name)
    identity = f"{normalized_artist}\0{normalized_title}"
    canonical_track_id = uuid5(NAMESPACE_URL, _TRACK_NAMESPACE + identity)
    artist_id = uuid5(NAMESPACE_URL, _ARTIST_NAMESPACE + normalized_artist)
    text = text_value
    lyrics_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    source = str(payload.get("lyrics_source") or "UNKNOWN_API").strip().upper()
    source = source[:100] or "UNKNOWN_API"
    blocked_signatures = (
        quarantined_source_signatures
        if quarantined_source_signatures is not None
        else load_quarantined_source_signatures()
    )
    blocked_sources = (
        suspended_sources if suspended_sources is not None else load_suspended_sources()
    )
    if source in blocked_sources or (source, lyrics_hash) in blocked_signatures:
        return None

    return LegacyLyricCandidate(
        line_number=line_number,
        canonical_track_id=canonical_track_id,
        artist_id=artist_id,
        title=title[:1_000],
        artist_name=artist_name[:500],
        source=source,
        lyrics_hash=lyrics_hash,
        text=text,
        retrieved_at=retrieved_at,
        rights_status=authorized_status,
        metadata={"ingest_artifact": "gemini_annotations.jsonl"},
    )


def preview_legacy_api_lyrics(
    input_path: Path,
    *,
    rights_status: str = "RESEARCH_AUTHORIZED",
) -> LegacyLyricPreview:
    """Count importable records and exact duplicates without storing lyric text."""

    retrieved_at = datetime.fromtimestamp(input_path.stat().st_mtime, tz=UTC)
    seen_documents: set[tuple[UUID, str, str]] = set()
    seen_tracks: set[UUID] = set()
    records_seen = eligible_rows = malformed_records = noneligible_records = 0
    lyric_text_bytes = 0
    with input_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            records_seen += 1
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                malformed_records += 1
                continue
            if not isinstance(payload, dict):
                noneligible_records += 1
                continue
            candidate = legacy_annotation_candidate(
                payload, line_number, retrieved_at, rights_status
            )
            if candidate is None:
                noneligible_records += 1
                continue
            eligible_rows += 1
            lyric_text_bytes += len(candidate.text.encode("utf-8"))
            seen_tracks.add(candidate.canonical_track_id)
            seen_documents.add(
                (candidate.canonical_track_id, candidate.source, candidate.lyrics_hash)
            )
    return LegacyLyricPreview(
        records_seen=records_seen,
        eligible_rows=eligible_rows,
        distinct_documents=len(seen_documents),
        distinct_tracks=len(seen_tracks),
        malformed_records=malformed_records,
        noneligible_records=noneligible_records,
        lyric_text_bytes=lyric_text_bytes,
    )


def import_legacy_api_lyrics(
    session: Session,
    input_path: Path,
    *,
    rights_status: str = "RESEARCH_AUTHORIZED",
    batch_size: int = _BATCH_SIZE,
) -> LegacyLyricImportSummary:
    """Idempotently ingest API-downloaded FOUND lyrics in bounded transactions."""

    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    preview = preview_legacy_api_lyrics(input_path, rights_status=rights_status)
    retrieved_at = datetime.fromtimestamp(input_path.stat().st_mtime, tz=UTC)
    candidates: list[LegacyLyricCandidate] = []
    documents_inserted = tracks_inserted = artists_inserted = 0
    with input_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            candidate = legacy_annotation_candidate(
                payload, line_number, retrieved_at, rights_status
            )
            if candidate is not None:
                candidates.append(candidate)
            if len(candidates) >= batch_size:
                inserted, new_tracks, new_artists = _insert_batch(session, candidates)
                documents_inserted += inserted
                tracks_inserted += new_tracks
                artists_inserted += new_artists
                candidates.clear()
    if candidates:
        inserted, new_tracks, new_artists = _insert_batch(session, candidates)
        documents_inserted += inserted
        tracks_inserted += new_tracks
        artists_inserted += new_artists

    return LegacyLyricImportSummary(
        records_seen=preview.records_seen,
        eligible_rows=preview.eligible_rows,
        malformed_records=preview.malformed_records,
        noneligible_records=preview.noneligible_records,
        documents_inserted=documents_inserted,
        documents_already_present=preview.eligible_rows - documents_inserted,
        tracks_inserted=tracks_inserted,
        artists_inserted=artists_inserted,
    )


def _insert_batch(session: Session, candidates: list[LegacyLyricCandidate]) -> tuple[int, int, int]:
    tracks = {
        candidate.canonical_track_id: {"id": candidate.canonical_track_id, "title": candidate.title}
        for candidate in candidates
    }
    artists = {
        candidate.artist_id: {"id": candidate.artist_id, "name": candidate.artist_name}
        for candidate in candidates
    }
    links = {
        (candidate.canonical_track_id, candidate.artist_id): {
            "track_id": candidate.canonical_track_id,
            "artist_id": candidate.artist_id,
        }
        for candidate in candidates
    }
    unique_documents: dict[tuple[UUID, str, str], LegacyLyricCandidate] = {}
    for candidate in candidates:
        unique_documents.setdefault(
            (candidate.canonical_track_id, candidate.source, candidate.lyrics_hash), candidate
        )
    document_rows = [
        {
            "id": uuid5(
                NAMESPACE_URL,
                "chart-observatory:api-lyrics:document:v1:"
                f"{candidate.canonical_track_id}:{candidate.source}:{candidate.lyrics_hash}",
            ),
            "canonical_track_id": candidate.canonical_track_id,
            "language_code": None,
            "source": candidate.source,
            "source_version": _SOURCE_VERSION,
            "rights_status": candidate.rights_status,
            "content_sha256": candidate.lyrics_hash,
            "text": candidate.text,
            "retrieved_at": candidate.retrieved_at,
            "metadata_json": candidate.metadata,
        }
        for candidate in unique_documents.values()
    ]

    try:
        new_tracks = session.execute(
            pg_insert(CanonicalTrack)
            .values(list(tracks.values()))
            .on_conflict_do_nothing(index_elements=[CanonicalTrack.id])
            .returning(CanonicalTrack.id)
        ).all()
        new_artists = session.execute(
            pg_insert(Artist)
            .values(list(artists.values()))
            .on_conflict_do_nothing(index_elements=[Artist.id])
            .returning(Artist.id)
        ).all()
        session.execute(
            pg_insert(track_artists).values(list(links.values())).on_conflict_do_nothing()
        )
        new_documents = session.execute(
            pg_insert(LyricDocument)
            .values(document_rows)
            .on_conflict_do_nothing(
                index_elements=[
                    LyricDocument.canonical_track_id,
                    LyricDocument.source,
                    LyricDocument.content_sha256,
                ]
            )
            .returning(LyricDocument.id)
        ).all()
        session.commit()
    except Exception:
        session.rollback()
        raise
    return len(new_documents), len(new_tracks), len(new_artists)
