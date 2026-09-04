from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from chart_observatory.artifacts.models import ArtifactContext, StoredArtifact
from chart_observatory.artifacts.repository import SqlArtifactCatalog
from chart_observatory.db.base import Base
from chart_observatory.db.models.audit import AuditEvent
from chart_observatory.db.models.provenance import SourceArtifact


def test_catalog_is_idempotent_and_audit_events_append() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    source_id, profile_id = uuid4(), uuid4()
    context = ArtifactContext(
        source_id, datetime(2026, 9, 4, tzinfo=UTC), "application/json", "test", "v1"
    )
    artifact = StoredArtifact("a" * 64, Path("synthetic"), 9, context)
    with Session(engine) as session:
        catalog = SqlArtifactCatalog(session)
        catalog.record_artifact(artifact, profile_id)
        catalog.record_artifact(artifact, profile_id)
        catalog.record_event("EXPORT", "test", {"dataset": "coverage_matrix"})
        assert session.scalar(select(func.count(SourceArtifact.id))) == 1
        assert session.scalar(select(AuditEvent.event_type)) == "EXPORT"
