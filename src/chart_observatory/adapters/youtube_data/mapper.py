import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from chart_observatory.charts.dto import ChartEntryDTO

VIEW_COUNT_DEFINITION_VERSION = "2025-03-31_SHORTS_STARTS_OR_REPLAYS"


@dataclass(frozen=True)
class YouTubePage:
    entries: tuple[ChartEntryDTO, ...]
    next_page_token: str | None
    total_results: int | None
    raw_bytes: bytes


def map_most_popular_page(
    raw: bytes, region_code: str, observed_at: datetime, start_position: int = 1
) -> YouTubePage:
    document = json.loads(raw)
    entries: list[ChartEntryDTO] = []
    for offset, item in enumerate(document.get("items", [])):
        snippet = item.get("snippet") or {}
        statistics = item.get("statistics") or {}
        view_count = statistics.get("viewCount")
        raw_fields: dict[str, object] = {
            "channel_id": snippet.get("channelId"),
            "channel_title": snippet.get("channelTitle"),
            "published_at": snippet.get("publishedAt"),
            "video_category_id": snippet.get("categoryId"),
            "region_code": region_code.upper(),
            "availability": "AVAILABLE" if snippet else "UNAVAILABLE",
            "view_count_definition_version": VIEW_COUNT_DEFINITION_VERSION,
        }
        for key, value in statistics.items():
            raw_fields[f"statistics_{key}"] = value
        entries.append(
            ChartEntryDTO(
                position=start_position + offset,
                native_id=str(item["id"]),
                item_kind="VIDEO",
                metric_value=Decimal(str(view_count)) if view_count is not None else None,
                metric_type="VIEWS" if view_count is not None else "NONE",
                raw_fields=raw_fields,
                title=snippet.get("title"),
            )
        )
    page_info = document.get("pageInfo") or {}
    total = page_info.get("totalResults")
    return YouTubePage(
        tuple(entries),
        document.get("nextPageToken"),
        int(total) if total is not None else None,
        raw,
    )
