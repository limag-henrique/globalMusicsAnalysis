import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from chart_observatory.adapters.apple_music.mapper import map_chart_payload
from chart_observatory.adapters.http import HttpPolicy, execute_http
from chart_observatory.charts.dto import ChartPayload
from chart_observatory.charts.ports import CurrentChartRequest
from chart_observatory.domain.enums import RightsOperation
from chart_observatory.domain.errors import RightsDenied, SourceDisabled
from chart_observatory.rights.gate import RightsGate


@dataclass(frozen=True)
class AppleRequest:
    path: str
    params: dict[str, object]
    correlation_id: str
    authorization: str | None = None


class AppleMusicChartSource:
    def __init__(
        self,
        source_id: UUID,
        *,
        transport: Any,
        network_enabled: bool = False,
        rights_gate: RightsGate | None = None,
        token_provider: Any = None,
        http_policy: HttpPolicy | None = None,
        sleep: Callable[[float], object] = time.sleep,
    ) -> None:
        self.source_id = source_id
        self.transport = transport
        self.network_enabled = network_enabled
        self.rights_gate = rights_gate
        self.token_provider = token_provider
        self.http_policy = http_policy or HttpPolicy()
        self.sleep = sleep

    def capabilities(self) -> dict[str, object]:
        return {"current_only": True, "max_limit": 200, "network_enabled": self.network_enabled}

    def build_request(self, storefront: str, limit: int = 200) -> AppleRequest:
        if not 1 <= limit <= 200:
            raise ValueError("Apple chart limit must be between 1 and 200")
        return AppleRequest(
            f"/v1/catalog/{storefront.lower()}/charts",
            {"types": "songs", "chart": "most-played", "limit": limit},
            str(uuid4()),
        )

    def fetch(self, storefront: str, limit: int, occurred_at: datetime) -> ChartPayload:
        if not self.network_enabled:
            raise SourceDisabled("Apple Music network collection is disabled")
        if self.rights_gate is None:
            raise RightsDenied("Apple Music has no configured rights gate")
        self.rights_gate.require(self.source_id, RightsOperation.FETCH, occurred_at)
        if self.token_provider is None:
            raise RightsDenied("Apple Music credentials are unavailable")
        base = self.build_request(storefront, limit)
        request = AppleRequest(
            base.path, base.params, base.correlation_id, self.token_provider.developer_token()
        )
        response = execute_http(self.transport, request, self.http_policy, sleep=self.sleep)
        if response.status_code in (401, 403):
            raise RightsDenied(f"Apple Music rejected authorization ({response.status_code})")
        if response.status_code >= 400:
            raise RuntimeError(f"Apple Music request failed ({response.status_code})")
        return map_chart_payload(response.content, storefront, occurred_at)

    def fetch_current(self, request: CurrentChartRequest) -> ChartPayload:
        if request.chart_name != "most-played":
            raise ValueError("Apple Music adapter supports only the most-played songs chart")
        return self.fetch(request.country_code.lower(), 200, datetime.now(UTC))
