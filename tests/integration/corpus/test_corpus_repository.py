from datetime import UTC, date, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from chart_observatory.charts.repository import ChartRepository
from chart_observatory.corpus.repository import (
    CorpusFreezeRequest,
    freeze_corpus,
    reconcile_entries,
)
from chart_observatory.db.base import Base
from chart_observatory.db.models.corpus import CanonicalChartEntry, CorpusMembership, SourceConflict
from chart_observatory.metadata.geography import geography_for_market
from chart_observatory.tracks.repository import TrackRepository


def test_reconciliation_collapses_duplicate_sources_and_records_rank_conflict() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        charts = ChartRepository(session)
        tracks = TrackRepository(session)
        track = tracks.create_track("Synthetic")
        definition_a = charts.create_definition("SPOTIFY", "MGD", "BR", "TOP_200", "DAILY", 200)
        definition_b = charts.create_definition(
            "SPOTIFY", "KAGGLE_DHRUVILDAVE", "BR", "TOP_200", "DAILY", 200
        )
        snap_a = charts.create_snapshot(
            definition_a.id,
            date(2021, 1, 1),
            date(2021, 1, 1),
            datetime(2021, 1, 1, tzinfo=UTC),
            "a",
        )
        snap_b = charts.create_snapshot(
            definition_b.id,
            date(2021, 1, 1),
            date(2021, 1, 1),
            datetime(2021, 1, 1, tzinfo=UTC),
            "b",
        )
        item_a = tracks.create_platform_item("SPOTIFY", "item-a", "CATALOG_TRACK")
        item_b = tracks.create_platform_item("SPOTIFY", "item-b", "CATALOG_TRACK")
        charts.add_entry(snap_a.id, item_a.id, 14, None, canonical_track_id=track.id)
        charts.add_entry(snap_b.id, item_b.id, 15, None, canonical_track_id=track.id)
        summary = reconcile_entries(session)
        assert summary.canonical_entries == 1
        assert summary.conflicts == 1
        assert session.scalar(select(CanonicalChartEntry).where(CanonicalChartEntry.rank == 14))
        assert session.scalar(select(SourceConflict))


def test_freeze_records_hash_and_membership() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        version = freeze_corpus(
            session,
            CorpusFreezeRequest(
                "Corpus",
                "v1",
                {"minimum_coverage": 0.95},
                ("snapshot",),
                date(2020, 1, 1),
                date(2022, 1, 1),
                ({"member_type": "CELL", "member_key": "MGD/SPOTIFY/BR/TOP_200"},),
            ),
        )
        assert len(version.manifest_sha256) == 64
        assert session.scalar(
            select(CorpusMembership).where(CorpusMembership.corpus_version_id == version.id)
        )


def test_geography_uses_iso_and_m49_metadata() -> None:
    record = geography_for_market("BR")
    assert record.iso3 == "BRA"
    assert record.m49 == "076"
    assert record.subregion == "South America"
