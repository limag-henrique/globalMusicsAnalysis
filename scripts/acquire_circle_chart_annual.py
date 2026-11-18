"""Acquire Circle Chart (KMCA) annual Digital Chart series for South Korea (2018-2020)."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

BASE_URL = "https://circlechart.kr"
PAGE_URL = f"{BASE_URL}/page_chart/onoff.circle?serviceGbn=ALL&termGbn=year&yearTime=3"
API_URL = f"{BASE_URL}/data/api/chart/onoff"
INTRO_URL = f"{BASE_URL}/popup/introduce_circlechart.circle"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def acquire_year(client: httpx.Client, year: int, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    page_resp = client.get(PAGE_URL)
    page_resp.raise_for_status()
    page_bytes = page_resp.content
    (out_dir / "source-page.html").write_bytes(page_bytes)

    api_resp = client.post(
        API_URL,
        data={
            "nationGbn": "T",
            "serviceGbn": "ALL",
            "termGbn": "year",
            "hitYear": str(year),
            "targetTime": str(year),
            "yearTime": "3",
            "PageSize": "200",
            "curUrl": "circlechart.kr/page_chart/onoff.circle?serviceGbn=ALL&termGbn=year&yearTime=3",
        },
        headers={"Referer": PAGE_URL},
    )
    api_resp.raise_for_status()
    api_bytes = api_resp.content
    (out_dir / "source-api-response.json").write_bytes(api_bytes)

    payload = json.loads(api_bytes.decode("utf-8"))
    if payload.get("ResultStatus") != "OK":
        raise RuntimeError(f"Circle Chart API failed for {year}: {payload.get('ResultStatus')}")

    raw_list = payload.get("List") or {}
    items = [raw_list[k] for k in sorted(raw_list.keys(), key=lambda x: int(x))]
    if not items:
        raise RuntimeError(f"No rows returned for {year}")

    series_id = f"CIRCLE_CHART_KR_{year}_DIGITAL_ANNUAL"
    api_sha = sha256_bytes(api_bytes)
    page_sha = sha256_bytes(page_bytes)

    rows = []
    positions = []
    for item in items:
        pos = int(item["SERVICE_RANKING"])
        positions.append(pos)
        score_raw = item.get("ROW_CNT")
        score = int(score_raw) if score_raw not in (None, "") else None
        rows.append(
            {
                "series_id": series_id,
                "provider_code": "CIRCLE_CHART",
                "provider_name": "Circle Chart (Korea Music Content Association)",
                "provider_name_native": "써클차트 (한국음악콘텐츠협회)",
                "chart_family": "Circle Digital Chart",
                "chart_family_native": "써클 디지털 차트",
                "chart_category": "digital_annual",
                "chart_category_native": "연간 디지털 차트",
                "publisher_country_code": "KR",
                "chart_market_code": "KR",
                "reporting_year": year,
                "period_label": f"{year} annual digital chart",
                "period_start": None,
                "period_end": None,
                "position": pos,
                "published_rank": str(item["SERVICE_RANKING"]),
                "title": (item.get("SONG_NAME") or "").strip(),
                "artist_credit": (item.get("ARTIST_NAME") or "").strip(),
                "album_name": (item.get("ALBUM_NAME") or "").strip(),
                "native_song_id": str(item.get("SEQ_MOM") or ""),
                "distributor": (item.get("DE_COMPANY_NAME") or "").strip(),
                "label": (item.get("MAKE_COMPANY_NAME") or "").strip(),
                "native_metric": "Digital Index (ROW_CNT)",
                "score": score,
                "source_url": PAGE_URL,
                "source_api_url": API_URL,
                "source_artifact": str((out_dir / "source-api-response.json").as_posix()),
                "source_sha256": api_sha,
                "source_page_artifact": str((out_dir / "source-page.html").as_posix()),
                "source_page_sha256": page_sha,
                "source_retrieved_at_utc": retrieved_at,
                "transcription_method": "direct_first_party_json_api_extraction",
                "evidence_status": "primary_source_verified",
                "merged_into_150k_spotify_youtube_selection": False,
            }
        )

    rankings_bytes = "".join(
        json.dumps(r, ensure_ascii=False) + "\n" for r in rows
    ).encode("utf-8")
    (out_dir / "rankings.jsonl").write_bytes(rankings_bytes)

    expected = list(range(1, len(positions) + 1))
    ties_or_gaps = [] if positions == expected else ["non_sequential_ranks"]

    manifest = {
        "schema_version": "circle-chart-annual-series-v1",
        "provider_code": "CIRCLE_CHART",
        "provider_name": "Circle Chart (Korea Music Content Association)",
        "provider_name_native": "써클차트 (한국음악콘텐츠협회)",
        "chart_family": "Circle Digital Chart",
        "chart_family_native": "써클 디지털 차트",
        "publisher_country_code": "KR",
        "chart_market_code": "KR",
        "market_scope_basis": "Circle Digital Chart aggregates South Korean digital streaming, download, and BGM usage across domestic platforms.",
        "reporting_year": year,
        "series_id": series_id,
        "reported_depth": len(rows),
        "positions": positions,
        "ties_or_gaps_as_published": ties_or_gaps,
        "period_label": f"{year} annual digital chart",
        "period_start": None,
        "period_end": None,
        "period_note": "Circle Chart labels this the annual digital chart for the year; exact week-cutoff dates are not disclosed in the JSON payload.",
        "ranking_file": "rankings.jsonl",
        "ranking_sha256": sha256_bytes(rankings_bytes),
        "source_artifacts": [
            {
                "local_path": str((out_dir / "source-api-response.json").as_posix()),
                "url": API_URL,
                "sha256": api_sha,
                "bytes": len(api_bytes),
                "retrieved_at_utc": retrieved_at,
                "role": "official_api_json",
            },
            {
                "local_path": str((out_dir / "source-page.html").as_posix()),
                "url": PAGE_URL,
                "sha256": page_sha,
                "bytes": len(page_bytes),
                "retrieved_at_utc": retrieved_at,
                "role": "official_chart_page_html",
            },
        ],
        "selection_policy": "Keep positions in independent provider series; do not merge into Spotify/YouTube 150,000-position selection.",
        "retrieved_at_utc": retrieved_at,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"year": year, "series_id": series_id, "rows": len(rows), "ties_or_gaps": ties_or_gaps}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=[2018, 2019, 2020])
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("data/derived/annual_revision/provider_series"),
    )
    args = parser.parse_args(argv)
    results = []
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for year in args.years:
            out_dir = args.base_dir / f"circle-chart-kr-{year}-annual"
            results.append(acquire_year(client, year, out_dir))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
