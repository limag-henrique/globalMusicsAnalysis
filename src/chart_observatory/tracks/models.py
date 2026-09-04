from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ExternalId:
    namespace: str
    raw_value: str
    normalized_value: str
    source_code: str
    canonical_track_id: UUID | None = None
    platform_item_id: UUID | None = None
