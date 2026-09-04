from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.charts.collection_runs import CollectionRunRepository
from chart_observatory.charts.repository import ChartRepository
from chart_observatory.db.base import Base
from chart_observatory.domain.enums import CoverageStatus


def test_outage_attempt_does_not_erase_prior_available_coverage() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        definition = ChartRepository(session).create_definition(
            "APPLE_MUSIC", "APPLE_MUSIC_API", "BR", "most-played", "DAILY", 100
        )
        repository = CollectionRunRepository(session)
        available = repository.record_attempt(
            definition.id,
            datetime(2026, 9, 3, tzinfo=UTC),
            date(2026, 9, 3),
            date(2026, 9, 3),
            CoverageStatus.AVAILABLE,
        )
        outage = repository.record_attempt(
            definition.id,
            datetime(2026, 9, 4, tzinfo=UTC),
            date(2026, 9, 3),
            date(2026, 9, 3),
            CoverageStatus.SOURCE_UNAVAILABLE,
        )
        history = repository.coverage_history(definition.id)
        assert available.id != outage.id
        assert [cell.status for cell in history] == ["AVAILABLE", "SOURCE_UNAVAILABLE"]
