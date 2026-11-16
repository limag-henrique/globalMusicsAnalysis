"""Worldwide, source-aware historical discovery; never turns snapshots into annual ranks."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import os
import re
import sys
from collections import Counter
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pycountry
from bs4 import BeautifulSoup

from chart_observatory.research_flow import file_hash, load_selection, write_json, write_rows

VERSION = "worldwide-chart-recovery-v2-native-entity-evidence"
COLLECTOR_SOURCE_SHA256 = file_hash(Path(__file__))
HELP_URL = "https://support.google.com/youtube/answer/9014376?hl=en"
ALIASES = {
    "UK": "GB",
    "US": "US",
    "South Korea": "KR",
    "Russia": "RU",
    "Taiwan": "TW",
    "Turkey": "TR",
    "Vietnam": "VN",
    "Bolivia": "BO",
    "Tanzania": "TZ",
}

EXTRACT_NATIVE_ENTITY = """elements => elements.map((e,i) => {
  const root=e.shadowRoot || e;
  const d=e.__data?.chartSummaryEntity || {};
  let videoUrl=null;
  try {
    const endpoint=typeof d.videoEndpoint === 'string'
      ? JSON.parse(d.videoEndpoint) : d.videoEndpoint;
    videoUrl=endpoint?.urlEndpoint?.url || null;
  } catch (_) {}
  const metricText=[...root.querySelectorAll('.metric.content')].at(-1)?.textContent.trim();
  return {
    rank:i+1,
    source_rank:Number(root.querySelector('#rank')?.textContent.trim()),
    title:root.querySelector('#entity-title')?.textContent.trim() || '',
    artist:root.querySelector('#artist-names')?.textContent.replace(/\\s+/g,' ').trim() || '',
    metric_text:metricText || null,
    native_rank:d.currentPosition ?? null,
    native_metric_value:d.viewsCount ?? null,
    native_entity_title:d.entityTitle || '',
    native_artist_names:d.artistNames || '',
    native_artist_ids:Array.isArray(d.artists)
      ? d.artists.map(a=>({id:a.id || null,name:a.name || ''})) : [],
    representative_video_url:videoUrl,
    native_release_date:d.releaseDate || null
  };
})"""


def representative_video_id(url):
    """Extract a video ID only for a canonical public YouTube watch URL."""
    if not isinstance(url, str):
        return None
    try:
        parsed = httpx.URL(url)
    except (TypeError, ValueError):
        return None
    value = parsed.params.get("v", "")
    if (
        parsed.scheme == "https"
        and parsed.host in {"youtube.com", "www.youtube.com"}
        and parsed.path == "/watch"
        and re.fullmatch(r"[A-Za-z0-9_-]{11}", value)
    ):
        return value
    return None


def normalize_native_entry(row, parse_view_count):
    """Retain native chart entity fields while proving rank/metric match the UI."""
    row = dict(row)
    display_metric = parse_view_count(row.pop("metric_text", None))
    native_metric = row.pop("native_metric_value", None)
    if type(native_metric) is not int or native_metric != display_metric:
        raise ValueError("native chart entity metric differs from rendered metric")
    native_rank = row.pop("native_rank", None)
    if type(native_rank) is not int or native_rank != row.get("rank"):
        raise ValueError("native chart entity rank differs from published rank")

    rendered_title, rendered_artist = row.get("title", ""), row.get("artist", "")
    entity_title = row.pop("native_entity_title", "")
    artist_names = row.pop("native_artist_names", "")
    if entity_title:
        row["title"] = entity_title
    if artist_names:
        row["artist"] = artist_names
    row.update(
        rendered_title=rendered_title,
        rendered_artist=rendered_artist,
        native_rank=native_rank,
        native_metric_value=native_metric,
        native_entity_evidence=True,
        native_artist_ids=[
            item for item in row.get("native_artist_ids", []) if isinstance(item, dict)
        ],
        representative_video_id=representative_video_id(row.get("representative_video_url")),
        display_metadata_conflict=bool(
            rendered_title and entity_title and rendered_title != entity_title
        )
        or bool(rendered_artist and artist_names and rendered_artist != artist_names),
        identity_basis="native_chart_entity_metadata",
        recording_identity_validated=False,
        representative_video_is_recording_id=False,
        metric_value=native_metric,
    )
    return row


def markets_from_help(html):
    soup = BeautifulSoup(html, "html.parser")
    label = soup.find(string=re.compile(r"YouTube Music Charts are available in"))
    if label is None:
        raise ValueError("official country directory could not be identified")
    listing = label.parent.find_next("ul")
    if listing is None:
        raise ValueError("official country list is missing")
    result = {}
    for item in listing.find_all("li", recursive=False):
        name = item.get_text(" ", strip=True)
        code = ALIASES.get(name)
        if code is None:
            code = pycountry.countries.lookup(name).alpha_2
        if code in result:
            raise ValueError("repeated official chart country")
        result[code] = name
    if len(result) < 30:
        raise ValueError("unexpectedly short official chart country directory")
    return result


def weeks(year, cutoff="2026-10-15"):
    if type(year) is not int or not 2018 <= year <= 2026:
        raise ValueError("year outside frozen research scope")
    end = min(date(year, 12, 31), date.fromisoformat(cutoff))
    value = date(year, 1, 1)
    value += timedelta(days=(3 - value.weekday()) % 7)
    result = []
    while value <= end:
        result.append(value.isoformat())
        value += timedelta(days=7)
    return result


def build_plan(selection, supported_markets):
    manifest, cells, members, inputs = load_selection(selection)
    observed = {r["country_code"] for r in members}
    per_country = {}
    tasks, unknown = [], []
    for cell in cells:
        country, year, quota = cell["country_code"], cell["year"], cell["quota"]
        if quota is not None:
            per_country[country] = quota
        if quota is None:
            reason = "quota_applicability_unresolved"
        elif country not in supported_markets:
            reason = "not_in_current_youtube_chart_directory"
        elif cell.get("missing_complete_annual_positions", quota) == 0:
            continue
        else:
            expected = weeks(year, manifest["cutoff"])
            tasks.append(
                {
                    "country_code": country,
                    "year": year,
                    "quota": quota,
                    "selected_positions": cell["selected_positions"],
                    "missing_complete_annual_positions": cell["missing_complete_annual_positions"],
                    "expected_period_ends": expected,
                    "source": "YOUTUBE_CHARTS_WEB",
                    "annual_rank_certified": False,
                    "requires_historical_route_verification": True,
                }
            )
            continue
        unknown.append(
            {
                "country_code": country,
                "year": year,
                "quota": quota,
                "reason": reason,
                "source_existence_conclusion": "not_established",
                "requires_other_historical_source": True,
            }
        )
    tasks.sort(
        key=lambda r: (
            r["country_code"] in observed,
            -r["year"],
            -r["missing_complete_annual_positions"],
            r["country_code"],
        )
    )
    current_catalog_capacity = sum(per_country[c] * 9 for c in observed)
    return {
        "version": VERSION,
        "selection_sha256": file_hash(Path(selection) / "manifest.json"),
        "requested_positions": manifest["requested_positions"],
        "observed_positions": len(members),
        "catalog_observed_markets": len(observed),
        "catalog_capacity_if_all_years_and_quotas_filled": current_catalog_capacity,
        "catalog_capacity_percent": 100
        * current_catalog_capacity
        / manifest["requested_positions"],
        "capacity_limit_applies_only_to_current_observed_catalog": True,
        "other_sources_may_exist": True,
        "youtube_documented_markets": len(supported_markets),
        "tasks": tasks,
        "other_source_tasks": unknown,
        "input_hashes": inputs,
        "paid_calls": 0,
        "classification_ready": False,
    }


def initialize_campaign(*, project, selection, state):
    project, selection, state = map(lambda p: Path(p).resolve(), (project, selection, state))
    if not state.is_relative_to(project / "data/runtime"):
        raise ValueError("recovery state must stay in project runtime")
    if (state / "campaign.json").exists():
        saved = json.loads((state / "campaign.json").read_text(encoding="utf-8"))
        if saved["selection_sha256"] != file_hash(selection / "manifest.json"):
            raise ValueError("recovery campaign belongs to another frozen selection")
        for name, digest in saved["input_hashes"].items():
            if file_hash(name) != digest:
                raise ValueError("frozen recovery input changed")
        return saved
    if state.exists():
        raise ValueError("new recovery campaign needs an unused directory")
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        response = client.get(HELP_URL)
        response.raise_for_status()
        html = response.text
    supported = markets_from_help(html)
    plan = build_plan(selection, supported)
    state.mkdir(parents=True)
    (state / "captures").mkdir()
    (state / "source-directory.html").write_text(html, encoding="utf-8")
    write_json(
        state / "source-directory.json",
        {
            "url": HELP_URL,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "sha256": file_hash(state / "source-directory.html"),
            "markets": supported,
            "historical_availability_verified": False,
        },
    )
    plan["input_hashes"][str(state / "source-directory.html")] = file_hash(
        state / "source-directory.html"
    )
    plan["source_directory"] = str(state / "source-directory.json")
    plan["project"] = str(project)
    plan["selection"] = str(selection)
    plan["created_at"] = datetime.now(UTC).isoformat()
    write_json(state / "campaign.json", plan)
    write_rows(state / "other-source-queue.jsonl", plan["other_source_tasks"])
    write_rows(state / "historical-queue.jsonl", plan["tasks"])
    return plan


def validate_capture(doc):
    country, end = doc["country_code"], date.fromisoformat(doc["period_end"])
    if not re.fullmatch(r"[A-Z]{2}", country) or end.weekday() != 3:
        raise ValueError("invalid market or native weekly endpoint")
    if not 2018 <= end.year <= 2026 or end > date(2026, 10, 15):
        raise ValueError("capture outside frozen research window")
    expected = f"https://charts.youtube.com/charts/TopSongs/{country.lower()}/weekly/{end:%Y%m%d}"
    if (
        doc["source_url"] != expected
        or doc["observed_country_code"] != country
        or doc["observed_period_end"] != end.isoformat()
    ):
        raise ValueError("provider returned another market or period")
    records = doc["rows"]
    if not 1 <= len(records) <= 200:
        raise ValueError("unexpected source depth")
    if [r["rank"] for r in records] != list(range(1, len(records) + 1)):
        raise ValueError("source ranks are missing, repeated or reordered")
    for row in records:
        if type(row.get("metric_value")) is not int or row["metric_value"] < 0:
            raise ValueError("exact source metric missing")
        if row.get("native_entity_evidence"):
            native_rank = row.get("native_rank")
            native_metric = row.get("native_metric_value")
            if type(native_rank) is not int or native_rank != row["rank"]:
                raise ValueError("native chart entity rank differs from published rank")
            if type(native_metric) is not int or native_metric != row["metric_value"]:
                raise ValueError("native chart entity metric differs from published metric")
    doc["missing_display_positions"] = [
        row["rank"] for row in records if not row.get("title") or not row.get("artist")
    ]
    doc["display_metadata_conflict_positions"] = [
        row["rank"] for row in records if row.get("display_metadata_conflict")
    ]
    doc.update(
        annual_rank_certified=False,
        recording_identity_validated=False,
        classification_ready=False,
        selection_status="DISCOVERY_QUARANTINE",
    )
    return doc


def _atomic(path, value):
    temporary = Path(path).with_suffix(".tmp")
    write_json(temporary, value)
    temporary.replace(path)


def is_recaptcha_challenge_frame_url(url):
    """Return true for Google's interactive reCAPTCHA challenge frame, not its anchor."""
    try:
        parsed = httpx.URL(url)
    except (TypeError, ValueError):
        return False
    return parsed.host in {"google.com", "www.google.com"} and parsed.path in {
        "/recaptcha/api2/bframe",
        "/recaptcha/enterprise/bframe",
    }


