"""Build a separate TopHit Russia 2025 annual radio chart provider packet."""

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
    "tophit-top-radio-hits-russia-annual-2025-archive-20260106.html"
)
PACKET_PATH = Path(
    "data/derived/annual_revision/provider_series/"
    "tophit-russia-top-radio-hits-annual-2025"
)
SERIES_ID = "TOPHIT_TOP_RADIO_HITS_RU_2025"
OFFICIAL_SOURCE_URL = "https://tophit.com/chart/top/radio/hits/ru/annual/2025"
ARCHIVE_SOURCE_URL = (
    "https://web.archive.org/web/20260106114803id_/"
    "https://tophit.com/chart/top/radio/hits/ru/annual/2025"
)


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

    expected_filter = {
        "variant": "top",
        "category": "radio",
        "type": "hits",
        "region": "ru",
        "period": "annual",
        "periodStart": "2025",
    }
    if payload.get("chartName") != "Top Radio Hits Russia Annual Chart":
        raise ValueError(f"unexpected TopHit chart name: {payload.get('chartName')!r}")
    if payload.get("filter") != expected_filter:
        raise ValueError(f"unexpected TopHit chart filter: {payload.get('filter')!r}")
    rows = payload.get("charts")
    if not isinstance(rows, list) or len(rows) != 200:
        raise ValueError(f"expected 200 chart rows, got {len(rows) if rows else 0}")

    positions = [int(row["position"]) for row in rows]
    if positions != list(range(1, 201)):
        raise ValueError("TopHit published positions are not the complete 1..200 sequence")
    if any(int(row.get("top") or 0) != 200 for row in rows):
        raise ValueError("TopHit row depth field differs from the chart's 200 positions")

    item_ids = []
    for row in rows:
        if row.get("periodStart") != "2025-01-01" or row.get("periodEnd") != "2025-12-31":
            raise ValueError(f"unexpected chart period at position {row.get('position')}")
        if row.get("region") != "ru" or row.get("period") != "annual":
            raise ValueError(f"unexpected chart market/period at position {row.get('position')}")
        track = row.get("track") or {}
        if not str(track.get("name") or "").strip():
            raise ValueError(f"missing source title at position {row.get('position')}")
        if not track.get("artists") or any(
            not str(artist.get("name") or "").strip() for artist in track["artists"]
        ):
            raise ValueError(f"missing source artist at position {row.get('position')}")
        if int(row.get("airs") or -1) < 0:
            raise ValueError(f"missing or negative airplay count at position {row.get('position')}")
        item_ids.append(str(track.get("id") or ""))
    if len(set(item_ids)) != 200 or "" in item_ids:
        raise ValueError("TopHit track IDs are missing or repeated")
    return payload


def artist_credit(track: dict[str, Any]) -> str:
    """Keep source artist names in source order; the raw relation fields are preserved."""
    return " & ".join(str(artist["name"]).strip() for artist in track["artists"])


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
        title = str(track["name"]).strip()
        artists = track["artists"]
        rows.append(
            {
                "series_id": SERIES_ID,
                "provider_code": "TOPHIT",
                "provider_name": "TopHit",
                "chart_family": "Top Radio Hits",
                "chart_category": "annual_radio_airplay",
                "publisher_country_code": "UA",
                "chart_market_code": "RU",
                "reporting_year": 2025,
                "period_label": "Calendar year 2025",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
                "position": int(chart_row["position"]),
                "published_rank": str(chart_row["position"]),
                "rank_kind": "publisher_published_rank",
                "title": title,
                "artist_credit": artist_credit(track),
                "native_id_namespace": "tophit_track_id",
                "native_song_id": str(track["id"]),
                "native_metric": "TopHit annual chart airplay count (airs)",
                "score": int(chart_row["airs"]),
                "source_url": ARCHIVE_SOURCE_URL,
                "official_source_url": OFFICIAL_SOURCE_URL,
                "source_artifact": SOURCE_PATH.as_posix(),
                "source_sha256": source_sha256,
                "source_retrieved_at_utc": retrieved_at,
                "source_archive_timestamp": "2026-01-06T11:48:03Z",
                "transcription_method": "decoded_from_archived_top-hit_nextjs_server_payload",
                "evidence_status": "primary_source_verified_archived_page",
                "ranking_basis": (
                    "TopHit's published annual radio chart position is retained as supplied; "
                    "the reported airplay count is stored as a separate score."
                ),
                "normalized_artist_credit_method": (
                    "Source artist names are joined in source order with ' & '; the complete "
                    "source artist objects and relation fields remain in source_entry."
                ),
                "source_entry": chart_row,
                "source_artist_names": [str(artist["name"]) for artist in artists],
                "source_artist_relations": [artist.get("relation") for artist in artists],
                "source_international_title": track.get("intlName"),
                "source_airplay_count": int(chart_row["airs"]),
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
        "chart_family": "Top Radio Hits",
        "chart_category": "annual_radio_airplay",
        "source_type": "archived_first_party_annual_chart_page",
        "source_url": OFFICIAL_SOURCE_URL,
        "source_archive_url": ARCHIVE_SOURCE_URL,
        "source_archive_timestamp": "2026-01-06T11:48:03Z",
        "live_source_http_status_at_capture": 403,
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
            "The page payload identifies the chart period as 2025-01-01 through 2025-12-31, "
            "and each row carries its published airplay count in `airs`."
        ),
        "publisher_reported_annual_depth": 200,
        "ranked_entry_count": len(rows),
        "ranking_file": rankings_path.name,
        "ranking_sha256": rankings_sha256,
        "series": [
            {
                "series_id": SERIES_ID,
                "chart_family": "Top Radio Hits",
                "chart_category": "annual_radio_airplay",
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
            "This TopHit national radio chart is a separate provider series. It is not merged "
            "into the 150,000-position Spotify/YouTube core selection."
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
                "source_sha256": source_sha256,
                "rankings_sha256": rankings_sha256,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
