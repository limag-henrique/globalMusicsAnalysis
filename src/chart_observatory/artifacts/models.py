from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True)
class ArtifactContext:
    source_id: UUID
    occurred_at: datetime
    media_type: str
    collector_version: str
    schema_version: str
    acquisition_parameters: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class StoredArtifact:
    sha256: str
    path: Path
    byte_size: int
    context: ArtifactContext
