import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from chart_observatory.adapters.http import HttpPolicy
from chart_observatory.adapters.youtube_data.categories import (
    map_categories,
    map_regions,
)
from chart_observatory.adapters.youtube_data.mapper import map_most_popular_page
from chart_observatory.adapters.youtube_data.most_popular import (
    YouTubeApiError,
    YouTubeMostPopularSource,
    YouTubeQuotaExceeded,
)
from chart_observatory.domain.enums import RightsOperation, RightsProfileStatus
from chart_observatory.domain.errors import RightsDenied, SourceDisabled
from chart_observatory.rights.gate import RightsGate
from chart_observatory.rights.models import RightsGrant, RightsProfile
from chart_observatory.rights.repository import InMemoryRightsRepository

FIXTURES = Path(__file__).parents[2] / "fixtures" / "youtube_data"
NOW = datetime(2026, 9, 4, tzinfo=UTC)


class NeverTransport:
    called = False

    def send(self, request: object) -> object:
        self.called = True
        raise AssertionError("disabled source must not reach transport")


@dataclass
class Response:
    status_code: int
    headers: dict[str, str]
    content: bytes


class PageTransport:
    def __init__(self, responses: list[Response | Exception]) -> None:
        self.responses = responses
        self.requests: list[object] = []

    def send(self, request: object) -> Response:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class KeyProvider:
    def api_key(self) -> str:
        return "fixture-key"


def _enabled_source(transport: PageTransport) -> YouTubeMostPopularSource:
    source_id, profile_id = uuid4(), uuid4()
    profile = RightsProfile(
        source_id=source_id,
        status=RightsProfileStatus.APPROVED,
        valid_from=NOW - timedelta(days=1),
        valid_until=None,
        grants=(RightsGrant(profile_id, RightsOperation.FETCH, True),),
        id=profile_id,
    )
    return YouTubeMostPopularSource(
        source_id,
        transport=transport,
        network_enabled=True,
        rights_gate=RightsGate(InMemoryRightsRepository([profile])),
        api_key_provider=KeyProvider(),
        http_policy=HttpPolicy(max_attempts=2, base_delay=0),
        sleep=lambda _: None,
    )


def test_region_and_assignable_category_discovery() -> None:
    regions = map_regions((FIXTURES / "regions.json").read_bytes())
    categories = map_categories((FIXTURES / "categories_br.json").read_bytes())
    assert {region.code for region in regions} == {
        "BR",
        "US",
        "GB",
        "FR",
        "DE",
        "ES",
        "PT",
        "IT",
        "SE",
    }
    assert [(category.id, category.title) for category in categories] == [
        ("10", "Music"),
        ("1", "Film & Animation"),
    ]


def test_video_mapping_preserves_video_identity_and_optional_statistics() -> None:
    page = map_most_popular_page((FIXTURES / "most_popular_br.json").read_bytes(), "BR", NOW)
    assert [entry.native_id for entry in page.entries] == ["br-video-a", "br-video-b"]
    assert page.entries[0].metric_type == "VIEWS"
    assert page.entries[0].metric_value == Decimal("1200")
    assert page.entries[1].metric_value is None
    assert "isrc" not in page.entries[0].raw_fields
    assert page.entries[0].raw_fields["view_count_definition_version"] == (
        "2025-03-31_SHORTS_STARTS_OR_REPLAYS"
    )


def test_requests_use_public_discovery_and_video_most_popular_endpoints() -> None:
    source = YouTubeMostPopularSource(uuid4(), transport=NeverTransport())
    assert source.build_regions_request().path == "/youtube/v3/i18nRegions"
    assert source.build_categories_request("BR").params == {
        "part": "snippet",
        "regionCode": "BR",
    }
    request = source.build_page_request("BR", "10", max_results=50, page_token="next")
    assert request.path == "/youtube/v3/videos"
    assert request.params == {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": "BR",
        "videoCategoryId": "10",
        "maxResults": 50,
        "pageToken": "next",
    }


def test_network_stays_disabled_before_transport() -> None:
    transport = NeverTransport()
    source = YouTubeMostPopularSource(uuid4(), transport=transport, network_enabled=False)
    with pytest.raises(SourceDisabled):
        source.fetch("BR", "10", NOW)
    assert transport.called is False


