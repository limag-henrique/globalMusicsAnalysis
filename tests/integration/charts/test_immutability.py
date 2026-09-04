from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from chart_observatory.charts.repository import ChartRepository
from chart_observatory.db.base import Base
from chart_observatory.tracks.repository import TrackRepository


def test_orm_rejects_snapshot_updates_and_entry_deletes() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        charts = ChartRepository(session)
        definition = charts.create_definition(
            "APPLE_MUSIC", "APPLE_MUSIC_API", "BR", "most-played", "DAILY", 100
        )
        snapshot = charts.create_snapshot(
            definition.id,
            date(2026, 9, 4),
            date(2026, 9, 4),
            datetime(2026, 9, 4, tzinfo=UTC),
            "immutable",
        )
        item = TrackRepository(session).create_platform_item(
            "APPLE_MUSIC", "immutable-item", "CATALOG_TRACK"
        )
        entry = charts.add_entry(snapshot.id, item.id, 1, None)
        session.commit()

        snapshot.entry_count = 99
        with pytest.raises(InvalidRequestError, match="immutable chart record"):
            session.flush()
        session.rollback()

        session.delete(entry)
        with pytest.raises(InvalidRequestError, match="immutable chart record"):
            session.flush()
