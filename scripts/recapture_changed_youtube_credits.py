"""Preserve native links for exact historical rows whose displayed credits changed."""

import hashlib
import json
import re
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from collect_chart_video_evidence import BASE, EXTRACT, OUT, metadata_id
from playwright.sync_api import sync_playwright
from scrape_youtube_chart_titles import country_code, parse_period, parse_view_count


def run():
    missing = {
        r["candidate_id"]
        for r in map(
            json.loads, (OUT / "native-identity-map.jsonl").read_text(encoding="utf-8").splitlines()
        )
        if not r["video_ids"]
    }
    pages = []
    for path in OUT.glob("??-????-??-??.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        original_bytes = Path(doc["source_file"]).read_bytes()
        if hashlib.sha256(original_bytes).hexdigest() != doc["source_sha256"]:
            raise ValueError("historical source hash mismatch")
        original = json.loads(original_bytes)
        wanted = {
            metadata_id(r["title"], r["artist"]): r
            for r in original["rows"]
            if metadata_id(r["title"], r["artist"]) in missing
        }
        if wanted:
            pages.append((doc, wanted))
    jobs, uncovered = [], set(missing)
    while uncovered:
        best = max(pages, key=lambda job: len(uncovered & job[1].keys()), default=None)
        if not best or not uncovered.intersection(best[1]):
            break
        jobs.append(best)
        uncovered.difference_update(best[1])
        pages.remove(best)
    cache = BASE / "youtube-changed-credits"
    cache.mkdir(exist_ok=True)
    evidence = []
    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        page = browser.new_page(locale="pt-BR")
        try:
            for doc, targets in jobs:
                path = cache / f"{doc['country_code']}-{doc['period_end']}.json"
                if path.exists():
                    capture = json.loads(path.read_text(encoding="utf-8"))
                else:
                    response = page.goto(
                        doc["source_url"], wait_until="domcontentloaded", timeout=30000
                    )
                    if not response or response.status != 200:
                        raise RuntimeError("public chart unavailable; stopping without bypass")
                    page.locator("ytmc-entry-row #rank").last.wait_for(timeout=20000)
                    labels = [
                        s.strip()
                        for s in page.locator("ytmc-dropdown-v2 paper-button").all_text_contents()
                    ]
                    dates = [parse_period(s)["end"] for s in labels if re.search(r"202[56]\s*$", s)]
                    countries = []
                    for label in labels:
                        with suppress(LookupError):
                            countries.append(country_code(label))
                    if dates != [doc["period_end"]] or countries != [doc["country_code"]]:
                        raise ValueError("country/date mismatch")
                    capture = dict(
                        source_url=doc["source_url"],
                        captured_at=datetime.now(UTC).isoformat(),
                        rows=page.locator("ytmc-entry-row").evaluate_all(EXTRACT),
                    )
                    part = path.with_suffix(".part")
                    part.write_text(json.dumps(capture, ensure_ascii=False), encoding="utf-8")
                    part.replace(path)
                    time.sleep(0.5)
                for key, original in targets.items():
                    matches = [
                        r
                        for r in capture["rows"]
                        if r["source_rank"] == original["source_rank"]
                        and r["title"] == original["title"]
                        and parse_view_count(r["metric_text"]) == original["metric_value"]
                    ]
                    if len(matches) != 1:
                        continue
                    observed = matches[0]
                    endpoint = json.loads(observed.get("source_endpoint") or "{}")
                    url = urlparse(endpoint.get("urlEndpoint", {}).get("url", ""))
                    video = parse_qs(url.query).get("v", [""])[0]
                    if url.hostname not in (
                        "www.youtube.com",
                        "music.youtube.com",
                    ) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
                        continue
                    evidence.append(
                        dict(
                            candidate_id=key,
                            native_video_id=video,
                            original_row=original,
                            observed_row=observed,
                            source_url=doc["source_url"],
                            evidence_file=str(path),
                            evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            linkage="exact_country_date_title_rank_metric_with_changed_display_credits",
                            artist_identity_validated=False,
                            recording_validated=False,
                            lyrics_validated=False,
                            classification_ready=False,
                        )
                    )
                print(json.dumps(dict(page=path.name, evidence_rows=len(evidence))), flush=True)
        finally:
            browser.close()
    path = cache / "pending-credit-review.jsonl"
    part = path.with_suffix(".part")
    part.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in evidence), encoding="utf-8"
    )
    part.replace(path)
    summary = dict(
        pages=len(jobs),
        original_unlinked_candidates=len(missing),
        candidates_with_row_link=len({r["candidate_id"] for r in evidence}),
        automatic_identity_validation=False,
    )
    (cache / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run()))
