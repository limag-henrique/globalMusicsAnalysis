from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.resolution import ResolutionRecord
from chart_observatory.tracks.repository import TrackRepository
from chart_observatory.tracks.resolution import TrackResolutionService


def test_resolution_attempt_persists_rule_evidence_and_candidates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repository = TrackRepository(session)
        repository.create_track("Synthetic Song")
        item = repository.create_platform_item(
            "APPLE_MUSIC", "candidate", "CATALOG_TRACK", "Synthetik Song"
        )
        TrackResolutionService(session).resolve(item.id)
        record = session.scalar(select(ResolutionRecord))
        assert record is not None
        assert record.rule_version == "resolution-v1"
        assert record.evidence == "FUZZY_CANDIDATE_ONLY"
        assert session.scalar(select(func.count(ResolutionRecord.id))) == 1
