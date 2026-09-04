from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from chart_observatory.domain.enums import RightsOperation, RightsProfileStatus


@dataclass(frozen=True)
class RightsGrant:
    profile_id: UUID
    operation: RightsOperation
    allowed: bool


@dataclass(frozen=True)
class RightsProfile:
    source_id: UUID
    status: RightsProfileStatus
    valid_from: datetime
    valid_until: datetime | None
    grants: tuple[RightsGrant, ...] = field(default_factory=tuple)
    id: UUID = field(default_factory=uuid4)

    def is_active_at(self, occurred_at: datetime) -> bool:
        return (
            self.status is RightsProfileStatus.APPROVED
            and self.valid_from <= occurred_at
            and (self.valid_until is None or occurred_at < self.valid_until)
        )


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    profile_id: UUID | None = None
