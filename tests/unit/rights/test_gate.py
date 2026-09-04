from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from chart_observatory.domain.enums import RightsOperation, RightsProfileStatus
from chart_observatory.domain.errors import RightsDenied
from chart_observatory.rights.gate import RightsGate
from chart_observatory.rights.models import RightsGrant, RightsProfile
from chart_observatory.rights.repository import InMemoryRightsRepository

NOW = datetime(2026, 9, 3, tzinfo=UTC)


def _profile(
    *operations: RightsOperation, status=RightsProfileStatus.APPROVED, valid_until=None
) -> RightsProfile:
    profile_id = uuid4()
    return RightsProfile(
        id=profile_id,
        source_id=uuid4(),
        status=status,
        valid_from=NOW - timedelta(days=1),
        valid_until=valid_until,
        grants=tuple(RightsGrant(profile_id, operation, True) for operation in operations),
    )


def test_pending_source_is_denied() -> None:
    profile = _profile(RightsOperation.FETCH, status=RightsProfileStatus.PENDING)
    decision = RightsGate(InMemoryRightsRepository([profile])).authorize(
        profile.source_id, RightsOperation.FETCH, NOW
    )
    assert decision.allowed is False
    assert decision.reason == "NO_ACTIVE_APPROVED_GRANT"


def test_each_operation_requires_its_own_grant() -> None:
    profile = _profile(RightsOperation.IMPORT)
    gate = RightsGate(InMemoryRightsRepository([profile]))
    gate.require(profile.source_id, RightsOperation.IMPORT, NOW)
    with pytest.raises(RightsDenied):
        gate.require(profile.source_id, RightsOperation.REDISTRIBUTE_ROWS, NOW)


def test_expiry_boundary_is_fail_closed() -> None:
    profile = _profile(RightsOperation.FETCH, valid_until=NOW)
    decision = RightsGate(InMemoryRightsRepository([profile])).authorize(
        profile.source_id, RightsOperation.FETCH, NOW
    )
    assert decision.allowed is False
    assert decision.reason == "NO_ACTIVE_APPROVED_GRANT"
