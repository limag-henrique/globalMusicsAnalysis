"""Recapture native representative-video endpoints for selected historical chart rows.

This does not re-rank observations or assert that a YouTube song-family chart
represents one recording. Its evidence supports recording/text review.
"""

import hashlib
import json
import re
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright
from scrape_youtube_chart_titles import (
    EXTRACT_METRICS,
    country_code,
    parse_period,
    parse_view_count,
)

from chart_observatory.ingestion.annual_selection import song_key

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/audited-calendars-2018-2026-20261031"
STATE = ROOT / "data/runtime/youtube-native-proof-20261031"
OUT = BASE / "youtube-native-evidence"
STOP = threading.Event()
GUARD = threading.Lock()
STATS = Counter()
EXTRACT = EXTRACT_METRICS.replace(
    "return {metric_text:value, rank:i+1,",
    "return {source_endpoint:root.querySelector('#entity-title')?.getAttribute('endpoint'),"
    "metric_text:value, rank:i+1,",
)


def metadata_id(title, artist):
    value = json.dumps(song_key(title, artist), ensure_ascii=False)
    return "YOUTUBE_METADATA:" + hashlib.sha256(value.encode()).hexdigest()


def publish(stage, **details):
    with GUARD:
        part = STATE / "status.part"
        part.write_text(
            json.dumps(
                dict(
                    stage=stage,
                    pid=__import__("os").getpid(),
                    updated_at=datetime.now(UTC).isoformat(),
                    counts=dict(STATS),
                    **details,
                ),
                indent=2,
            ),
            encoding="utf-8",
        )
        part.replace(STATE / "status.json")


