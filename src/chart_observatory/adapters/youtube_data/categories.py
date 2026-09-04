import json
from dataclasses import dataclass


@dataclass(frozen=True)
class YouTubeRegion:
    code: str
    name: str


@dataclass(frozen=True)
class YouTubeVideoCategory:
    id: str
    title: str


def map_regions(raw: bytes) -> tuple[YouTubeRegion, ...]:
    document = json.loads(raw)
    return tuple(
        YouTubeRegion(str(item["id"]), str(item.get("snippet", {}).get("name", "")))
        for item in document.get("items", [])
    )


def map_categories(raw: bytes) -> tuple[YouTubeVideoCategory, ...]:
    document = json.loads(raw)
    return tuple(
        YouTubeVideoCategory(str(item["id"]), str(item.get("snippet", {}).get("title", "")))
        for item in document.get("items", [])
        if item.get("snippet", {}).get("assignable") is True
    )
