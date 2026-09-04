from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.artifacts.models import StoredArtifact
from chart_observatory.db.models.audit import AuditEvent
from chart_observatory.db.models.provenance import SourceArtifact


class ArtifactCatalog(Protocol):
    def record_artifact(self, artifact: StoredArtifact, rights_profile_id: UUID) -> None: ...

    def record_event(self, event_type: str, actor: str, payload: dict[str, object]) -> None: ...


class SqlArtifactCatalog:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_artifact(self, artifact: StoredArtifact, rights_profile_id: UUID) -> None:
        existing = self.session.scalar(
            select(SourceArtifact.id).where(SourceArtifact.sha256 == artifact.sha256)
        )
        if existing is not None:
            return
        self.session.add(
            SourceArtifact(
                sha256=artifact.sha256,
                byte_size=artifact.byte_size,
                media_type=artifact.context.media_type,
                source_id=artifact.context.source_id,
                rights_profile_id=rights_profile_id,
                retrieved_at=artifact.context.occurred_at,
                collector_version=artifact.context.collector_version,
                schema_version=artifact.context.schema_version,
                acquisition_parameters=artifact.context.acquisition_parameters,
            )
        )
        self.session.flush()

    def record_event(self, event_type: str, actor: str, payload: dict[str, object]) -> None:
        self.session.add(AuditEvent(event_type=event_type, actor=actor, payload=payload))
        self.session.flush()
