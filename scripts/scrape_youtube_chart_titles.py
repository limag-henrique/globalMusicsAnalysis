"""Collect rendered public YouTube charts; no direct provider API calls.

Uses isolated headless Chrome sessions, a bounded page pool, HTTP cache, and CDP
resource blocking. Saves only names, artists, source row/rank, market and period.
Completed snapshots are cached on disk and never fetched again on resume.
Playwright is an optional acquisition dependency, not an application dependency.
"""

import argparse
import asyncio
import csv
import hashlib
import json
import re
import shutil
import time
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import pycountry
from import_web_chart_titles import CUTOFF, import_snapshot, validate_snapshot
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from chart_observatory.config import Settings

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/raw/web_chart_titles/20261021"
ARTICLE_MARKETS = ROOT / (
    "data/derived/research_quality/country-all-history-20261011-022524/annual-country-metrics.csv"
)
MONTHS = {
    "jan": 1,
    "fev": 2,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "apr": 4,
    "mai": 5,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "aug": 8,
    "set": 9,
    "sep": 9,
    "out": 10,
    "oct": 10,
    "nov": 11,
    "dez": 12,
    "dec": 12,
}
ALIASES = {
    "Global": "GLOBAL",
    "Russia": "RU",
    "South Korea": "KR",
    "Taiwan": "TW",
    "Turkey": "TR",
    "Vietnam": "VN",
    "Bolivia": "BO",
    "Tanzania": "TZ",
}
BLOCKED = [
    "*i.ytimg.com/*",
    "*yt3.ggpht.com/*",
    "*google-analytics.com/*",
    "*googletagmanager.com/*",
    "*doubleclick.net/*",
    "*googleads.g.doubleclick.net/*",
    "*.jpg*",
    "*.jpeg*",
    "*.png*",
    "*.webp*",
    "*.gif*",
    "*.woff*",
    "*.ttf*",
    "*.mp4*",
    "*.webm*",
    "*fonts.googleapis.com/*",
    "*fonts.gstatic.com/*",
]
EXTRACT = """elements => elements.map((e,i) => {
  const root=e.shadowRoot || e;
  return {rank:i+1, source_rank:Number(root.querySelector('#rank')?.textContent.trim()),
    title:root.querySelector('#entity-title')?.textContent.trim() || '',
    artist:root.querySelector('#artist-names')?.textContent.replace(/\\s+/g,' ').trim() || ''};
})"""
EXTRACT_METRICS = EXTRACT.replace(
    "return {rank:i+1,",
    "const value=[...root.querySelectorAll('.metric.content')].at(-1)?.textContent.trim();"
    "return {metric_text:value, rank:i+1,",
)


def parse_view_count(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:[0-9]+|[0-9]{1,3}(?:[,. \u00a0][0-9]{3})+)", value
    ):
        raise ValueError("missing or abbreviated weekly views")
    return int(re.sub(r"\D", "", value))


def parse_period(label):
    year = int(re.search(r"(20\d{2})\s*$", label).group(1))
    months = re.findall(r"([a-z]{3})\.", label.lower())
    month = MONTHS[months[-1]]
    last = label.split("–")[-1]
    day = int(re.search(r"\d{1,2}", last).group())
    end = date(year, month, day)
    return {"label": label, "start": (end - timedelta(days=6)).isoformat(), "end": end.isoformat()}


def country_code(name):
    return ALIASES[name] if name in ALIASES else pycountry.countries.lookup(name).alpha_2


def save_capture(document, output):
    document = validate_snapshot(document)
    compact = json.dumps(
        {k: v for k, v in document.items() if k != "observed_country_code"},
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha256(compact.encode()).hexdigest()[:12]
    filename = (
        f"{document['provider']}_{document['country_code']}_{document['period_end']}_{digest}.json"
    )
    path = output / filename
    if not path.exists() or document.get("observed_country_code"):
        if path.exists():
            previous = json.loads(path.read_text(encoding="utf-8"))
            document["retrieved_at"] = previous.get("retrieved_at", datetime.now(UTC).isoformat())
            document["verified_at"] = datetime.now(UTC).isoformat()
        else:
            document["retrieved_at"] = datetime.now(UTC).isoformat()
        temporary = path.with_suffix(".part")
        temporary.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    return path, len(document["rows"])


def write_json_atomic(path, document):
    temporary = path.with_suffix(".part")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(6):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * 2**attempt)


