from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from chart_observatory.adapters.apple_music.charts import AppleMusicChartSource
from chart_observatory.adapters.http import HttpPolicy
from chart_observatory.charts.ports import CurrentChartRequest
from chart_observatory.domain.enums import RightsOperation, RightsProfileStatus
from chart_observatory.domain.errors import SourceDisabled
from chart_observatory.rights.gate import RightsGate
from chart_observatory.rights.models import RightsGrant, RightsProfile
from chart_observatory.rights.repository import InMemoryRightsRepository

FIXTURE = Path(__file__).parents[2] / "fixtures" / "apple_music" / "charts_songs_br.json"


class SpyTransport:
    called = False

    def send(self, request):
        self.called = True
        raise AssertionError("network must stay disabled")


def test_apple_request_is_current_songs_chart() -> None:
    source = AppleMusicChartSource(uuid4(), transport=SpyTransport(), network_enabled=False)
    request = source.build_request(storefront="br", limit=200)
    assert request.path == "/v1/catalog/br/charts"
    assert request.params == {"types": "songs", "chart": "most-played", "limit": 200}


def test_disabled_fetch_fails_before_transport() -> None:
    transport = SpyTransport()
    source = AppleMusicChartSource(uuid4(), transport=transport, network_enabled=False)
    with pytest.raises(SourceDisabled):
        source.fetch("br", 200, datetime(2026, 9, 3, tzinfo=UTC))
    assert transport.called is False


def test_common_chart_source_entrypoint_is_also_disabled_before_transport() -> None:
    transport = SpyTransport()
    source = AppleMusicChartSource(uuid4(), transport=transport, network_enabled=False)
    with pytest.raises(SourceDisabled):
        source.fetch_current(CurrentChartRequest("BR", "most-played"))
    assert transport.called is False


@dataclass
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes


class RetryingTransport:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, request: object) -> HttpResponse:
        self.calls += 1
        if self.calls == 1:
            return HttpResponse(429, {"Retry-After": "0"}, b"rate limited")
        return HttpResponse(200, {}, FIXTURE.read_bytes())


class TokenProvider:
    def developer_token(self) -> str:
        return "fixture-token"


def test_enabled_fixture_fetch_uses_bounded_http_policy() -> None:
    now = datetime(2026, 9, 4, tzinfo=UTC)
    source_id, profile_id = uuid4(), uuid4()
    profile = RightsProfile(
        source_id=source_id,
        status=RightsProfileStatus.APPROVED,
        valid_from=now - timedelta(days=1),
        valid_until=None,
        grants=(RightsGrant(profile_id, RightsOperation.FETCH, True),),
        id=profile_id,
    )
    transport = RetryingTransport()
    source = AppleMusicChartSource(
        source_id,
        transport=transport,
        network_enabled=True,
        rights_gate=RightsGate(InMemoryRightsRepository([profile])),
        token_provider=TokenProvider(),
        http_policy=HttpPolicy(max_attempts=2),
        sleep=lambda _: None,
    )
    payload = source.fetch("br", 200, now)
    assert payload.entries[0].native_id == "apple-1"
    assert transport.calls == 2
