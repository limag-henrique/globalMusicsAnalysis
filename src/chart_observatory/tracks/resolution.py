from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.db.models.resolution import ResolutionRecord
from chart_observatory.db.models.tracks import CanonicalTrack, ExternalIdClaim, PlatformItem
from chart_observatory.domain.enums import ResolutionStatus
from chart_observatory.tracks.similarity import title_similarity


@dataclass(frozen=True)
class ResolutionCandidate:
    canonical_track_id: UUID
    score: float
    evidence: str


@dataclass(frozen=True)
class ResolutionOutcome:
    status: ResolutionStatus
    canonical_track_id: UUID | None
    candidates: tuple[ResolutionCandidate, ...] = ()


class TrackResolutionService:
    RULE_VERSION = "resolution-v1"

    def __init__(self, session: Session) -> None:
        self.session = session

    def resolve(self, item_id: UUID) -> ResolutionOutcome:
        item = self.session.get(PlatformItem, item_id)
        if item is None:
            raise LookupError(item_id)
        item_isrcs = self.session.scalars(
            select(ExternalIdClaim).where(
                ExternalIdClaim.platform_item_id == item_id,
                ExternalIdClaim.namespace == "ISRC",
            )
        ).all()
        track_ids: set[UUID] = set()
        for claim in item_isrcs:
            track_ids.update(
                self.session.scalars(
                    select(ExternalIdClaim.canonical_track_id).where(
                        ExternalIdClaim.namespace == "ISRC",
                        ExternalIdClaim.normalized_value == claim.normalized_value,
                        ExternalIdClaim.canonical_track_id.is_not(None),
                    )
                )
            )
        if len(track_ids) == 1:
            outcome = ResolutionOutcome(ResolutionStatus.MATCHED_EXACT, next(iter(track_ids)))
            return self._record(item_id, outcome, "EXACT_ISRC")
        if len(track_ids) > 1:
            exact_candidates = tuple(
                ResolutionCandidate(track_id, 1.0, "CONFLICTING_ISRC")
                for track_id in sorted(track_ids, key=str)
            )
            return self._record(
                item_id,
                ResolutionOutcome(ResolutionStatus.NEEDS_REVIEW, None, exact_candidates),
                "CONFLICTING_ISRC",
            )
        candidates: tuple[ResolutionCandidate, ...] = ()
        if item.title:
            scored = [
                ResolutionCandidate(
                    track.id, title_similarity(item.title, track.title), "FUZZY_TITLE_CANDIDATE"
                )
                for track in self.session.scalars(select(CanonicalTrack))
            ]
            candidates = tuple(
                sorted(
                    (c for c in scored if c.score >= 0.6),
                    key=lambda c: (-c.score, str(c.canonical_track_id)),
                )
            )
        status = ResolutionStatus.NEEDS_REVIEW if candidates else ResolutionStatus.UNRESOLVED
        return self._record(
            item_id,
            ResolutionOutcome(status, None, candidates),
            "FUZZY_CANDIDATE_ONLY" if candidates else "NO_EVIDENCE",
        )

    def _record(
        self, item_id: UUID, outcome: ResolutionOutcome, evidence: str
    ) -> ResolutionOutcome:
        self.session.add(
            ResolutionRecord(
                platform_item_id=item_id,
                canonical_track_id=outcome.canonical_track_id,
                status=outcome.status,
                rule_version=self.RULE_VERSION,
                evidence=evidence,
                score=max((candidate.score for candidate in outcome.candidates), default=None),
                candidates=[
                    {
                        "canonical_track_id": str(c.canonical_track_id),
                        "score": c.score,
                        "evidence": c.evidence,
                    }
                    for c in outcome.candidates
                ],
            )
        )
        self.session.flush()
        return outcome
