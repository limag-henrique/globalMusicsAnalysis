from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.charts.repository import ChartRepository
from chart_observatory.db.base import Base
from chart_observatory.tracks.repository import TrackRepository


def test_unresolved_entry_and_missing_metric_are_preserved() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        charts = ChartRepository(session)
        definition = charts.create_definition(
            "APPLE_MUSIC", "APPLE_MUSIC_API", "BR", "most-played", "DAILY", 100
        )
        snapshot = charts.create_snapshot(
            definition.id,
            date(2026, 9, 3),
            date(2026, 9, 3),
            datetime(2026, 9, 3, tzinfo=UTC),
            "abc",
        )
        item = TrackRepository(session).create_platform_item(
            "APPLE_MUSIC", "song-1", "CATALOG_TRACK"
        )
        entry = charts.add_entry(snapshot.id, item.id, position=1, metric_value=None)
        assert entry.canonical_track_id is None
        assert entry.metric_value is None


def test_correction_supersedes_without_mutating_original() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = ChartRepository(session)
        definition = repo.create_definition("SPOTIFY", "SOUNDCHARTS", "BR", "top", "WEEKLY", 200)
        first = repo.create_snapshot(
            definition.id,
            date(2026, 8, 28),
            date(2026, 9, 3),
            datetime(2026, 9, 3, tzinfo=UTC),
            "first",
        )
        correction = repo.create_snapshot(
            definition.id,
            date(2026, 8, 28),
            date(2026, 9, 3),
            datetime(2026, 9, 4, tzinfo=UTC),
            "second",
            supersedes_snapshot_id=first.id,
        )
        assert correction.id != first.id
        assert correction.supersedes_snapshot_id == first.id
        assert first.checksum == "first"
