"""Recover a missing YouTube artist through exact historical chart row endpoints."""

import json
import re
from contextlib import suppress
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright
from scrape_youtube_chart_titles import country_code, parse_period, parse_view_count

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/audited-calendars-2018-2026-20261031"
CACHE = ROOT / "data/raw/metadata_resolution/20261031"
TARGET = "YOUTUBE_METADATA:e5c17570cdb0616908f6582bad9ab59fc5a097be7dec1b3512aa0209dcb2c5cf"


def resolve():
    selected = [
        json.loads(line)
        for line in (BASE / "combined.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    bindings = [row for row in selected if row["candidate_id"] == TARGET]
    cells = {(row["country_code"], row["year"]) for row in bindings}
    if not bindings or {row["title"] for row in bindings} != {"SEMPERO (Super Slowed)"}:
        raise ValueError("target contract changed")
    captures = []
    for country, year in sorted(cells):
        for path in sorted(
            (ROOT / "data/raw/annual_top80/20261021").glob(
                f"YOUTUBE_CHARTS_WEB_{country}_{year}-*.json"
            )
        ):
            document = json.loads(path.read_text(encoding="utf-8"))
            for row in document["rows"]:
                if row.get("title") == bindings[0]["title"] and not row.get("artist"):
                    captures.append((document, row))
    evidence, native_ids = [], set()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="pt-BR")
        try:
            for doc, expected in captures:
                output = CACHE / f"sempero-{doc['country_code']}-{doc['period_end']}.json"
                if output.exists():
                    record = json.loads(output.read_text(encoding="utf-8"))
                else:
                    response = page.goto(
                        doc["source_url"], wait_until="domcontentloaded", timeout=30000
                    )
                    page.locator("ytmc-entry-row #rank").last.wait_for(timeout=20000)
                    captions = [
                        s.strip()
                        for s in page.locator("ytmc-dropdown-v2 paper-button").all_text_contents()
                    ]
                    periods = [
                        parse_period(s)["end"] for s in captions if re.search(r"202[56]\s*$", s)
                    ]
                    countries = []
                    for caption in captions:
                        with suppress(LookupError):
                            countries.append(country_code(caption))
                    if periods != [doc["period_end"]] or countries != [doc["country_code"]]:
                        raise ValueError("rendered chart country/date differs from source")
                    matches = page.locator("ytmc-entry-row").filter(has_text=expected["title"])
                    if matches.count() != 1:
                        raise ValueError("chart row ambiguous or absent")
                    row = matches.first
                    rank = int(row.locator("#rank").inner_text())
                    metric = parse_view_count(
                        row.locator(".metric.content").last.inner_text().strip()
                    )
                    if rank != expected["rank"] or metric != expected["metric_value"]:
                        raise ValueError("historical row differs from saved chart")
                    endpoint = json.loads(row.locator("#entity-title").get_attribute("endpoint"))
                    url = endpoint.get("urlEndpoint", {}).get("url", "")
                    parsed = urlparse(url)
                    native = parse_qs(parsed.query).get("v", [""])[0]
                    if parsed.hostname != "www.youtube.com" or not re.fullmatch(
                        r"[A-Za-z0-9_-]{11}", native
                    ):
                        raise ValueError("no verifiable native video endpoint")
                    record = dict(
                        source_url=doc["source_url"],
                        country_code=doc["country_code"],
                        period_end=doc["period_end"],
                        source_rank=rank,
                        metric_value=metric,
                        video_id=native,
                        title=expected["title"],
                        response_status=response.status,
                        row_html=row.evaluate("el => el.outerHTML"),
                    )
                    output.write_text(
                        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                native_ids.add(record["video_id"])
                evidence.append(str(output))
                print(
                    json.dumps(dict(period=doc["period_end"], video_id=record["video_id"])),
                    flush=True,
                )
        finally:
            browser.close()
    video_path = CACHE / "youtube-sempero-video.json"
    video = json.loads(video_path.read_text(encoding="utf-8"))
    if native_ids != {video.get("videoId")} or video.get("title") != bindings[0]["title"]:
        raise ValueError("video identity or edition differs across source periods")
    match = re.search(r"(?im)^Artist:\s*\n([^\n]+)", video.get("shortDescription", ""))
    if not match:
        raise ValueError("linked video does not explicitly credit an artist")
    enrichment_path = BASE / "metadata-enrichment.json"
    enrichment = json.loads(enrichment_path.read_text(encoding="utf-8"))
    enrichment["resolved"][TARGET] = dict(
        title=bindings[0]["title"],
        artist=match[1].strip(),
        basis="exact_historical_chart_endpoints_and_linked_video_artist_credit",
        native_video_id=video["videoId"],
        evidence=evidence + [str(video_path)],
        recording_and_text_validation=False,
    )
    temporary = enrichment_path.with_suffix(".part")
    temporary.write_text(json.dumps(enrichment, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(enrichment_path)
    return dict(
        resolved=TARGET,
        artist=match[1].strip(),
        verified_chart_rows=len(evidence),
        native_video_id=video["videoId"],
    )


if __name__ == "__main__":
    print(json.dumps(resolve()))
