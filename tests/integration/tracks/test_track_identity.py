from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.tracks.repository import TrackRepository


def test_multiple_videos_remain_distinct_for_one_recording() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = TrackRepository(session)
        track = repo.create_track(title="Synthetic Song")
        video_a = repo.create_platform_item("YOUTUBE_VIDEO", "video-a", "VIDEO")
        video_b = repo.create_platform_item("YOUTUBE_VIDEO", "video-b", "VIDEO")
        repo.link_item(track.id, video_a.id, evidence="HUMAN_REVIEW")
        repo.link_item(track.id, video_b.id, evidence="HUMAN_REVIEW")
        session.flush()
        assert video_a.id != video_b.id
        assert [item.native_id for item in repo.items_for_track(track.id)] == ["video-a", "video-b"]


def test_conflicting_isrc_claims_are_retained() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = TrackRepository(session)
        first = repo.create_track(title="First")
        second = repo.create_track(title="Second")
        repo.claim_external_id(first.id, "ISRC", "br-abc-21-00001", "SOURCE_A")
        repo.claim_external_id(second.id, "ISRC", "BRABC2100001", "SOURCE_B")
        session.flush()
        assert len(repo.claims_for("ISRC", "BRABC2100001")) == 2
