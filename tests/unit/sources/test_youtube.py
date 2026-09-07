import json
from dataclasses import dataclass

from chart_observatory.sources.youtube import YouTubeMarketDiscovery


@dataclass
class Response:
    status_code: int
    content: bytes


class Transport:
    def __init__(self) -> None:
        self.requests = []

    def send(self, request: object) -> Response:
        self.requests.append(request)
        return Response(
            200,
            json.dumps({"items": [{"id": "BR", "snippet": {"name": "Brazil"}}]}).encode(),
        )


def test_youtube_market_discovery_uses_official_regions_endpoint() -> None:
    transport = Transport()
    regions = YouTubeMarketDiscovery("secret", transport).discover_regions()
    assert regions[0].code == "BR"
    assert transport.requests[0].path == "/youtube/v3/i18nRegions"
    assert transport.requests[0].params["key"] == "secret"