def recaptcha_challenge_present(page):
    """Detect an interactive challenge frame so the collector does not retry blindly."""
    return any(is_recaptcha_challenge_frame_url(frame.url) for frame in page.frames)


async def collect_campaign(
    *, project, selection, state, max_requests=12, hours=2, retry_unresolved=False
):
    """Bounded, resumable official-route acquisition, without database writes."""
    if type(max_requests) is not int or not 1 <= max_requests <= 10000:
        raise ValueError("request budget must be in 1..10000")
    if not 0 < hours <= 24:
        raise ValueError("duration must be in (0,24] hours")
    import msvcrt

    from playwright.async_api import async_playwright

    state = Path(state).resolve()
    plan = initialize_campaign(project=project, selection=selection, state=state)
    checkpoint_path = state / "checkpoint.json"
    checkpoint = (
        json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {}
    )
    sys.path.insert(0, str(Path(project).resolve() / "scripts"))
    scraper = importlib.import_module("scrape_youtube_chart_titles")
    lock_path = Path(project).resolve() / "data/runtime/worldwide-youtube-recovery-owner.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        deadline = asyncio.get_running_loop().time() + hours * 3600
        attempts, pause_reason = 0, None
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(locale="pt-BR")
            page = await context.new_page()
            cdp = await context.new_cdp_session(page)
            await cdp.send("Network.enable")
            await cdp.send("Network.setBlockedURLs", {"urls": scraper.BLOCKED})
            try:
                for task in plan["tasks"]:
                    country = task["country_code"]
                    # Verify oldest, middle and newest route before filling a calendar.
                    ends = task["expected_period_ends"]
                    preferred = [ends[0], ends[len(ends) // 2], ends[-1]]
                    ordered = list(dict.fromkeys([*preferred, *ends]))
                    failures = 0
                    for end_text in ordered:
                        key = f"{country}/{end_text}"
                        history = []
                        if key in checkpoint:
                            item = checkpoint[key]
                            if (
                                item.get("capture")
                                and file_hash(state / item["capture"]) != item["sha256"]
                            ):
                                raise ValueError("saved capture changed; manual review required")
                            if (
                                not retry_unresolved
                                or item["status"] != "historical_route_unresolved"
                                or item.get("attempt_count", 1) >= 2
                            ):
                                continue
                            history = [
                                *item.get("history", []),
                                {k: v for k, v in item.items() if k != "history"},
                            ]
                        if (state / "stop.request").exists():
                            return _status(state, checkpoint, "operator_requested_stop", attempts)
                        if (
                            attempts >= max_requests
                            or asyncio.get_running_loop().time() >= deadline
                        ):
                            return _status(
                                state, checkpoint, "request_or_time_budget_reached", attempts
                            )
                        end = date.fromisoformat(end_text)
                        url = f"https://charts.youtube.com/charts/TopSongs/{country.lower()}/weekly/{end:%Y%m%d}"
                        _atomic(
                            state / "status.json",
                            {
                                "stage": "collecting_official_history",
                                "target": key,
                                "pid": os.getpid(),
                                "updated_at": datetime.now(UTC).isoformat(),
                                "paid_calls": 0,
                            },
                        )
                        attempts += 1
                        periods, markets = [], []
                        try:
                            response = await page.goto(
                                url, wait_until="domcontentloaded", timeout=30000
                            )
                            status = response.status if response is not None else None
                            if status in {401, 403, 429}:
                                pause_reason = f"provider_access_paused_HTTP_{status}"
                                checkpoint[key] = {
                                    "status": "provider_paused",
                                    "http_status": status,
                                    "url": url,
                                }
                                break
                            if recaptcha_challenge_present(page):
                                pause_reason = "provider_captcha_challenge"
                                checkpoint[key] = {
                                    "status": "provider_paused_captcha",
                                    "reason": "google_recaptcha_challenge_frame_present",
                                    "http_status": status,
                                    "url": url,
                                    "observed_at": datetime.now(UTC).isoformat(),
                                    "attempt_count": len(history) + 1,
                                    "history": history,
                                }
                                _atomic(checkpoint_path, checkpoint)
                                break
                            await page.locator("ytmc-entry-row #rank").last.wait_for(timeout=20000)
                            captions = await page.locator(
                                "ytmc-dropdown-v2 paper-button"
                            ).all_text_contents()
                            periods = [
                                scraper.parse_period(v.strip())
                                for v in captions
                                if re.search(r"20\d{2}\s*$", v)
                            ]
                            markets = []
                            for label in captions:
                                with suppress(LookupError):
                                    markets.append(scraper.country_code(label.strip()))
                            if len(periods) != 1 or markets != [country]:
                                raise ValueError("ambiguous rendered market or period")
                            rendered = await page.locator("ytmc-entry-row").evaluate_all(
                                EXTRACT_NATIVE_ENTITY
                            )
                            displayed_records = scraper.normalize_rendered_rows(rendered)
                            records = []
                            for row in displayed_records:
                                if row["source_rank"] != row["rank"]:
                                    raise ValueError("published rank differs from DOM order")
                                records.append(
                                    normalize_native_entry(row, scraper.parse_view_count)
                                )
                            doc = validate_capture(
                                {
                                    "country_code": country,
                                    "period_end": end_text,
                                    "period_start": (end - timedelta(days=6)).isoformat(),
                                    "source_url": url,
                                    "observed_country_code": markets[0],
                                    "observed_period_end": periods[0]["end"],
                                    "provider": "YOUTUBE_CHARTS_WEB",
                                    "collector_version": VERSION,
                                    "collector_sha256": COLLECTOR_SOURCE_SHA256,
                                    "rows": records,
                                    "retrieved_at": datetime.now(UTC).isoformat(),
                                }
                            )
                            payload = json.dumps(doc, ensure_ascii=False, sort_keys=True).encode()
                            digest = hashlib.sha256(payload).hexdigest()
                            capture = f"captures/{digest}.json"
                            (state / capture).write_bytes(payload)
                            checkpoint[key] = {
                                "status": "captured_discovery",
                                "capture": capture,
                                "sha256": digest,
                                "rows": len(records),
                                "url": url,
                                "attempt_count": len(history) + 1,
                                "history": history,
                            }
                            failures = 0
                        except Exception as exc:
                            if recaptcha_challenge_present(page):
                                pause_reason = "provider_captcha_challenge"
                                checkpoint[key] = {
                                    "status": "provider_paused_captcha",
                                    "reason": "google_recaptcha_challenge_frame_present",
                                    "error_type": type(exc).__name__,
                                    "url": url,
                                    "observed_at": datetime.now(UTC).isoformat(),
                                    "attempt_count": len(history) + 1,
                                    "history": history,
                                }
                                _atomic(checkpoint_path, checkpoint)
                                break
                            checkpoint[key] = {
                                "status": "historical_route_unresolved",
                                "error_type": type(exc).__name__,
                                "reason": str(exc)[:300],
                                "observed_market_codes": markets,
                                "observed_periods": periods,
                                "url": url,
                                "observed_at": datetime.now(UTC).isoformat(),
                                "attempt_count": len(history) + 1,
                                "history": history,
                            }
                            failures += not isinstance(exc, ValueError)
                        _atomic(checkpoint_path, checkpoint)
                        if failures >= 2:
                            break
                        await asyncio.sleep(3)
                    if pause_reason:
                        _atomic(checkpoint_path, checkpoint)
                        break
                return _status(
                    state, checkpoint, pause_reason or "eligible_queue_scanned", attempts
                )
            finally:
                await browser.close()


def _status(state, checkpoint, reason, attempts):
    report = {
        "stage": "paused_provider" if reason.startswith("provider_") else "finished_pending_review",
        "reason": reason,
        "pid": os.getpid(),
        "attempts_this_invocation": attempts,
        "checkpoint_requests": len(checkpoint),
        "statuses": dict(Counter(row["status"] for row in checkpoint.values())),
        "captured_weekly_rows": sum(row.get("rows", 0) for row in checkpoint.values()),
        "annual_positions_added": 0,
        "annual_rank_certified": False,
        "classification_ready": False,
        "paid_calls": 0,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    _atomic(Path(state) / "status.json", report)
    return report
