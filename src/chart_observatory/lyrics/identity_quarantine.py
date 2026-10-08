"""Durable, non-destructive review decisions for lyric identity risks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from uuid import UUID

SCHEMA_VERSION = 2
SOURCE_SUSPENSION_STATUS = "suspended_pending_validation"
EXCLUDED_DECISIONS = frozenset(
    {"suspected_mismatch", "confirmed_mismatch", "insufficient_text", "contaminated_text"}
)
ALL_DECISIONS = EXCLUDED_DECISIONS | frozenset(
    {"confirmed_match", "probable_match", "related_version", "needs_review"}
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_QUARANTINE_MANIFEST = (
    Path(__file__).resolve().parents[3] / "config" / "lyrics_identity_quarantine.json"
)


@dataclass(frozen=True, slots=True)
class IdentityQuarantineEntry:
    lyric_document_id: UUID
    canonical_track_id: UUID
    title: str
    artist: str
    source: str
    lyrics_hash: str
    decision: str
    reason: str
    evidence: tuple[str, ...]
    reviewed_on: str
    review_method: str
    preserved_snapshot_ids: tuple[UUID, ...]
    corrected_document_id: UUID | None
    replacement_snapshot_id: UUID | None


@dataclass(frozen=True, slots=True)
class SuspendedSourcePolicy:
    source: str
    status: str
    reason: str
    effective_on: str
    expected_document_count: int
    allow_active_batch_reconciliation: bool


def load_quarantine_entries(
    path: Path | None = None,
) -> tuple[IdentityQuarantineEntry, ...]:
    """Load and validate the manifest; malformed or missing data fails closed."""

    manifest_path = path or DEFAULT_QUARANTINE_MANIFEST
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported lyric identity quarantine schema version")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("lyric identity quarantine entries must be a list")

    entries: list[IdentityQuarantineEntry] = []
    seen_ids: set[UUID] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ValueError("lyric identity quarantine entry must be an object")
        try:
            entry = IdentityQuarantineEntry(
                lyric_document_id=UUID(_required_string(raw, "lyric_document_id")),
                canonical_track_id=UUID(_required_string(raw, "canonical_track_id")),
                title=_required_string(raw, "title"),
                artist=_required_string(raw, "artist"),
                source=_required_string(raw, "source"),
                lyrics_hash=_required_string(raw, "lyrics_hash"),
                decision=_required_string(raw, "decision"),
                reason=_required_string(raw, "reason"),
                evidence=_required_evidence(raw.get("evidence")),
                reviewed_on=_required_string(raw, "reviewed_on"),
                review_method=_required_string(raw, "review_method"),
                preserved_snapshot_ids=_optional_uuids(raw.get("preserved_snapshot_ids", [])),
                corrected_document_id=_optional_uuid(raw.get("corrected_document_id")),
                replacement_snapshot_id=_optional_uuid(raw.get("replacement_snapshot_id")),
            )
        except (TypeError, AttributeError) as exc:
            raise ValueError("invalid lyric identity quarantine entry") from exc
        if entry.decision not in ALL_DECISIONS:
            raise ValueError("unsupported quarantine decision")
        if _SHA256_PATTERN.fullmatch(entry.lyrics_hash) is None:
            raise ValueError("invalid lyrics hash in quarantine entry")
        if entry.lyric_document_id in seen_ids:
            raise ValueError("duplicate lyric document in quarantine manifest")
        seen_ids.add(entry.lyric_document_id)
        entries.append(entry)
    return tuple(entries)


def load_suspended_sources(path: Path | None = None) -> frozenset[str]:
    """Return sources barred from new imports, provider queues, and science."""

    if path is not None:
        return _suspended_sources(load_source_suspension_policies(path))
    manifest_path = DEFAULT_QUARANTINE_MANIFEST
    return _load_cached_suspended_sources(manifest_path, manifest_path.stat().st_mtime_ns)


def load_source_suspension_policies(
    path: Path | None = None,
) -> tuple[SuspendedSourcePolicy, ...]:
    """Load the auditable source-level hold policy; malformed data fails closed."""

    manifest_path = path or DEFAULT_QUARANTINE_MANIFEST
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported lyric identity quarantine schema version")
    raw_policies = payload.get("suspended_sources")
    if not isinstance(raw_policies, list):
        raise ValueError("suspended lyric sources must be a list")

    policies: list[SuspendedSourcePolicy] = []
    seen_sources: set[str] = set()
    for raw in raw_policies:
        if not isinstance(raw, dict):
            raise ValueError("suspended lyric source policy must be an object")
        source = _required_string(raw, "source").upper()
        status = _required_string(raw, "status")
        if status != SOURCE_SUSPENSION_STATUS:
            raise ValueError("unsupported source suspension status")
        expected_document_count = raw.get("expected_document_count")
        if not isinstance(expected_document_count, int) or expected_document_count < 1:
            raise ValueError("suspended source expected document count must be positive")
        allow_reconciliation = raw.get("allow_active_batch_reconciliation")
        if not isinstance(allow_reconciliation, bool):
            raise ValueError("active batch reconciliation policy must be boolean")
        if source in seen_sources:
            raise ValueError("duplicate suspended lyric source")
        seen_sources.add(source)
        policies.append(
            SuspendedSourcePolicy(
                source=source,
                status=status,
                reason=_required_string(raw, "reason"),
                effective_on=_required_string(raw, "effective_on"),
                expected_document_count=expected_document_count,
                allow_active_batch_reconciliation=allow_reconciliation,
            )
        )
    return tuple(policies)


def excluded_document_ids(
    entries: tuple[IdentityQuarantineEntry, ...],
) -> frozenset[UUID]:
    """Return IDs whose evidence status excludes them from science/provider queues."""

    return frozenset(
        entry.lyric_document_id for entry in entries if entry.decision in EXCLUDED_DECISIONS
    )


def load_quarantined_source_signatures(
    path: Path | None = None,
) -> frozenset[tuple[str, str]]:
    """Return exact source/hash pairs whose evidence is in an excluded state."""

    if path is not None:
        return _source_signatures(load_quarantine_entries(path))
    manifest_path = DEFAULT_QUARANTINE_MANIFEST
    return _load_cached_source_signatures(manifest_path, manifest_path.stat().st_mtime_ns)


@lru_cache(maxsize=1)
def _load_cached_source_signatures(
    manifest_path: Path, modified_at_ns: int
) -> frozenset[tuple[str, str]]:
    del modified_at_ns
    return _source_signatures(load_quarantine_entries(manifest_path))


@lru_cache(maxsize=1)
def _load_cached_suspended_sources(manifest_path: Path, modified_at_ns: int) -> frozenset[str]:
    del modified_at_ns
    return _suspended_sources(load_source_suspension_policies(manifest_path))


def _suspended_sources(
    policies: tuple[SuspendedSourcePolicy, ...],
) -> frozenset[str]:
    return frozenset(policy.source for policy in policies)


def _source_signatures(
    entries: tuple[IdentityQuarantineEntry, ...],
) -> frozenset[tuple[str, str]]:
    return frozenset(
        (entry.source.upper(), entry.lyrics_hash)
        for entry in entries
        if entry.decision in EXCLUDED_DECISIONS
    )


def scientifically_eligible_document_ids(
    document_ids: tuple[UUID, ...] | list[UUID],
    entries: tuple[IdentityQuarantineEntry, ...],
) -> tuple[UUID, ...]:
    """Filter an ordered lyric-document ID collection for scientific selection."""

    excluded = excluded_document_ids(entries)
    return tuple(document_id for document_id in document_ids if document_id not in excluded)


def _required_string(raw: dict[str, object], name: str) -> str:
    value = raw.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required quarantine field: {name}")
    return value


def _required_evidence(value: object) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise ValueError("quarantine evidence must be a non-empty list of strings")
    return tuple(value)


def _optional_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional quarantine IDs must be UUID strings")
    return UUID(value)


def _optional_uuids(value: object) -> tuple[UUID, ...]:
    if not isinstance(value, list):
        raise ValueError("preserved snapshot IDs must be a list")
    if any(not isinstance(item, str) for item in value):
        raise ValueError("preserved snapshot IDs must be UUID strings")
    return tuple(UUID(item) for item in value)
