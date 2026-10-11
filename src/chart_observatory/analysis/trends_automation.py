"""Paced, resumable access to the public Trends website (not Google's alpha API)."""

import csv
import hashlib
import json
import math
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from chart_observatory.analysis.country_context import FIELDS, export_context

BASE = "https://trends.google.com/trends/api"
WEB_SOURCE = "google_trends_web_unofficial"


def _json_response(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    content = response.text
    if content.startswith(")]}'"):
        content = content[4:].lstrip(",\r\n ")
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("Trends returned a non-object response")
    return payload


def _observations(query: dict[str, str], raw: bytes) -> list[dict[str, Any]]:
    payload = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    result = []
    start, end = date.fromisoformat(query["period_start"]), date.fromisoformat(query["period_end"])
    for sample in payload["response"]["default"]["timelineData"]:
        sample_date = datetime.fromtimestamp(int(sample["time"]), UTC).date()
        if not start <= sample_date <= end:
            # Weekly buckets may start before the requested first date. Preserve raw,
            # but do not attribute a bucket outside the requested period to that year.
            continue
        values = sample["value"]
        if len(values) != 1:
            raise ValueError("Expected one term per independently scaled Trends query")
        value = float(values[0])
        if not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError("Invalid Trends index")
        has_data = sample.get("hasData", [True])[0]
        status = (
            "observed_partial_index"
            if sample.get("isPartial", False)
            else "observed_relative_index"
        )
        result.append(
            {
                **query,
                "source": WEB_SOURCE,
                "value": value if has_data else "",
                "status": status if has_data else "not_reported",
                "raw_value": values[0],
                "sample_date": sample_date.isoformat(),
                "raw_sha256": digest,
                "retrieved_at": payload["retrieved_at"],
            }
        )
    if not result:
        result.append(
            {
                **query,
                "source": WEB_SOURCE,
                "value": "",
                "status": "no_data",
                "raw_sha256": digest,
                "retrieved_at": payload["retrieved_at"],
            }
        )
    return result


def collect_trends(
    annual: Path,
    output: Path,
    *,
    client: httpx.Client | None = None,
    limit: int | None = None,
    interval: float = 8,
    wait: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Collect English/native query plan, stopping on HTTP errors and resuming successes."""
    if interval < 0 or (limit is not None and limit < 1):
        raise ValueError("Interval must be nonnegative and limit positive")
    if client is None:
        with httpx.Client(timeout=30, follow_redirects=True) as owned:
            return collect_trends(
                annual, output, client=owned, limit=limit, interval=interval, wait=wait
            )
    export_context(annual, output / "plan")
    with (output / "plan/query-plan.csv").open(encoding="utf-8-sig", newline="") as handle:
        queries = list(csv.DictReader(handle))
    # Start with the best documented native vocabulary; no change to the country set.
    queries.sort(
        key=lambda q: (
            q["country_iso2"] != "BR",
            q["country_iso2"],
            q["year"] != "2021",
            q["year"],
            q["language"] != "en",
        )
    )
    raw_dir = output / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    attempted = 0
    blocked: dict[str, Any] | None = None
    for query in queries:
        raw_path = raw_dir / f"{query['query_id']}.json"
        if raw_path.exists():
            cached = json.loads(raw_path.read_bytes())
            if cached["query"] != query:
                raise ValueError("Cached Trends query metadata mismatch")
            _observations(query, raw_path.read_bytes())
            continue
        if limit is not None and attempted >= limit:
            break
        if attempted:
            wait(interval)
        attempted += 1
        request = {
            "comparisonItem": [
                {
                    "keyword": query["term"],
                    "time": f"{query['period_start']} {query['period_end']}",
                    "geo": query["country_iso2"],
                }
            ],
            "category": 0,
            "property": "",
        }
        try:
            widgets = _json_response(
                client.get(
                    BASE + "/explore",
                    params={
                        "hl": "en-US",
                        "tz": "0",
                        "req": json.dumps(request, ensure_ascii=False),
                    },
                )
            )["widgets"]
            widget = next((w for w in widgets if w["id"] == "TIMESERIES"), None)
            if widget is None:
                raise ValueError("Trends response has no TIMESERIES widget")
            wait(interval)
            response = _json_response(
                client.get(
                    BASE + "/widgetdata/multiline",
                    params={
                        "hl": "en-US",
                        "tz": "0",
                        "req": json.dumps(widget["request"], ensure_ascii=False),
                        "token": widget["token"],
                    },
                )
            )
            data = {
                "query": query,
                "request": request,
                "response": response,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "source": WEB_SOURCE,
            }
            raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            _observations(query, raw)  # Validate before checkpointing.
            raw_path.write_bytes(raw)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            http_status = (
                exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            )
            # Exception URLs can contain temporary widget tokens. Never persist them.
            blocked = {
                "query_id": query["query_id"],
                "country_iso2": query["country_iso2"],
                "term": query["term"],
                "language": query["language"],
                "status": "rate_limited" if http_status == 429 else "collection_error",
                "http_status": http_status,
                "error_type": type(exc).__name__,
            }
            break
    records = []
    completed = 0
    for query in queries:
        raw_path = raw_dir / f"{query['query_id']}.json"
        if raw_path.exists():
            records.extend(_observations(query, raw_path.read_bytes()))
            completed += 1
        else:
            status = (
                blocked["status"]
                if blocked and blocked["query_id"] == query["query_id"]
                else "pending"
            )
            records.append({**query, "source": WEB_SOURCE, "status": status, "value": ""})
    with (output / "trends-observations.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    summary = {
        "source": WEB_SOURCE,
        "planned_queries": len(queries),
        "completed_queries": completed,
        "pending_queries": len(queries) - completed,
        "attempted_this_run": attempted,
        "blocked": blocked,
        "interval_seconds": interval,
        "created_at": datetime.now(UTC).isoformat(),
        "csv_sha256": hashlib.sha256((output / "trends-observations.csv").read_bytes()).hexdigest(),
        "limitations": [
            "Unofficial website endpoints may change or deny automated access",
            "Local indices cannot rank countries or be summed across terms",
            "Native vocabulary remains a candidate requiring linguistic review",
        ],
    }
    (output / "collection-status.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
