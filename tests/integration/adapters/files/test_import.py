from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from chart_observatory.adapters.files.manual import (
    ImportRequest,
    InMemoryImportSink,
    ManualChartImporter,
    SqlManualImportSink,
)
from chart_observatory.artifacts.repository import SqlArtifactCatalog
from chart_observatory.artifacts.store import ArtifactStore
from chart_observatory.db.base import Base
from chart_observatory.db.models.audit import AuditEvent
from chart_observatory.db.models.charts import ChartEntry
from chart_observatory.db.models.provenance import SourceArtifact
from chart_observatory.domain.enums import RightsOperation, RightsProfileStatus
from chart_observatory.rights.gate import RightsGate
from chart_observatory.rights.models import RightsGrant, RightsProfile
from chart_observatory.rights.repository import InMemoryRightsRepository

FIXTURE = Path(__file__).parents[3] / "fixtures" / "manual" / "valid_daily.csv"
NOW = datetime(2026, 9, 3, tzinfo=UTC)


def test_reimport_is_idempotent(tmp_path) -> None:
    source_id, profile_id = uuid4(), uuid4()
    grants = tuple(
        RightsGrant(profile_id, operation, True)
        for operation in (
            RightsOperation.IMPORT,
            RightsOperation.STORE_RAW,
            RightsOperation.STORE_NORMALIZED,
        )
    )
    profile = RightsProfile(
        source_id=source_id,
        status=RightsProfileStatus.APPROVED,
        valid_from=NOW - timedelta(days=1),
        valid_until=None,
        grants=grants,
        id=profile_id,
    )
    gate = RightsGate(InMemoryRightsRepository([profile]))
    sink = InMemoryImportSink()
    importer = ManualChartImporter(
        source_id=source_id,
        rights_gate=gate,
        artifact_store=ArtifactStore(tmp_path, gate),
        sink=sink,
    )
    request = ImportRequest(FIXTURE, "manual_generic_v1", NOW)
    first = importer.import_file(request)
    second = importer.import_file(request)
    assert first.snapshot_id == second.snapshot_id
    assert second.created_entries == 0
    assert len(sink.rows) == 3


def test_sql_sink_persists_unresolved_rows_transactionally(tmp_path) -> None:
    source_id, profile_id = uuid4(), uuid4()
    grants = tuple(
        RightsGrant(profile_id, operation, True)
        for operation in (
            RightsOperation.IMPORT,
            RightsOperation.STORE_RAW,
            RightsOperation.STORE_NORMALIZED,
        )
    )
    profile = RightsProfile(
        source_id=source_id,
        status=RightsProfileStatus.APPROVED,
        valid_from=NOW - timedelta(days=1),
        valid_until=None,
        grants=grants,
        id=profile_id,
    )
    gate = RightsGate(InMemoryRightsRepository([profile]))
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        importer = ManualChartImporter(
            source_id=source_id,
            rights_gate=gate,
            artifact_store=ArtifactStore(tmp_path, gate),
            artifact_catalog=SqlArtifactCatalog(session),
            sink=SqlManualImportSink(session),
        )
        result = importer.import_file(ImportRequest(FIXTURE, "manual_generic_v1", NOW))
        assert result.created_entries == 3
        assert session.scalar(select(func.count(ChartEntry.id))) == 3
        assert all(
            entry.canonical_track_id is None for entry in session.scalars(select(ChartEntry))
        )
        assert session.scalar(select(func.count(SourceArtifact.id))) == 1
        assert session.scalar(select(AuditEvent.event_type)) == "IMPORT"
