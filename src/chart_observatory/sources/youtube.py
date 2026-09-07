from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chart_observatory.adapters.youtube_data.categories import (
    YouTubeRegion,
    YouTubeVideoCategory,
    map_categories,
    map_regions,
)


@dataclass(frozen=True)
class YouTubeDiscoveryRequest:
    path: str
    params: dict[str, object]
    method: str = "GET"
    body: None = None
    headers: dict[str, str] | None = None


class YouTubeMarketDiscovery:
    """Official region/category discovery; it does not label videos as music charts."""

    def __init__(self, api_key: str | None, transport: Any) -> None:
        self.api_key = api_key
        self.transport = transport

    def discover_regions(self) -> tuple[YouTubeRegion, ...]:
        response = self._send("/youtube/v3/i18nRegions", {"part": "snippet"})
        return map_regions(response.content)

    def discover_categories(self, region_code: str) -> tuple[YouTubeVideoCategory, ...]:
        response = self._send(
            "/youtube/v3/videoCategories", {"part": "snippet", "regionCode": region_code.upper()}
        )
        return map_categories(response.content)

    def _send(self, path: str, params: dict[str, object]) -> Any:
        if not self.api_key:
            raise RuntimeError("YouTube Data API key is not configured")
        request = YouTubeDiscoveryRequest(path, {**params, "key": self.api_key})
        response = self.transport.send(request)
        if response.status_code >= 400:
            raise RuntimeError(f"YouTube discovery failed ({response.status_code})")
        return response
