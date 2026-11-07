"""Positive, hash-bound eligibility for every new classification dispatch.

Existing documents/snapshots are never modified or implicitly approved. A reviewed
document carries its explicit adjudication in metadata_json['classification_adjudication'].
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    ValidationError,
)

from chart_observatory.db.models.corpus import LyricDocument
from chart_observatory.lyrics import review_evidence
from chart_observatory.lyrics.identity_quarantine import (
    excluded_document_ids,
    load_quarantine_entries,
    load_suspended_sources,
)
from chart_observatory.lyrics.repository import AUTHORIZED_RIGHTS

GATE_VERSION = "lyrics-classification-gate-v1"
ADJUDICATION_KEY = "classification_adjudication"
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonBlank = Annotated[str, Field(min_length=1, pattern=r"\S")]


class ClassificationAdjudication(BaseModel):
    """An explicit decision, not a successful download or an AI confidence score."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate_version: Literal["lyrics-classification-gate-v1"]
    adjudication_id: NonBlank
    document_id: UUID
    recording_id: UUID
    lyrics_hash: Digest
    source: NonBlank
    status: Literal["approved"]
    identity_verified: StrictBool
    integrity_verified: StrictBool
    method: Literal["official_transcription", "human_audio_verification"]
    evidence_url: HttpUrl
    evidence_sha256: Digest
    verified_at: AwareDatetime
    adjudicated_at: AwareDatetime
    adjudicator: NonBlank


@dataclass(frozen=True)
class GateDecision:
    eligible: bool
    reason: str


@dataclass(frozen=True)
class ClassificationGate:
    excluded_ids: frozenset[UUID]
    suspended_sources: frozenset[str]
    pending_documents: frozenset[tuple[str, str]]

    @classmethod
    def load(cls, quarantine_path: Path | None = None) -> ClassificationGate:
        # Missing/malformed policy files raise before any provider interaction.
        reports = review_evidence.load_review_evidence()
        return cls(
            excluded_document_ids(load_quarantine_entries(quarantine_path)),
            load_suspended_sources(quarantine_path),
            frozenset(
                (row["document_id"], row["lyrics_hash"])
                for row in reports
                if row["status"] == "pending_adjudication"
            ),
        )

    def assess(self, document: LyricDocument) -> GateDecision:
        if document.rights_status not in AUTHORIZED_RIGHTS:
            return GateDecision(False, "rights_unauthorized")
        if document.id in self.excluded_ids:
            return GateDecision(False, "identity_quarantined")
        if document.source.upper() in self.suspended_sources:
            return GateDecision(False, "source_suspended")
        if (str(document.id), document.content_sha256) in self.pending_documents:
            return GateDecision(False, "pending_adjudication")
        if not isinstance(document.text, str):
            return GateDecision(False, "text_unavailable")
        if hashlib.sha256(document.text.encode("utf-8")).hexdigest() != document.content_sha256:
            return GateDecision(False, "text_hash_mismatch")
        raw = (document.metadata_json or {}).get(ADJUDICATION_KEY)
        if raw is None:
            return GateDecision(False, "adjudication_missing")
        try:
            approval = ClassificationAdjudication.model_validate(raw)
        except ValidationError:
            return GateDecision(False, "adjudication_invalid")
        if (
            approval.document_id != document.id
            or approval.recording_id != document.canonical_track_id
            or approval.lyrics_hash != document.content_sha256
            or approval.source != document.source
        ):
            return GateDecision(False, "adjudication_binding_mismatch")
        if not approval.identity_verified:
            return GateDecision(False, "identity_unverified")
        if not approval.integrity_verified:
            return GateDecision(False, "integrity_unverified")
        if (
            approval.evidence_url.scheme != "https"
            or approval.adjudicated_at < approval.verified_at
        ):
            return GateDecision(False, "adjudication_evidence_invalid")
        return GateDecision(True, "eligible")

    def require(self, document: LyricDocument) -> None:
        decision = self.assess(document)
        if not decision.eligible:
            raise ClassificationEligibilityError(decision.reason)


class ClassificationEligibilityError(ValueError):
    """Dispatch was stopped before sending an unapproved lyric to a provider."""
