"""Resume official weekly chart discovery for quota gaps; stage evidence, never annual ranks."""

import argparse
import asyncio
import hashlib
import json
import msvcrt
import re
import time
from collections import Counter
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from scrape_youtube_chart_titles import (
    BLOCKED,
    EXTRACT_METRICS,
    country_code,
    normalize_rendered_rows,
    parse_period,
    parse_view_count,
)
from sqlalchemy import create_engine, text

from chart_observatory.config import Settings
from chart_observatory.ingestion.import_quotas import load_quotas
from chart_observatory.quota_campaign import remaining_seconds
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data/runtime/chart-gap-discovery-20261101"
COVERAGE = ROOT / "data/derived/lyrics/quota-20261030/review-inventory/staging-coverage.json"
CUTOFF = date(2026, 10, 15)
QUOTAS = ROOT / (
    "data/derived/annual_revision/reconciled-russia-2018-2026-20261031/sources/country_quotas.csv"
)
REPORT_VERSION = "annual-quota-boundary-v2"


def quota_gap_cells(coverage):
    quotas = load_quotas(QUOTAS)
    cells = [c for c in coverage["cells"] if c["missing_ranking_positions"]]
    for cell in cells:
        if cell["quota"] != quotas.get(cell["country_code"]):
            raise ValueError("coverage quota differs from approved country table")
    return cells


def weeks(year):
    if not 2018 <= year <= 2026:
        raise ValueError("year outside approved protocol")
    end = min(date(year, 12, 31), CUTOFF)
    end -= timedelta(days=(end.weekday() - 3) % 7)
    while end.year == year:
        yield end
        end -= timedelta(days=7)