def main():
    from playwright.sync_api import Error

    STATE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    selected = [
        json.loads(line)
        for line in (BASE / "combined.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wanted = {r["candidate_id"] for r in selected if r["platform"] == "YOUTUBE"}
    cells = {(r["country_code"], r["year"]) for r in selected if r["platform"] == "YOUTUBE"}
    jobs, expected = [], Counter()
    for country, year in sorted(cells):
        for path in sorted(
            (ROOT / "data/raw/annual_top80/20261021").glob(
                f"YOUTUBE_CHARTS_WEB_{country}_{year}-*.json"
            )
        ):
            raw = path.read_bytes()
            doc = json.loads(raw)
            if doc["period_end"] > "2026-10-15":
                continue
            targets = {}
            for row in doc["rows"]:
                key = metadata_id(row["title"], row["artist"])
                if key in wanted:
                    targets[key] = row
                    expected[key] += 1
            if targets:
                jobs.append(
                    dict(
                        document=doc,
                        targets=targets,
                        source_file=str(path),
                        source_sha256=hashlib.sha256(raw).hexdigest(),
                    )
                )
    STATS["planned_pages"] = len(jobs)
    STATS["selected_candidates"] = len(wanted)
    publish("collecting")

    def worker(batch):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(locale="pt-BR")
            page.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if route.request.resource_type in ("image", "media", "font")
                    else route.continue_()
                ),
            )
            try:
                for job in batch:
                    if STOP.is_set():
                        break
                    doc = job["document"]
                    cache = OUT / f"{doc['country_code']}-{doc['period_end']}.json"
                    if cache.exists():
                        old = json.loads(cache.read_text(encoding="utf-8"))
                        if (
                            old.get("source_sha256") == job["source_sha256"]
                            and old.get("status") == "verified"
                        ):
                            with GUARD:
                                STATS["cached_pages"] += 1
                            publish("collecting")
                            continue
                    result = dict(
                        source_url=doc["source_url"],
                        source_file=job["source_file"],
                        source_sha256=job["source_sha256"],
                        country_code=doc["country_code"],
                        period_end=doc["period_end"],
                        captured_at=datetime.now(UTC).isoformat(),
                        status="unverified",
                        rows=[],
                        conflicts=[],
                    )
                    try:
                        response = page.goto(
                            doc["source_url"], wait_until="domcontentloaded", timeout=30000
                        )
                        if response and response.status in (401, 403, 429):
                            STOP.set()
                            raise ValueError("provider_access_paused")
                        page.locator("ytmc-entry-row #rank").last.wait_for(timeout=20000)
                        captions = [
                            s.strip()
                            for s in page.locator(
                                "ytmc-dropdown-v2 paper-button"
                            ).all_text_contents()
                        ]
                        dates = [
                            parse_period(s)["end"] for s in captions if re.search(r"202[56]\s*$", s)
                        ]
                        countries = []
                        for caption in captions:
                            with suppress(LookupError):
                                countries.append(country_code(caption))
                        if dates != [doc["period_end"]] or countries != [doc["country_code"]]:
                            raise ValueError("rendered_country_or_date_mismatch")
                        observed = page.locator("ytmc-entry-row").evaluate_all(EXTRACT)
                        by_key = defaultdict(list)
                        for row in observed:
                            by_key[metadata_id(row["title"], row["artist"])].append(row)
                        for key, source in job["targets"].items():
                            matches = by_key.get(key, [])
                            if len(matches) != 1:
                                result["conflicts"].append(
                                    dict(
                                        candidate_id=key, reason="metadata_row_ambiguous_or_absent"
                                    )
                                )
                                continue
                            row = matches[0]
                            if (
                                row["source_rank"] != source.get("source_rank", source["rank"])
                                or parse_view_count(row["metric_text"]) != source["metric_value"]
                            ):
                                result["conflicts"].append(
                                    dict(
                                        candidate_id=key, reason="historical_rank_or_metric_changed"
                                    )
                                )
                                continue
                            endpoint = json.loads(row.get("source_endpoint") or "{}")
                            url = endpoint.get("urlEndpoint", {}).get("url", "")
                            parsed = urlparse(url)
                            video = parse_qs(parsed.query).get("v", [""])[0]
                            if parsed.hostname not in (
                                "www.youtube.com",
                                "music.youtube.com",
                            ) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
                                result["conflicts"].append(
                                    dict(candidate_id=key, reason="native_video_endpoint_absent")
                                )
                                continue
                            result["rows"].append(
                                dict(
                                    candidate_id=key,
                                    video_id=video,
                                    title=row["title"],
                                    artist=row["artist"],
                                    source_rank=row["source_rank"],
                                    metric_value=source["metric_value"],
                                    native_id_kind="CHART_REPRESENTATIVE_VIDEO",
                                )
                            )
                        result["status"] = "verified" if not result["conflicts"] else "partial"
                    except (Error, ValueError, TypeError, KeyError) as exc:
                        result["error_type"] = type(exc).__name__
                        result["error"] = str(exc).splitlines()[0][:150]
                    part = cache.with_suffix(".part")
                    part.write_text(
                        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    part.replace(cache)
                    with GUARD:
                        STATS["processed_pages"] += 1
                        STATS["verified_rows"] += len(result["rows"])
                        STATS["conflicts"] += len(result["conflicts"])
                    publish("collecting")
                    time.sleep(0.5)
            finally:
                browser.close()

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(worker, (jobs[::2], jobs[1::2])))
    proofs = defaultdict(list)
    for path in OUT.glob("??-????-??-??.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for row in doc.get("rows", []):
            proofs[row["candidate_id"]].append(
                {
                    **row,
                    "source_url": doc["source_url"],
                    "country_code": doc["country_code"],
                    "period_end": doc["period_end"],
                    "evidence_file": str(path),
                }
            )
    with (OUT / "native-identity-map.jsonl").open("w", encoding="utf-8") as handle:
        for key in sorted(wanted):
            records = proofs.get(key, [])
            videos = sorted({row["video_id"] for row in records})
            handle.write(
                json.dumps(
                    dict(
                        candidate_id=key,
                        expected_source_rows=expected[key],
                        verified_source_rows=len(records),
                        video_ids=videos,
                        evidence=records,
                        identity_scope="chart_representative_videos_not_recording_adjudication",
                        all_source_rows_verified=len(records) == expected[key]
                        and bool(expected[key]),
                        recording_validated=False,
                        lyrics_validated=False,
                    ),
                    ensure_ascii=False,
                )
                + "\n"
            )
    publish(
        "provider_access_paused" if STOP.is_set() else "collected_pending_recording_review",
        candidates_with_native_evidence=len(proofs),
    )


if __name__ == "__main__":
    main()
