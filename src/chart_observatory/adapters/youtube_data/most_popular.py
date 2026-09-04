import base64
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from chart_observatory.adapters.http import HttpPolicy, execute_http
from chart_observatory.adapters.youtube_data.categories import (
    YouTubeRegion,
    YouTubeVideoCategory,
    map_categories,
    map_regions,
)
from chart_observatory.adapters.youtube_data.mapper import (
    VIEW_COUNT_DEFINITION_VERSION,
    map_most_popular_page,
)
from chart_observatory.charts.dto import ChartEntryDTO, ChartPayload
from chart_observatory.charts.ports import CurrentChartRequest
from chart_observatory.domain.enums import RightsOperation
from chart_observatory.domain.errors import RightsDenied, SourceDisabled
from chart_observatory.rights.gate import RightsGate


class YouTubeApiError(RuntimeError):
    pass


class YouTubeQuotaExceeded(YouTubeApiError):
    pass


@dataclass(frozen=True)
class YouTubeRequest:
    path: str
    params: dict[str, object]
    correlation_id: str
    api_key: str | None = field(default=None, repr=False)


class YouTubeMostPopularSource:
    QUOTA_UNITS_PER_LIST = 1

    def __init__(
        self,
        source_id: UUID,
        *,
        transport: Any,
        network_enabled: bool = False,
        rights_gate: RightsGate | None = None,
        api_key_provider: Any = None,
        http_policy: HttpPolicy | None = None,
        sleep: Callable[[float], object] = time.sleep,
    ) -> None:
        self.source_id = source_id
        self.transport = transport
        self.network_enabled = network_enabled
        self.rights_gate = rights_gate
        self.api_key_provider = api_key_provider
        self.http_policy = http_policy or HttpPolicy()
        self.sleep = sleep

    def capabilities(self) -> dict[str, object]:
        return {
            "chart_family": "YOUTUBE_VIDEO_MOST_POPULAR",
            "ranked_item_kind": "VIDEO",
            "chart_label": "YouTube Video Most Popular",
            "semantic_equivalence": "NOT_YOUTUBE_MUSIC_TOP_SONGS",
            "current_only": True,
            "max_page_size": 50,
            "network_enabled": self.network_enabled,
        }

    def build_regions_request(self) -> YouTubeRequest:
        return YouTubeRequest("/youtube/v3/i18nRegions", {"part": "snippet"}, str(uuid4()))

    def build_categories_request(self, region_code: str) -> YouTubeRequest:
        return YouTubeRequest(
            "/youtube/v3/videoCategories",
            {"part": "snippet", "regionCode": region_code.upper()},
            str(uuid4()),
        )

    def build_page_request(
        self,
        region_code: str,
        category_id: str,
        *,
        max_results: int = 50,
        page_token: str | None = None,
    ) -> YouTubeRequest:
        if not 1 <= max_results <= 50:
            raise ValueError("YouTube maxResults must be between 1 and 50")
        params: dict[str, object] = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": region_code.upper(),
            "videoCategoryId": category_id,
            "maxResults": max_results,
        }
        if page_token:
            params["pageToken"] = page_token
        return YouTubeRequest("/youtube/v3/videos", params, str(uuid4()))

    def discover_regions(self, occurred_at: datetime) -> tuple[YouTubeRegion, ...]:
        raw, _ = self._send(self.build_regions_request(), occurred_at)
        return map_regions(raw)

    def discover_categories(
        self, region_code: str, occurred_at: datetime
    ) -> tuple[YouTubeVideoCategory, ...]:
        raw, _ = self._send(self.build_categories_request(region_code), occurred_at)
        return map_categories(raw)

    def fetch(self, region_code: str, category_id: str, occurred_at: datetime) -> ChartPayload:
        raw_pages: list[bytes] = []
        entries: list[ChartEntryDTO] = []
        page_token: str | None = None
        quota_units = 0
        while True:
            raw, attempts = self._send(
                self.build_page_request(region_code, category_id, page_token=page_token),
                occurred_at,
            )
            quota_units += attempts * self.QUOTA_UNITS_PER_LIST
            page = map_most_popular_page(raw, region_code, occurred_at, len(entries) + 1)
            raw_pages.append(raw)
            entries.extend(page.entries)
            page_token = page.next_page_token
            if not page_token:
                break
        raw_envelope = json.dumps(
            [base64.b64encode(page).decode("ascii") for page in raw_pages],
            separators=(",", ":"),
        ).encode()
        return ChartPayload(
            source_code="YOUTUBE_DATA_API",
            platform_code="YOUTUBE_VIDEO",
            country_code=region_code.upper(),
            chart_name="YouTube Video Most Popular",
            native_frequency="DAILY",
            observed_at=occurred_at,
            raw_bytes=raw_envelope,
            entries=tuple(entries),
            provider_metadata={
                "video_category_id": category_id,
                "quota_units": quota_units,
                "view_count_definition_version": VIEW_COUNT_DEFINITION_VERSION,
                "semantic_equivalence": "NOT_YOUTUBE_MUSIC_TOP_SONGS",
            },
        )

    def fetch_current(self, request: CurrentChartRequest) -> ChartPayload:
        prefix = "most-popular:"
        if not request.chart_name.startswith(prefix):
            raise ValueError("YouTube chart must specify most-popular:<video-category-id>")
        return self.fetch(
            request.country_code,
            request.chart_name.removeprefix(prefix),
            datetime.now(UTC),
        )

    def _send(self, request: YouTubeRequest, occurred_at: datetime) -> tuple[bytes, int]:
        if not self.network_enabled:
            raise SourceDisabled("YouTube Data API network collection is disabled")
        if self.rights_gate is None:
            raise RightsDenied("YouTube Data API has no configured rights gate")
        self.rights_gate.require(self.source_id, RightsOperation.FETCH, occurred_at)
        if self.api_key_provider is None:
            raise RightsDenied("YouTube Data API credentials are unavailable")
        authorized = YouTubeRequest(
            request.path,
            request.params,
            request.correlation_id,
            self.api_key_provider.api_key(),
        )
        attempts = 0

        def record_attempt() -> None:
            nonlocal attempts
            attempts += 1

        response = execute_http(
            self.transport,
            authorized,
            self.http_policy,
            sleep=self.sleep,
            on_attempt=record_attempt,
        )
        if response.status_code >= 400:
            reason = self._error_reason(response.content)
            if reason in {"quotaExceeded", "dailyLimitExceeded"}:
                raise YouTubeQuotaExceeded(reason)
            if response.status_code in {401, 403}:
                raise RightsDenied(f"YouTube authorization rejected ({response.status_code})")
            raise YouTubeApiError(f"YouTube request failed ({response.status_code}, {reason})")
        return bytes(response.content), attempts

    @staticmethod
    def _error_reason(raw: bytes) -> str:
        try:
            errors = json.loads(raw).get("error", {}).get("errors", [])
            return str(errors[0].get("reason", "unknown")) if errors else "unknown"
        except (AttributeError, IndexError, json.JSONDecodeError):
            return "malformed_error"