def validate_capture(doc):
    country = doc["country_code"]
    end = date.fromisoformat(doc["period_end"])
    if not re.fullmatch(r"[A-Z]{2}", country) or country == "GLOBAL":
        raise ValueError("country required")
    if not 2018 <= end.year <= 2026 or end > CUTOFF:
        raise ValueError("period outside approved protocol")
    expected = f"https://charts.youtube.com/charts/TopSongs/{country.lower()}/weekly/{end:%Y%m%d}"
    if doc["source_url"] != expected or doc["observed_country_code"] != country:
        raise ValueError("source market mismatch")
    if doc["observed_period_end"] != end.isoformat():
        raise ValueError("source calendar mismatch")
    rows = doc["rows"]
    if not rows or len(rows) > 200:
        raise ValueError("unexpected chart depth")
    if [r["rank"] for r in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("noncontiguous published positions")
    for row in rows:
        if not row["title"] or not row["artist"] or type(row["metric_value"]) is not int:
            raise ValueError("missing title, artist or exact weekly views")
        if row["metric_value"] < 0:
            raise ValueError("negative weekly views")
    identities = Counter((r["title"].casefold(), r["artist"].casefold()) for r in rows)
    doc["repeated_display_identities"] = [list(k) for k, n in identities.items() if n > 1]
    doc.update(
        annual_rank_certified=False,
        recording_identity_validated=False,
        classification_ready=False,
        selection_status="DISCOVERY_QUARANTINE",
    )
    return doc


def stage(engine, doc):
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    path = STATE / "captures" / f"{digest}.json"
    if not path.exists():
        path.write_text(raw, encoding="utf-8")
    # Additive evidence table, deliberately separate from definitive annual selections.
    with engine.begin() as conn:
        conn.execute(
            text("""CREATE TABLE IF NOT EXISTS quota_chart_discovery_snapshots (
            evidence_sha256 text PRIMARY KEY, country_code text NOT NULL,
            period_end date NOT NULL, source_url text NOT NULL, payload jsonb NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT now())""")
        )
        conn.execute(
            text("""INSERT INTO quota_chart_discovery_snapshots
            (evidence_sha256,country_code,period_end,source_url,payload)
            VALUES (:sha,:country,:end,:url,CAST(:payload AS jsonb))
            ON CONFLICT (evidence_sha256) DO NOTHING"""),
            dict(
                sha=digest,
                country=doc["country_code"],
                end=doc["period_end"],
                url=doc["source_url"],
                payload=raw,
            ),
        )
    return digest


def annual_discovery(cell, checkpoint):
    """Export provisional display-based totals only after every required week is saved."""
    country, year = cell["country_code"], cell["year"]
    expected = [f"{country}/{end}" for end in weeks(year)]
    found = [checkpoint[k] for k in expected if checkpoint.get(k, {}).get("sha256")]
    report = dict(
        report_version=REPORT_VERSION,
        country_code=country,
        year=year,
        quota=cell["quota"],
        expected_weeks=len(expected),
        collected_weeks=len(found),
        missing_weeks=[k for k in expected if not checkpoint.get(k, {}).get("sha256")],
        annual_rank_certified=False,
        classification_ready=False,
        selection_status="DISCOVERY_QUARANTINE",
        candidates=[],
        maximum_annual_songs=cell["quota"],
        annual_memberships_added=0,
        weekly_reference_occurrences=sum(e.get("observations", 0) for e in found),
        reference_occurrences_are_unique_songs=False,
    )
    if len(found) != len(expected):
        report["blocker"] = "incomplete_weekly_history"
        return report
    totals = {}
    seen_periods = set()
    for evidence in found:
        raw = (STATE / "captures" / f"{evidence['sha256']}.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
            raise ValueError("discovery evidence hash mismatch")
        doc = validate_capture(json.loads(raw))
        if (
            doc["country_code"] != country
            or int(doc["period_end"][:4]) != year
            or f"{country}/{doc['period_end']}" not in expected
            or doc["period_end"] in seen_periods
        ):
            raise ValueError("evidence belongs to another market, calendar or repeated week")
        seen_periods.add(doc["period_end"])
        if doc["repeated_display_identities"]:
            report["blocker"] = "conflicting_weekly_display_identities"
            return report
        for row in doc["rows"]:
            # Exact display strings only; never merge spelling variants or covers.
            key = (row["title"], row["artist"])
            item = totals.setdefault(
                key, dict(title=key[0], artist=key[1], observed_weekly_views=0, evidence_sha256=[])
            )
            item["observed_weekly_views"] += row["metric_value"]
            item["evidence_sha256"].append(evidence["sha256"])
    ordered = sorted(
        totals.values(), key=lambda r: (-r["observed_weekly_views"], r["title"], r["artist"])
    )
    report["blocker"] = "native_recording_identity_and_annual_protocol_review"
    report["candidates"] = [
        dict(row, provisional_position=i) for i, row in enumerate(ordered[: cell["quota"]], 1)
    ]
    return report


async def run(hours):
    from playwright.async_api import async_playwright

    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    cells = quota_gap_cells(coverage)
    cells.sort(key=lambda c: (c["country_code"] not in {"IL", "KR"}, -c["year"], c["country_code"]))
    checkpoint_path = STATE / "checkpoint.json"
    checkpoint = (
        json.loads(checkpoint_path.read_text(encoding="utf-8")) if checkpoint_path.exists() else {}
    )
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    deadline = time.monotonic() + hours * 3600
    remaining = remaining_seconds()
    if remaining is not None:
        deadline = min(deadline, time.monotonic() + remaining)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=["--no-proxy-server"])
        context = await browser.new_context(locale="pt-BR")
        page = await context.new_page()
        cdp = await context.new_cdp_session(page)
        await cdp.send("Network.enable")
        await cdp.send("Network.setBlockedURLs", {"urls": BLOCKED})
        try:
            for cell in cells:
                country, year = cell["country_code"], cell["year"]
                failures = 0
                for end in weeks(year):
                    key = f"{country}/{end}"
                    if key in checkpoint:
                        if checkpoint[key]["status"] != "imported_discovery":
                            failures += 1
                            if failures >= 2:
                                break
                        continue
                    if time.monotonic() >= deadline:
                        return
                    url = (
                        f"https://charts.youtube.com/charts/TopSongs/"
                        f"{country.lower()}/weekly/{end:%Y%m%d}"
                    )
                    publish_status(
                        STATE / "status.json",
                        dict(
                            stage="collecting_official_history",
                            target=key,
                            completed_attempts=len(checkpoint),
                            updated_at=datetime.now(UTC).isoformat(),
                            classification_ready=False,
                        ),
                    )
                    try:
                        response = await page.goto(
                            url, wait_until="domcontentloaded", timeout=30000
                        )
                        if response.status in {401, 403, 429}:
                            raise PermissionError(f"provider access paused: HTTP {response.status}")
                        await page.locator("ytmc-entry-row #rank").last.wait_for(timeout=20000)
                        captions = await page.locator(
                            "ytmc-dropdown-v2 paper-button"
                        ).all_text_contents()
                        periods = [
                            parse_period(v.strip())
                            for v in captions
                            if re.search(r"20\d{2}\s*$", v)
                        ]
                        markets = []
                        for caption in captions:
                            with suppress(LookupError):
                                markets.append(country_code(caption.strip()))
                        if len(periods) != 1 or markets != [country]:
                            raise ValueError("ambiguous rendered country/calendar")
                        rows = normalize_rendered_rows(
                            await page.locator("ytmc-entry-row").evaluate_all(EXTRACT_METRICS)
                        )
                        for row in rows:
                            row["metric_value"] = parse_view_count(row.pop("metric_text", None))
                        doc = validate_capture(
                            dict(
                                country_code=country,
                                observed_country_code=markets[0],
                                period_end=end.isoformat(),
                                observed_period_end=periods[0]["end"],
                                period_start=(end - timedelta(days=6)).isoformat(),
                                source_url=url,
                                provider="YOUTUBE_CHARTS_WEB",
                                rows=rows,
                            )
                        )
                        digest = stage(engine, doc)
                        checkpoint[key] = dict(
                            status="imported_discovery", sha256=digest, observations=len(rows)
                        )
                        failures = 0
                    except PermissionError:
                        raise
                    except Exception as exc:
                        checkpoint[key] = dict(
                            status="unresolved_source",
                            error=type(exc).__name__,
                            detail=str(exc).splitlines()[0][:200],
                            url=url,
                        )
                        failures += 1
                    publish_status(checkpoint_path, checkpoint)
                    if failures >= 2:
                        break
                    await asyncio.sleep(3)
                publish_status(
                    STATE / f"annual-discovery-{country}-{year}.json",
                    annual_discovery(cell, checkpoint),
                )
            publish_status(
                STATE / "status.json",
                dict(
                    stage="finished_with_pending_ranking_review",
                    attempts=len(checkpoint),
                    imported_snapshots=sum(
                        v["status"] == "imported_discovery" for v in checkpoint.values()
                    ),
                    observations=sum(v.get("observations", 0) for v in checkpoint.values()),
                    annual_rank_certified=False,
                    classification_ready=False,
                    updated_at=datetime.now(UTC).isoformat(),
                ),
            )
        finally:
            await browser.close()
            engine.dispose()


def prepare_timeout_retry():
    path = STATE / "checkpoint.json"
    checkpoint = json.loads(path.read_text(encoding="utf-8"))
    history_path = STATE / "timeout-retry-history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    if len(history) >= 2:
        return
    targets = {
        k: v
        for k, v in checkpoint.items()
        if v.get("status") == "unresolved_source" and v.get("error") == "TimeoutError"
    }
    if not targets:
        return
    history.append(dict(observed_at=datetime.now(UTC).isoformat(), previous_attempts=targets))
    if not publish_status(history_path, history):
        raise OSError("cannot preserve timeout attempt history")
    for key in targets:
        del checkpoint[key]
    if not publish_status(path, checkpoint):
        raise OSError("cannot persist bounded retry plan")


def main(hours, retry_timeouts=False):
    (STATE / "captures").mkdir(parents=True, exist_ok=True)
    with (STATE / "owner.lock").open("a+b") as lock:
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            if retry_timeouts:
                prepare_timeout_retry()
            asyncio.run(run(hours))
        except Exception as exc:
            publish_status(
                STATE / "status.json",
                dict(
                    stage="attention_required",
                    error_type=type(exc).__name__,
                    updated_at=datetime.now(UTC).isoformat(),
                ),
            )
            raise


def report_discovery():
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    checkpoint_path = STATE / "checkpoint.json"
    if not checkpoint_path.exists():
        return
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    for cell in quota_gap_cells(coverage):
        path = STATE / f"annual-discovery-{cell['country_code']}-{cell['year']}.json"
        scoped = {
            k: v
            for k, v in checkpoint.items()
            if k.startswith(f"{cell['country_code']}/{cell['year']}-")
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                dict(version=REPORT_VERSION, quota=cell["quota"], sources=scoped), sort_keys=True
            ).encode()
        ).hexdigest()
        if (
            path.exists()
            and json.loads(path.read_text(encoding="utf-8")).get("checkpoint_sha256") == fingerprint
        ):
            continue
        report = annual_discovery(cell, checkpoint)
        publish_status(path, dict(report, checkpoint_sha256=fingerprint))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=float, default=8)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--retry-timeouts", action="store_true")
    args = parser.parse_args()
    if not 0 < args.hours <= 8:
        parser.error("hours must be in (0,8]")
    if args.report_only:
        report_discovery()
    else:
        main(args.hours, args.retry_timeouts)
