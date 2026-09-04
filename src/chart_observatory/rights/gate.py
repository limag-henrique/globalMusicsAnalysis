from datetime import datetime
from uuid import UUID

from chart_observatory.domain.enums import RightsOperation
from chart_observatory.domain.errors import RightsDenied
from chart_observatory.rights.models import AuthorizationDecision
from chart_observatory.rights.repository import RightsRepository


class RightsGate:
    def __init__(self, repository: RightsRepository) -> None:
        self.repository = repository

    def authorize(
        self, source_id: UUID, operation: RightsOperation, occurred_at: datetime
    ) -> AuthorizationDecision:
        active = [
            profile
            for profile in self.repository.profiles_for(source_id, occurred_at)
            if profile.is_active_at(occurred_at)
        ]
        allowed_profiles = []
        for profile in active:
            matching = [grant.allowed for grant in profile.grants if grant.operation is operation]
            if matching == [True]:
                allowed_profiles.append(profile)
        if len(allowed_profiles) == 1:
            return AuthorizationDecision(True, "ACTIVE_APPROVED_GRANT", allowed_profiles[0].id)
        return AuthorizationDecision(False, "NO_ACTIVE_APPROVED_GRANT")

    def require(self, source_id: UUID, operation: RightsOperation, occurred_at: datetime) -> None:
        decision = self.authorize(source_id, operation, occurred_at)
        if not decision.allowed:
            raise RightsDenied(f"{operation}: {decision.reason}")
