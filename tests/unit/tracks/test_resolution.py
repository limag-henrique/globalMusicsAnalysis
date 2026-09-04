from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.domain.enums import ResolutionStatus
from chart_observatory.tracks.repository import TrackRepository
from chart_observatory.tracks.resolution import TrackResolutionService


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_exact_isrc_matches_one_recording() -> None:
    with _session() as session:
        repo = TrackRepository(session)
        track = repo.create_track("Synthetic Song")
        repo.claim_external_id(track.id, "ISRC", "BRABC2100001", "CATALOG")
        item = repo.create_platform_item("APPLE_MUSIC", "1", "CATALOG_TRACK")
        repo.claim_item_external_id(item.id, "ISRC", "br-abc-21-00001", "APPLE")
        outcome = TrackResolutionService(session).resolve(item.id)
        assert outcome.status is ResolutionStatus.MATCHED_EXACT
        assert outcome.canonical_track_id == track.id


def test_conflicting_isrc_needs_review() -> None:
    with _session() as session:
        repo = TrackRepository(session)
        for title in ("First", "Second"):
            track = repo.create_track(title)
            repo.claim_external_id(track.id, "ISRC", "BRABC2100001", "CATALOG")
        item = repo.create_platform_item("APPLE_MUSIC", "1", "CATALOG_TRACK")
        repo.claim_item_external_id(item.id, "ISRC", "BRABC2100001", "APPLE")
        outcome = TrackResolutionService(session).resolve(item.id)
        assert outcome.status is ResolutionStatus.NEEDS_REVIEW
        assert outcome.canonical_track_id is None
        assert len(outcome.candidates) == 2


def test_fuzzy_candidate_never_confirms() -> None:
    with _session() as session:
        repo = TrackRepository(session)
        repo.create_track("Synthetic Song")
        item = repo.create_platform_item("APPLE_MUSIC", "1", "CATALOG_TRACK", "Synthetik Song")
        outcome = TrackResolutionService(session).resolve(item.id)
        assert outcome.status is ResolutionStatus.NEEDS_REVIEW
        assert outcome.canonical_track_id is None
        assert outcome.candidates
