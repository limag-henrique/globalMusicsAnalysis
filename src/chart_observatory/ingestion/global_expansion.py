"""Population quotas and evidence-only national chart ingestion.

Current snapshots never become annual memberships or authorize paid acquisition.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

COEFFICIENT = 7.470872933481587


def required(parent: Tag, selector: str) -> Tag:
    node = parent.select_one(selector)
    if node is None:
        raise ValueError(f"missing required chart element: {selector}")
    return node


def african_ranking(html: str, source: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    published = None
    if source == "TURNTABLE_NG_COMPOSITE":
        data = json.loads(required(soup, "#__NEXT_DATA__").get_text())["props"]["pageProps"][
            "chartData"
        ]
        if data["category"] != "Official Nigeria Top 100" or data["isDeleted"]:
            raise ValueError("Nigeria chart identity mismatch")
        published = data["dateCreated"]
        for item in data["chartItems"]:
            rows.append(
                dict(
                    position=int(item["rank"]),
                    title=item["title"],
                    artist=item["artiste"],
                    native_observation_id=str(item["id"]),
                    url=item["musicLink"],
                )
            )
    elif source == "MDUNDO_KE_WEEKLY":
        heading = required(soup, "h1")
        if heading.get_text(" ", strip=True) != "Weekly Top 100 in Kenya":
            raise ValueError("Kenya chart identity mismatch")
        chart = heading.find_parent("section", class_="song-list_section")
        if chart is None:
            raise ValueError("missing chart container")
        for item in chart.select('li.str_off[data-element-type="song"]'):
            anchor = item.select_one("a.song-info")
            if not anchor:
                continue
            match = re.fullmatch(
                r"(\d+)\.\s+(.+)", required(anchor, ".song-author").get_text(" ", strip=True)
            )
            if not match:
                raise ValueError("missing explicit ordinal")
            href = anchor.get("href")
            if not isinstance(href, str):
                raise ValueError("invalid recording URL")
            recording_url = urljoin("https://mdundo.com", href)
            parts = urlsplit(recording_url)
            if (
                parts.hostname != "mdundo.com"
                or parts.scheme != "https"
                or parts.path != f"/song/{item['data-element-id']}"
            ):
                raise ValueError("recording URL identity mismatch")
            rows.append(
                dict(
                    position=int(match[1]),
                    title=required(anchor, ".song-title").get_text(" ", strip=True),
                    artist=match[2],
                    native_id=item["data-element-id"],
                    url=recording_url,
                )
            )
    else:
        raise ValueError("source not enabled")
    rows.sort(key=lambda r: r["position"])
    if len(rows) != 100 or [r["position"] for r in rows] != list(range(1, 101)):
        raise ValueError("incomplete or ambiguous Top 100")
    if any(not r["title"].strip() or not r["artist"].strip() for r in rows):
        raise ValueError("incomplete recording identity")
    return dict(
        rows=rows,
        source_published_at=published,
        period_scope="CURRENT_WEEKLY_SNAPSHOT",
        annual_rank_certified=False,
        classification_ready=False,
        lyrics_acquisition_ready=False,
        comparability="SEPARATE_SOURCE_FAMILY; country audience basis requires review"
        if source.startswith("MDUNDO")
        else "COMPOSITE_STREAMING_AND_AIRPLAY",
    )


def population_quota(population: int, diversity: float | None) -> int:
    if population <= 0 or (diversity is not None and not 0 <= diversity <= 1):
        raise ValueError("invalid demographic input")
    weight = math.sqrt(population / 1_000_000) * (1 + 0.5 * (diversity or 0))
    return min(500, 100 + 10 * math.floor(COEFFICIENT * weight / 10 + 1e-12))


def apple_ranking(html: str, expected_label: str, playlist_id: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    schema = json.loads(required(soup, 'script[id="schema:music-playlist"]').get_text())
    data = json.loads(required(soup, 'script[id="serialized-server-data"]').get_text())
    if schema.get("name") != expected_label:
        raise ValueError("chart country label mismatch")
    sections = data["data"][0]["data"]["sections"]
    headers = [s for s in sections if s.get("itemKind") == "containerDetailHeaderLockup"]
    tracks = [s for s in sections if s.get("itemKind") == "trackLockup"]
    if len(headers) != 1 or len(tracks) != 1:
        raise ValueError("ambiguous chart sections")
    if any(s["id"].rsplit(" - ", 1)[-1] != playlist_id for s in [headers[0], tracks[0]]):
        raise ValueError("playlist identity mismatch")
    if headers[0]["items"][0]["title"] != expected_label:
        raise ValueError("header country mismatch")
    rows = []
    for item in tracks[0]["items"]:
        descriptor = item["contentDescriptor"]
        if descriptor["kind"] != "song":
            raise ValueError("non-song chart item")
        row = dict(
            position=int(item["rankingText"]),
            title=item["title"],
            artist=item["artistName"],
            native_id=str(descriptor["identifiers"]["storeAdamID"]),
            url=descriptor["url"],
        )
        if not row["title"].strip() or not row["artist"].strip():
            raise ValueError("incomplete recording identity")
        rows.append(row)
    rows.sort(key=lambda r: r["position"])
    if [r["position"] for r in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("duplicate or missing ordinal position")
    if len({r["native_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate recording")
    if len(rows) != schema["numTracks"] or len(rows) != len(schema["track"]):
        raise ValueError("truncated chart")
    for row, reference in zip(rows, schema["track"], strict=True):
        reference_url = urlsplit(reference["url"])
        reference_id = parse_qs(reference_url.query).get("i")
        if reference_id is None and "/song/" in reference_url.path:
            reference_id = [reference_url.path.rsplit("/", 1)[-1]]
        if row["title"] != reference["name"] or reference_id != [row["native_id"]]:
            raise ValueError("independent playlist representations disagree")
    return dict(
        source_published_at=schema.get("datePublished"),
        rows=rows,
        period_scope="CURRENT_DAILY_SNAPSHOT",
        annual_rank_certified=False,
        classification_ready=False,
        lyrics_acquisition_ready=False,
    )
