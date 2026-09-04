from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from chart_observatory.artifacts.models import ArtifactContext
from chart_observatory.artifacts.store import ArtifactStore
from chart_observatory.domain.enums import RightsOperation, RightsProfileStatus
from chart_observatory.domain.errors import RightsDenied
from chart_observatory.rights.gate import RightsGate
from chart_observatory.rights.models import RightsGrant, RightsProfile
from chart_observatory.rights.repository import InMemoryRightsRepository

NOW = datetime(2026, 9, 3, tzinfo=UTC)


def _context(allowed: bool) -> tuple[RightsGate, ArtifactContext]:
    source_id, profile_id = uuid4(), uuid4()
    profile = RightsProfile(
        source_id=source_id,
        status=RightsProfileStatus.APPROVED,
        valid_from=NOW - timedelta(days=1),
        valid_until=None,
        grants=(RightsGrant(profile_id, RightsOperation.STORE_RAW, allowed),),
        id=profile_id,
    )
    return RightsGate(InMemoryRightsRepository([profile])), ArtifactContext(
        source_id=source_id,
        occurred_at=NOW,
        media_type="text/plain",
        collector_version="test",
        schema_version="v1",
    )


def test_same_bytes_reuse_checksum_without_overwrite(tmp_path) -> None:
    gate, context = _context(True)
    store = ArtifactStore(tmp_path, gate)
    first = store.put(b"synthetic", context)
    second = store.put(b"synthetic", context)
    assert first.sha256 == second.sha256
    assert first.path == second.path
    assert first.path.read_bytes() == b"synthetic"


def test_raw_storage_is_denied_without_grant(tmp_path) -> None:
    gate, context = _context(False)
    with pytest.raises(RightsDenied):
        ArtifactStore(tmp_path, gate).put(b"synthetic", context)