def test_capability_label_never_claims_youtube_music_equivalence() -> None:
    capabilities = YouTubeMostPopularSource(uuid4(), transport=NeverTransport()).capabilities()
    assert capabilities["chart_family"] == "YOUTUBE_VIDEO_MOST_POPULAR"
    assert capabilities["ranked_item_kind"] == "VIDEO"
    assert capabilities["chart_label"] == "YouTube Video Most Popular"
    assert capabilities["semantic_equivalence"] == "NOT_YOUTUBE_MUSIC_TOP_SONGS"


def test_paginated_fetch_preserves_raw_pages_and_accounts_for_quota() -> None:
    first = (FIXTURES / "most_popular_br_page1.json").read_bytes()
    second = (FIXTURES / "most_popular_br_page2.json").read_bytes()
    transport = PageTransport([Response(200, {}, first), Response(200, {}, second)])
    payload = _enabled_source(transport).fetch("BR", "10", NOW)
    assert [entry.position for entry in payload.entries] == [1, 2]
    assert payload.provider_metadata["quota_units"] == 2
    encoded_pages = json.loads(payload.raw_bytes)
    assert [base64.b64decode(page) for page in encoded_pages] == [first, second]


def test_quota_exhaustion_is_distinct_from_authorization_failure() -> None:
    transport = PageTransport([Response(403, {}, (FIXTURES / "quota_error.json").read_bytes())])
    with pytest.raises(YouTubeQuotaExceeded):
        _enabled_source(transport).fetch("BR", "10", NOW)


@pytest.mark.parametrize("status", [401, 403])
def test_permanent_authorization_errors_are_not_retried(status: int) -> None:
    transport = PageTransport(
        [Response(status, {}, b'{"error":{"errors":[{"reason":"forbidden"}]}}')]
    )
    with pytest.raises(RightsDenied):
        _enabled_source(transport).fetch("BR", "10", NOW)
    assert len(transport.requests) == 1


def test_ordinary_rate_limit_and_timeout_are_retried() -> None:
    success = Response(200, {}, (FIXTURES / "most_popular_br.json").read_bytes())
    rate_limited = PageTransport(
        [
            Response(429, {"Retry-After": "0"}, b'{"error":{"errors":[]}}'),
            success,
        ]
    )
    timed_out = PageTransport([TimeoutError("synthetic timeout"), success])
    assert len(_enabled_source(rate_limited).fetch("BR", "10", NOW).entries) == 2
    assert len(_enabled_source(timed_out).fetch("BR", "10", NOW).entries) == 2


def test_retried_requests_are_included_in_quota_accounting() -> None:
    success = Response(200, {}, (FIXTURES / "most_popular_br.json").read_bytes())
    transport = PageTransport(
        [
            Response(429, {"Retry-After": "0"}, b'{"error":{"errors":[]}}'),
            success,
        ]
    )
    payload = _enabled_source(transport).fetch("BR", "10", NOW)
    assert payload.provider_metadata["quota_units"] == 2


def test_bad_request_retry_exhaustion_and_malformed_json_fail_explicitly() -> None:
    bad_request = PageTransport(
        [Response(400, {}, b'{"error":{"errors":[{"reason":"badRequest"}]}}')]
    )
    exhausted = PageTransport([Response(500, {}, b"server"), Response(500, {}, b"server")])
    malformed = PageTransport([Response(200, {}, b"not-json")])
    with pytest.raises(YouTubeApiError):
        _enabled_source(bad_request).fetch("BR", "10", NOW)
    with pytest.raises(YouTubeApiError):
        _enabled_source(exhausted).fetch("BR", "10", NOW)
    with pytest.raises(json.JSONDecodeError):
        _enabled_source(malformed).fetch("BR", "10", NOW)


def test_empty_deleted_and_changed_category_records_are_preserved_safely() -> None:
    empty = map_most_popular_page(b'{"items":[]}', "BR", NOW)
    changed = map_most_popular_page(
        b'{"items":[{"id":"gone"},{"id":"moved","snippet":{"title":"Moved","categoryId":"20"}}]}',
        "BR",
        NOW,
    )
    assert empty.entries == ()
    assert changed.entries[0].raw_fields["availability"] == "UNAVAILABLE"
    assert changed.entries[1].raw_fields["video_category_id"] == "20"