def collection_status(planned, collected, failures, *, paused=False):
    if paused:
        return "PAUSED"
    return "COMPLETE" if collected == planned and not failures else "PARTIAL"


def normalize_rendered_rows(rows):
    ranked = []
    for row in rows:
        source_rank = row.get("source_rank")
        if type(source_rank) is not int or not 1 <= source_rank <= 200:
            if row.get("title"):
                raise ValueError("named source row has no valid rank")
            continue
        ranked.append({**row, "rank": len(ranked) + 1})
    if not 1 <= len(ranked) <= 200:
        raise ValueError("unexpected chart depth")
    return ranked


def write_database_batch(engine, paths):
    for attempt in range(3):
        try:
            with Session(engine) as session, session.begin():
                return sum(
                    import_snapshot(session, json.loads(path.read_text(encoding="utf-8")), path)
                    for path in paths
                )
        except OperationalError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)


async def collect(args):
    from playwright.async_api import async_playwright, expect

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    completed = set()
    verified_files = []
    for path in output.glob("YOUTUBE_CHARTS_WEB_*.json"):
        # Cache correctness is checked before suppressing a network request.
        doc = validate_snapshot(json.loads(path.read_text(encoding="utf-8")))
        if doc.get("observed_country_code") == doc["country_code"] and (
            not getattr(args, "annual_metrics", False)
            or all("metric_value" in r for r in doc["rows"])
        ):
            completed.add((doc["country_code"], doc["period_end"]))
            verified_files.append(path)
    verified_files.extend(output.glob("KWORB_SPOTIFY_WEB_*.json"))
    with ARTICLE_MARKETS.open(encoding="utf-8-sig", newline="") as handle:
        wanted = {r["market_code"] for r in csv.DictReader(handle)} - {"GLOBAL"}
    if args.countries:
        wanted &= set(args.countries.split(","))
    started = time.monotonic()
    stats = {
        "new_snapshots": 0,
        "title_observations": 0,
        "network_bytes": 0,
        "failures": [],
        "workers": args.workers,
        "inserted_rows": 0,
    }
    last_report = started

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome",
            headless=True,
            args=[
                "--no-proxy-server",
                "--blink-settings=imagesEnabled=false",
                "--disable-background-networking",
                "--disable-extensions",
                "--disable-component-update",
                "--disable-http2",
            ],
        )
        context = await browser.new_context(locale="pt-BR", viewport={"width": 640, "height": 480})

        async def new_page(page_context):
            page = await page_context.new_page()
            page.acquisition_failures = []

            def failed_request(request):
                if request.resource_type in ("document", "script", "xhr", "fetch"):
                    parsed = urlparse(request.url)
                    page.acquisition_failures.append(
                        {"host": parsed.hostname, "path": parsed.path, "reason": request.failure}
                    )

            page.on("requestfailed", failed_request)
            cdp = await page_context.new_cdp_session(page)
            await cdp.send("Network.enable")
            await cdp.send("Network.setBlockedURLs", {"urls": BLOCKED})
            # Routing would disable the browser's HTTP cache. CDP blocking preserves it.
            cdp.on(
                "Network.loadingFinished",
                lambda event: stats.__setitem__(
                    "network_bytes", stats["network_bytes"] + event.get("encodedDataLength", 0)
                ),
            )
            return page

        first = await new_page(context)
        await first.goto(
            "https://charts.youtube.com/charts/TopSongs/br/weekly",
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        await expect(first.locator("ytmc-entry-row #rank").last).to_have_text(
            re.compile(r"\d+"), timeout=30_000
        )
        options = [
            v.strip()
            for v in await first.locator("ytmc-dropdown-v2 paper-item").all_text_contents()
        ]
        inventory = {"labels": [v for v in options if re.search(r"202[56]\s*$", v)]}
        available = {}
        for name in options:
            if not name or re.search(r"[\d.]", name):
                continue
            with suppress(LookupError):
                available[country_code(name)] = name
        markets = sorted(wanted & available.keys())
        periods = [parse_period(label) for label in dict.fromkeys(inventory["labels"])]
        periods = [p for p in periods if date(2025, 1, 1) <= date.fromisoformat(p["end"]) <= CUTOFF]
        if not periods or not markets:
            raise ValueError("empty market/calendar inventory")
        await context.close()
        write_json_atomic(
            output / "inventory_manifest.json",
            {
                "requested_markets": sorted(wanted),
                "available_markets": markets,
                "unavailable_markets": sorted(wanted - available.keys()),
                "periods": periods,
                "cutoff": CUTOFF.isoformat(),
                "year_convention": "NATIVE_WEEK_END_YEAR",
            },
        )
        jobs = [
            (country, period)
            for year in (2026, 2025)
            for country in markets
            for period in periods
            if period["end"].startswith(str(year)) and (country, period["end"]) not in completed
        ]
        stats.update(
            {
                "requested_markets": sorted(wanted),
                "available_markets": markets,
                "unavailable_markets": sorted(wanted - available.keys()),
                "weeks_per_market": len(periods),
                "planned_snapshots": len(jobs),
                "already_saved_snapshots": len(completed),
            }
        )
        if args.max_snapshots:
            jobs = jobs[: args.max_snapshots]
        queue = asyncio.Queue()
        for job in jobs:
            queue.put_nowait(job)
        print(json.dumps({"phase": "planned", **stats}), flush=True)
        pending_imports = []
        import_lock = asyncio.Lock()
        last_database_flush = time.monotonic()
        engine = (
            create_engine(
                Settings.load(ROOT).database_url,
                connect_args={"connect_timeout": 5},
                pool_pre_ping=True,
            )
            if args.apply
            else None
        )

        def write_database(paths):
            return write_database_batch(engine, paths)

        async def flush_database(force=False):
            nonlocal last_database_flush
            if engine is None or import_lock.locked():
                return
            async with import_lock:
                if pending_imports and (
                    len(pending_imports) >= 100
                    or force
                    or time.monotonic() - last_database_flush >= 60
                ):
                    paths = pending_imports[:100]
                    del pending_imports[:100]
                    try:
                        stats["inserted_rows"] += await asyncio.to_thread(write_database, paths)
                        last_database_flush = time.monotonic()
                    except Exception:
                        pending_imports[:0] = paths
                        raise

        def report(final=False, failed=False):
            report_data = {
                **stats,
                "status": "FAILED"
                if failed
                else collection_status(
                    stats["planned_snapshots"],
                    stats["new_snapshots"],
                    stats["failures"],
                    paused=(output / "pause.request").exists(),
                )
                if final
                else "RUNNING",
                "limited_run": bool(args.max_snapshots),
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "pending": queue.qsize(),
                "pending_database_imports": len(pending_imports),
                "updated_at": datetime.now(UTC).isoformat(),
            }
            write_json_atomic(output / "collection_manifest.json", report_data)
            print(
                json.dumps(
                    {
                        k: v
                        for k, v in report_data.items()
                        if k
                        not in (
                            "failures",
                            "requested_markets",
                            "available_markets",
                            "unavailable_markets",
                        )
                    }
                ),
                flush=True,
            )

        async def worker():
            nonlocal last_report
            worker_context = await browser.new_context(
                locale="pt-BR", viewport={"width": 640, "height": 480}
            )
            page = await new_page(worker_context)
            page_uses = 0
            while not queue.empty() and not (output / "pause.request").exists():
                if shutil.disk_usage(output).free < 5 * 1024**3:
                    (output / "pause.request").touch()
                    break
                country, period = queue.get_nowait()
                url = (
                    f"https://charts.youtube.com/charts/TopSongs/{country.lower()}/weekly/"
                    + period["end"].replace("-", "")
                )
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    await expect(page.locator("ytmc-entry-row #rank").last).to_have_text(
                        re.compile(r"\d+"), timeout=20_000
                    )
                    # Compare the semantic date, not locale-specific thin spaces
                    # or responsive accessibility visibility of the date button.
                    captions = await page.locator(
                        "ytmc-dropdown-v2 paper-button"
                    ).all_text_contents()
                    selected = [
                        parse_period(v.strip()) for v in captions if re.search(r"202[56]\s*$", v)
                    ]
                    if len(selected) != 1 or selected[0]["end"] != period["end"]:
                        raise ValueError("source selected a different week")
                    observed = []
                    for caption in captions:
                        with suppress(LookupError):
                            observed.append(country_code(caption.strip()))
                    if observed != [country]:
                        raise ValueError("rendered country differs from URL")
                    captured_rows = normalize_rendered_rows(
                        await page.locator("ytmc-entry-row").evaluate_all(
                            EXTRACT_METRICS if getattr(args, "annual_metrics", False) else EXTRACT
                        )
                    )
                    if getattr(args, "annual_metrics", False):
                        for row in captured_rows:
                            if row["title"]:
                                row["metric_value"] = parse_view_count(row.pop("metric_text", None))
                    document = {
                        "provider": "YOUTUBE_CHARTS_WEB",
                        "country_code": country,
                        "observed_country_code": observed[0],
                        "source_url": url,
                        "period_start": period["start"],
                        "period_end": period["end"],
                        "missing_title_positions": [
                            r["rank"] for r in captured_rows if not r["title"]
                        ],
                        "rows": [r for r in captured_rows if r["title"]],
                    }
                    path, count = save_capture(document, output)
                    if engine is not None:
                        pending_imports.append(path)
                    stats["new_snapshots"] += 1
                    stats["title_observations"] += count
                except Exception as error:
                    key = (country, period["end"])
                    attempts[key] = attempts.get(key, 0) + 1
                    if attempts[key] <= args.retries:
                        queue.put_nowait((country, period))
                    else:
                        stats["failures"].append(
                            {
                                "country": country,
                                "period_end": period["end"],
                                "error": type(error).__name__,
                                "detail": (str(error).splitlines() or [""])[0][:200],
                                "url": url,
                                "network_failures": page.acquisition_failures[-5:],
                            }
                        )
                    await page.close()
                    page = await new_page(worker_context)
                    page_uses = 0
                finally:
                    queue.task_done()
                await flush_database()
                if time.monotonic() - last_report >= 15:
                    last_report = time.monotonic()
                    report()
                await asyncio.sleep(0.15)
                page_uses += 1
                if page_uses >= 40:
                    await page.close()
                    page = await new_page(worker_context)
                    page_uses = 0
            await worker_context.close()

        attempts = {}
        failed = False
        try:
            if engine is not None:
                pending_imports.extend(verified_files)
                while pending_imports:
                    await flush_database(force=True)
            async with asyncio.TaskGroup() as group:
                for _ in range(args.workers):
                    group.create_task(worker())
        except BaseException:
            failed = True
            raise
        finally:
            try:
                while pending_imports and engine is not None:
                    await flush_database(force=True)
            except BaseException:
                failed = True
                raise
            finally:
                report(final=True, failed=failed)
                if engine is not None:
                    engine.dispose()
                await browser.close()
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--countries", help="Optional comma-separated article market codes")
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--max-snapshots", type=int)
    parser.add_argument(
        "--retries",
        type=int,
        choices=(0, 1, 2),
        default=1,
        help="Additional attempts per failed week (default: 1)",
    )
    parser.add_argument("--apply", action="store_true", help="Import verified captures in batches")
    parser.add_argument(
        "--annual-metrics",
        action="store_true",
        help="Collect weekly views into annual selection staging, without raw DB import",
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Request graceful pause of the run using this output directory; no network",
    )
    args = parser.parse_args()
    if args.annual_metrics:
        if args.apply:
            parser.error(
                "--annual-metrics uses build_annual_top80.py --apply for the capped selection"
            )
        if args.output == OUTPUT:
            args.output = ROOT / "data/raw/annual_top80/20261021"
    args.output = args.output.resolve()
    if args.pause:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "pause.request").touch()
        print(json.dumps({"status": "PAUSE_REQUESTED", "output": str(args.output)}))
        return
    if args.max_snapshots is not None and args.max_snapshots <= 0:
        parser.error("--max-snapshots must be positive")
    (args.output / "pause.request").unlink(missing_ok=True)
    result = asyncio.run(collect(args))
    if result["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
