from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.domain.enums import ResolutionStatus
from chart_observatory.tracks.repository import TrackRepository
from chart_observatory.tracks.resolution import TrackResolutionService


def test_artist_and_title_match_before_title_only_fuzzy_candidates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = TrackRepository(session)
        track = repository.create_track(
            "Stay", artist="The Kid LAROI & Justin Bieber", duration_ms=141000
        )
        item = repository.create_platform_item(
            "APPLE_MUSIC",
            "apple-stay",
            "CATALOG_TRACK",
            "Stay",
            artist="The Kid LAROI & Justin Bieber",
            duration_ms=141000,
            release_date=date(2021, 7, 9),
        )

        outcome = TrackResolutionService(session).resolve(item.id)

        assert outcome.status is ResolutionStatus.MATCHED_HIGH_CONFIDENCE
        assert outcome.canonical_track_id == track.id

