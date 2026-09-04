from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.charts.repository import ChartRepository
from chart_observatory.db.base import Base
from chart_observatory.metrics.track_summary import summarize_track_platform_country
from chart_observatory.tracks.repository import TrackRepository


def test_summary_query_reports_resolved_results_and_unresolved_denominator() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        charts = ChartRepository(session)
        tracks = TrackRepository(session)
        definition = charts.create_definition(
            "SPOTIFY", "MANUAL_AUTHORIZED_FILE", "BR", "top", "DAILY", 3
        )
        snapshot = charts.create_snapshot(
            definition.id,
            date(2026, 9, 4),
            date(2026, 9, 4),
            datetime(2026, 9, 4, tzinfo=UTC),
            "summary",
        )
        track = tracks.create_track("Resolved")
        for position in (1, 2, 3):
            item = tracks.create_platform_item("SPOTIFY", f"item-{position}", "CATALOG_TRACK")
            charts.add_entry(
                snapshot.id,
                item.id,
                position,
                None,
                canonical_track_id=track.id if position < 3 else None,
            )
        summary = summarize_track_platform_country(session, track.id, definition.id)
        assert summary.appearances == 2
        assert summary.peak_rank == 1
        assert summary.unresolved_numerator == 1
        assert summary.unresolved_denominator == 3
