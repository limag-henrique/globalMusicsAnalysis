"""Build a separate TopHit Russia 2025 annual all-internet chart packet."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = Path(
    "data/raw/national_charts/tophit_ru_annual_2025/"
    "tophit-top-all-internet-hits-russia-annual-2025-archive-20260106.html"
)
PACKET_PATH = Path(
    "data/derived/annual_revision/provider_series/"
    "tophit-russia-top-all-internet-hits-annual-2025"
)
SERIES_ID = "TOPHIT_TOP_ALL_INTERNET_HITS_RU_2025"
OFFICIAL_SOURCE_URL = "https://tophit.com/chart/top/internet/hits/ru/annual/2025"
ARCHIVE_SOURCE_URL = (
    "https://web.archive.org/web/20260106184455id_/"
    "https://tophit.com/chart/top/internet/hits/ru/annual/2025"
)
EXPECTED_FILTER = {
    "variant": "top",
    "category": "internet",
    "type": "hits",
    "region": "ru",
    "period": "annual",
    "periodStart": "2025",
}
METRIC_FIELDS = ("airs", "youtubeViews", "spotifyStreams")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_chart(path: Path) -> dict[str, Any]:
    html = path.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
    )
    if not match:
        raise ValueError("TopHit archive page has no Next.js page payload")
    next_data = json.loads(match.group(1))
    compressed = base64.b64decode(next_data["props"]["pageProps"]["data"])
    payload = json.loads(zlib.decompress(compressed))

    if payload.get("chartName") != "Top All Internet Hits Russia Annual Chart":
        raise ValueError(f"unexpected TopHit chart name: {payload.get('chartName')!r}")
    if payload.get("filter") != EXPECTED_FILTER:
        raise ValueError(f"unexpected TopHit chart filter: {payload.get('filter')!r}")
    rows = payload.get("charts")
    if not isinstance(rows, list) or len(rows) != 200:
        raise ValueError(f"expected 200 chart rows, got {len(rows) if rows else 0}")

    positions = [int(row["position"]) for row in rows]
    if positions != list(range(1, 201)):
        raise ValueError("TopHit published positions are not the complete 1..200 sequence")
    if any(int(row.get("top") or 0) != 200 for row in rows):
        raise ValueError("TopHit row depth field differs from the chart's 200 positions")

    item_ids: list[str] = []
    row_ids: list[str] = []
    for row in rows:
        position = row.get("position")
        if (
            row.get("periodStart") != "2025-01-01"
            or row.get("periodEnd") != "2025-12-31"
            or row.get("period") != "annual"
        ):
            raise ValueError(f"unexpected chart period at position {position}")
        track = row.get("track") or {}
        if not str(track.get("name") or "").strip():
            raise ValueError(f"missing source title at position {position}")
        artists = track.get("artists") or []
        if any(not str(artist.get("name") or "").strip() for artist in artists):
            raise ValueError(f"blank artist object at position {position}")
        if str(track.get("id") or "") != str(row.get("itemId") or ""):
            raise ValueError(f"track ID and item ID disagree at position {position}")
        item_ids.append(str(track.get("id") or ""))
        row_ids.append(str(row.get("id") or ""))
        for metric in METRIC_FIELDS:
            value = row.get(metric)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"missing or invalid {metric} at position {position}")
            nested_value = (track.get("statSummary") or {}).get(metric)
            if nested_value != value:
                raise ValueError(
                    f"row and track {metric} disagree at position {position}: "
                    f"{value!r} != {nested_value!r}"
                )
    if len(set(item_ids)) != 200 or "" in item_ids:
        raise ValueError("TopHit track IDs are missing or repeated")
    if len(set(row_ids)) != 200 or "" in row_ids:
        raise ValueError("TopHit chart row IDs are missing or repeated")
    return payload


def artist_credit(track: dict[str, Any]) -> str:
    """Join source artist names in source order, keeping absent credits blank."""
    artists = track.get("artists") or []
    return " & ".join(str(artist["name"]).strip() for artist in artists)


def main() -> None:
    source_path = ROOT / SOURCE_PATH
    packet_path = ROOT / PACKET_PATH
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    packet_path.mkdir(parents=True, exist_ok=True)

    source_sha256 = sha256_file(source_path)
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = read_chart(source_path)
    rows = []
    for chart_row in payload["charts"]:
        track = chart_row["track"]
        artists = track.get("artists") or []
        metrics = {name: int(chart_row[name]) for name in METRIC_FIELDS}
        rows.append(
            {
                "series_id": SERIES_ID,
                "provider_code": "TOPHIT",
                "provider_name": "TopHit",
                "chart_family": "Top All Internet Hits",
                "chart_category": "annual_all_internet_hits",
                "publisher_country_code": "UA",
                "chart_market_code": "RU",
                "reporting_year": 2025,
                "period_label": "Calendar year 2025",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
                "position": int(chart_row["position"]),
                "published_rank": str(chart_row["position"]),
                "rank_kind": "publisher_published_rank",
                "title": str(track["name"]).strip(),
                "artist_credit": artist_credit(track),
                "native_id_namespace": "tophit_track_id",
                "native_song_id": str(track["id"]),
                "native_metric": (
                    "TopHit-reported annual chart metrics: airs, youtubeViews, and "
                    "spotifyStreams; the captured page does not disclose a composite formula"
                ),
                "score": None,
                "source_url": ARCHIVE_SOURCE_URL,
                "official_source_url": OFFICIAL_SOURCE_URL,
                "source_artifact": SOURCE_PATH.as_posix(),
                "source_sha256": source_sha256,
                "source_retrieved_at_utc": retrieved_at,
                "source_archive_timestamp": "2026-01-06T18:44:55Z",
                "transcription_method": "decoded_from_archived_top-hit_nextjs_server_payload",
                "evidence_status": "primary_source_verified_archived_page",
                "ranking_basis": (
                    "TopHit's published annual chart position is retained as supplied. "
                    "The captured page reports airplay, YouTube-view, and Spotify-stream "
                    "counts alongside the rank, but does not disclose their weighting formula."
                ),
                "normalized_artist_credit_method": (
                    "Source artist names are joined in source order with ' & '; a source row "
                    "with no artists retains an empty credit and the full source row is kept."
                ),
                "source_entry": chart_row,
                "source_artist_names": [str(artist["name"]) for artist in artists],
                "source_artist_relations": [artist.get("relation") for artist in artists],
                "source_international_title": track.get("intlName"),
                "source_metrics": metrics,
                "source_page_reported_depth": int(chart_row["top"]),
                "merged_into_150k_spotify_youtube_selection": False,
            }
        )

    rankings_path = packet_path / "rankings.jsonl"
    rankings_text = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )
    rankings_path.write_text(rankings_text, encoding="utf-8")
    rankings_sha256 = sha256_file(rankings_path)
    manifest = {
        "schema_version": "provider-series-packet-v1",
        "status": "primary_source_verified_archived_page",
        "provider_code": "TOPHIT",
        "provider_name": "TopHit",
        "publisher_country_code": "UA",
        "publisher_jurisdiction_basis": (
            "The matching legal entity, TOV TOPHIT (EDRPOU 42089400), is registered in "
            "Ukraine and lists Igor Kraev as its director. The match between that entity and "
            "the TopHit chart publisher is an inference from the entity name and official chart "
            "branding; the chart's Russia market is stored separately as RU. Registry reference: "
            "https://opendatabot.ua/c/42089400"
        ),
        "chart_family": "Top All Internet Hits",
        "chart_category": "annual_all_internet_hits",
        "source_type": "archived_first_party_annual_chart_page",
        "source_url": OFFICIAL_SOURCE_URL,
        "source_archive_url": ARCHIVE_SOURCE_URL,
        "source_archive_timestamp": "2026-01-06T18:44:55Z",
        "live_source_http_status_at_capture": None,
        "archived_source_http_status": 200,
        "source_artifacts": [
            {
                "local_path": SOURCE_PATH.as_posix(),
                "source_url": ARCHIVE_SOURCE_URL,
                "sha256": source_sha256,
                "content_type": "text/html; charset=utf-8",
                "note": "Wayback replay of the TopHit first-party annual chart page.",
            }
        ],
        "ranking_basis": (
            "Use the publisher-supplied annual positions 1-200 without recalculating ranks. "
            "The page payload identifies the 2025 calendar-year Russia chart and carries the "
            "airplay, YouTube-view, and Spotify-stream metrics for each entry. No combined "
            "weighting formula is stated in the captured page."
        ),
        "publisher_reported_annual_depth": 200,
        "ranked_entry_count": len(rows),
        "source_artist_credit_anomalies": [
            {
                "position": 178,
                "issue": "source track has an empty artists array; no artist was inferred",
            }
        ],
        "reported_metrics": {
            "airs": "TopHit-reported airplay count",
            "youtubeViews": "TopHit-reported YouTube view count",
            "spotifyStreams": "TopHit-reported Spotify stream count",
            "notes": (
                "All three are retained as separate reported metrics. The chart page does not "
                "explain a formula for combining them into rank. Zero values are preserved."
            ),
        },
        "ranking_file": rankings_path.name,
        "ranking_sha256": rankings_sha256,
        "series": [
            {
                "series_id": SERIES_ID,
                "chart_family": "Top All Internet Hits",
                "chart_category": "annual_all_internet_hits",
                "publisher_country_code": "UA",
                "chart_market_code": "RU",
                "reporting_year": 2025,
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
                "reported_depth": 200,
                "observed_ranked_entries": len(rows),
                "positions": list(range(1, len(rows) + 1)),
                "missing_positions": [],
                "ties_or_gaps_as_published": [],
                "status": "primary_source_verified_archived_page",
            }
        ],
        "non_core_scope": (
            "This TopHit national annual chart is a distinct provider series. It is not merged "
            "into the 150,000-position Spotify/YouTube core selection or the separate TopHit "
            "annual radio series."
        ),
    }
    (packet_path / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "packet": PACKET_PATH.as_posix(),
                "series_id": SERIES_ID,
                "ranked_positions": len(rows),
                "reported_depth": 200,
                "blank_artist_positions": [
                    row["position"] for row in rows if not row["artist_credit"]
                ],
                "source_sha256": source_sha256,
                "rankings_sha256": rankings_sha256,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
