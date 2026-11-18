"""Acquire and package archived TopHit Top Radio Hits Russia Annual charts (2018-2024)."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

SNAPSHOTS = {
    2018: "20241126203731",
    2019: "20241121200458",
    2022: "20240925073546",
    2023: "20240925191731",
    2024: "20250330111543",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def decode_next_data(html: str, year: int) -> dict[str, Any]:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html
    )
    if not match:
        raise ValueError(f"TopHit {year} archive page has no __NEXT_DATA__")
    next_data = json.loads(match.group(1))
    compressed = base64.b64decode(next_data["props"]["pageProps"]["data"])
    payload = json.loads(zlib.decompress(compressed))
    if payload.get("chartName") != "Top Radio Hits Russia Annual Chart":
        raise ValueError(f"Unexpected chartName for {year}: {payload.get('chartName')!r}")
    rows = payload.get("charts") or []
    positions = [int(r["position"]) for r in rows]
    if positions != list(range(1, len(rows) + 1)):
        raise ValueError(f"Non-sequential positions for {year}")
    return payload


def process_year(client: httpx.Client, year: int, ts: str, root: Path) -> dict[str, Any]:
    official_url = f"https://tophit.com/chart/top/radio/hits/ru/annual/{year}"
    archive_url = f"https://web.archive.org/web/{ts}id_/{official_url}"
    raw_dir = root / f"data/raw/national_charts/tophit_ru_annual_{year}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"tophit-top-radio-hits-russia-annual-{year}-archive-{ts[:8]}.html"

    if not raw_path.exists():
        resp = client.get(archive_url)
        resp.raise_for_status()
        raw_path.write_bytes(resp.content)

    raw_sha = sha256_file(raw_path)
    payload = decode_next_data(raw_path.read_text(encoding="utf-8"), year)
    charts = payload["charts"]
    retrieved_at = datetime.now(UTC).isoformat(timespec="seconds")

    series_id = f"TOPHIT_TOP_RADIO_HITS_RU_{year}"
    packet_dir = root / f"data/derived/annual_revision/provider_series/tophit-russia-top-radio-hits-annual-{year}"
    packet_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for chart_row in charts:
        track = chart_row["track"]
        artists = track["artists"]
        rows.append(
            {
                "series_id": series_id,
                "provider_code": "TOPHIT",
                "provider_name": "TopHit",
                "chart_family": "Top Radio Hits",
                "chart_category": "annual_radio_airplay",
                "publisher_country_code": "UA",
                "chart_market_code": "RU",
                "reporting_year": year,
                "period_label": f"Calendar year {year}",
                "period_start": chart_row.get("periodStart") or f"{year}-01-01",
                "period_end": chart_row.get("periodEnd") or f"{year}-12-31",
                "position": int(chart_row["position"]),
                "published_rank": str(chart_row["position"]),
                "rank_kind": "publisher_published_rank",
                "title": str(track["name"]).strip(),
                "artist_credit": " & ".join(str(a["name"]).strip() for a in artists),
                "native_id_namespace": "tophit_track_id",
                "native_song_id": str(track["id"]),
                "native_metric": "TopHit annual chart airplay count (airs)",
                "score": int(chart_row["airs"]),
                "source_url": archive_url,
                "official_source_url": official_url,
                "source_artifact": raw_path.relative_to(root).as_posix(),
                "source_sha256": raw_sha,
                "source_retrieved_at_utc": retrieved_at,
                "source_archive_timestamp": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}Z",
                "transcription_method": "decoded_from_archived_tophit_nextjs_server_payload",
                "evidence_status": "primary_source_verified_archived_page",
                "source_entry": chart_row,
                "source_artist_names": [str(a["name"]) for a in artists],
                "source_international_title": track.get("intlName"),
                "source_airplay_count": int(chart_row["airs"]),
                "source_page_reported_depth": int(chart_row.get("top") or len(charts)),
                "merged_into_150k_spotify_youtube_selection": False,
            }
        )

    rankings_path = packet_dir / "rankings.jsonl"
    rankings_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows),
        encoding="utf-8",
    )
    rankings_sha = sha256_file(rankings_path)
    manifest = {
        "schema_version": "provider-series-packet-v1",
        "status": "primary_source_verified_archived_page",
        "provider_code": "TOPHIT",
        "provider_name": "TopHit",
        "publisher_country_code": "UA",
        "chart_market_code": "RU",
        "reporting_year": year,
        "series": [
            {
                "series_id": series_id,
                "chart_family": "Top Radio Hits",
                "chart_category": "annual_radio_airplay",
                "reported_depth": len(rows),
                "positions": list(range(1, len(rows) + 1)),
                "ties_or_gaps_as_published": [],
                "ranking_file": "rankings.jsonl",
                "ranking_sha256": rankings_sha,
                "period_start": rows[0]["period_start"],
                "period_end": rows[0]["period_end"],
                "source_url": archive_url,
                "official_source_url": official_url,
            }
        ],
        "source_artifacts": [
            {
                "local_path": raw_path.relative_to(root).as_posix(),
                "url": archive_url,
                "sha256": raw_sha,
                "bytes": raw_path.stat().st_size,
                "retrieved_at_utc": retrieved_at,
                "role": "archived_official_chart_html",
            }
        ],
        "selection_policy": "Keep positions in independent provider series; do not merge into Spotify/YouTube 150,000-position selection.",
    }
    (packet_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"year": year, "series_id": series_id, "rows": len(rows), "raw_sha256": raw_sha, "rankings_sha256": rankings_sha}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=[2018, 2019, 2022, 2023, 2024])
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    out = []
    with httpx.Client(timeout=45, follow_redirects=True) as client:
        for yr in args.years:
            out.append(process_year(client, yr, SNAPSHOTS[yr], root))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
