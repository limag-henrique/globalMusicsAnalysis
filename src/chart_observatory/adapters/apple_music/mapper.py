import json
from datetime import datetime

from chart_observatory.charts.dto import ChartEntryDTO, ChartPayload


def map_chart_payload(raw: bytes, storefront: str, observed_at: datetime) -> ChartPayload:
    document = json.loads(raw)
    charts = document.get("results", {}).get("songs", [])
    data = charts[0].get("data", []) if charts else []
    entries = []
    for position, item in enumerate(data, start=1):
        attributes = item.get("attributes", {})
        raw_fields = {
            "isrc": attributes.get("isrc"),
            "artistName": attributes.get("artistName"),
            "albumName": attributes.get("albumName"),
            "releaseDate": attributes.get("releaseDate"),
            "contentRating": attributes.get("contentRating"),
            "genreNames": attributes.get("genreNames", []),
        }
        entries.append(
            ChartEntryDTO(
                position,
                str(item["id"]),
                "CATALOG_TRACK",
                None,
                "NONE",
                raw_fields,
                attributes.get("name"),
            )
        )
    return ChartPayload(
        "APPLE_MUSIC_API",
        "APPLE_MUSIC",
        storefront.upper(),
        "most-played",
        "DAILY",
        observed_at,
        raw,
        tuple(entries),
    )
