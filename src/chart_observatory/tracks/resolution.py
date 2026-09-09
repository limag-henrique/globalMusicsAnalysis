from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.db.models.resolution import ResolutionRecord
from chart_observatory.db.models.tracks import CanonicalTrack, ExternalIdClaim, PlatformItem
from chart_observatory.domain.enums import ResolutionStatus
from chart_observatory.tracks.normalization import normalize_artist, normalize_text
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
        candidates = self._metadata_candidates(item)
        if len(candidates) == 1 and candidates[0].evidence.startswith("ARTIST_TITLE_EXACT"):
            outcome = ResolutionOutcome(
                ResolutionStatus.MATCHED_HIGH_CONFIDENCE,
                candidates[0].canonical_track_id,
                candidates,
            )
            return self._record(item_id, outcome, candidates[0].evidence)
        status = ResolutionStatus.NEEDS_REVIEW if candidates else ResolutionStatus.UNRESOLVED
        return self._record(
            item_id,
            ResolutionOutcome(status, None, candidates),
            "FUZZY_CANDIDATE_ONLY" if candidates else "NO_EVIDENCE",
        )

    def _metadata_candidates(self, item: PlatformItem) -> tuple[ResolutionCandidate, ...]:
        if not item.title:
            return ()
        title_key = normalize_text(item.title)
        artist_key = normalize_artist(item.artist) if item.artist else None
        tracks = list(self.session.scalars(select(CanonicalTrack)))
        exact: list[ResolutionCandidate] = []
        for track in tracks:
            track_artists = {normalize_artist(artist.name) for artist in track.artists}
            if (
                normalize_text(track.title) != title_key
                or not artist_key
                or artist_key not in track_artists
            ):
                continue
            score = 0.98
            evidence = "ARTIST_TITLE_EXACT"
            if item.duration_ms is not None and track.duration_ms == item.duration_ms:
                score = 0.995
                evidence += "_DURATION"
            if item.release_date is not None and track.release_date == item.release_date:
                score = min(0.999, score + 0.003)
                evidence += "_RELEASE_DATE"
            exact.append(ResolutionCandidate(track.id, score, evidence))
        if exact:
            return tuple(
                sorted(
                    exact,
                    key=lambda candidate: (-candidate.score, str(candidate.canonical_track_id)),
                )
            )

        scored: list[ResolutionCandidate] = []
        for track in tracks:
            title_score = title_similarity(item.title, track.title)
            artist_score = 0.0
            if artist_key:
                artist_score = max(
                    (title_similarity(item.artist or "", artist.name) for artist in track.artists),
                    default=0.0,
                )
                score = title_score * 0.7 + artist_score * 0.3
                evidence = "FUZZY_TITLE_ARTIST_CANDIDATE"
            else:
                score = title_score
                evidence = "FUZZY_TITLE_CANDIDATE"
            if score >= 0.6:
                scored.append(ResolutionCandidate(track.id, score, evidence))
        return tuple(
            sorted(
                scored,
                key=lambda candidate: (-candidate.score, str(candidate.canonical_track_id)),
            )
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
