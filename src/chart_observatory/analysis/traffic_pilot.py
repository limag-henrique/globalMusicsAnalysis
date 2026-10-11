"""Bounded, resumable Semrush Trends pilot; missing access never becomes traffic zero."""

import csv
import hashlib
import io
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import polars as pl

DOMAINS = ("pornhub.com", "xvideos.com", "xnxx.com")
MARKETS = ("BR", "US", "GB", "DE", "JP")
ENDPOINT = "https://api.semrush.com/analytics/ta/api/v3/summary"


def export_traffic_pilot(
    annual: pl.DataFrame,
    output: Path,
    *,
    api_key: str | None = None,
    collect: bool = False,
    limit: int = 1,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Plan country/month requests; collect explicitly, and validate original response CSVs."""
    if limit < 1:
        raise ValueError("Request limit must be positive")
    if collect and not api_key:
        raise ValueError("SEMRUSH_API_KEY required; no commercial calls were made")
    output.mkdir(parents=True, exist_ok=True)
    raw = output / "raw"
    raw.mkdir(exist_ok=True)
    plan = []
    for r in sorted(
        annual.select("market_code", "year").unique().to_dicts(),
        key=lambda r: (r["market_code"], r["year"]),
    ):
        if r["market_code"] not in MARKETS:
            continue
        for month in range(1, 3 if r["year"] == 2022 else 13):
            month_start = f"{r['year']}-{month:02d}-01"
            request_id = f"{r['market_code']}-{r['year']}-{month:02d}"
            plan.append(
                {
                    "request_id": request_id,
                    "country": r["market_code"],
                    "month": month_start,
                    "targets": ",".join(DOMAINS),
                    "device_type": "all",
                    "endpoint": ENDPOINT,
                    "max_summary_units": len(DOMAINS),
                }
            )
    pl.from_dicts(plan).write_csv(output / "request-plan.csv")
    visits = []
    calls = 0
    owns_client = client is None
    http = client or httpx.Client(timeout=60)
    try:
        for p in plan:
            path = raw / f"{p['request_id']}.csv"
            metadata = raw / f"{p['request_id']}.json"
            if not path.exists() and collect and calls < limit:
                params = {
                    "targets": p["targets"],
                    "display_date": p["month"],
                    "country": p["country"],
                    "export_columns": "target,visits,country,display_date,device_type",
                    "key": api_key,
                }
                try:
                    response = http.get(ENDPOINT, params=params)
                except httpx.HTTPError:
                    raise ValueError("Semrush transport failure; collection stopped") from None
                if response.status_code != 200:
                    raise ValueError(f"Semrush HTTP {response.status_code}; collection stopped")
                payload = response.content
                _parse(payload, p)
                path.write_bytes(payload)
                metadata.write_text(
                    json.dumps(
                        {
                            "request": p,
                            "sha256": hashlib.sha256(payload).hexdigest(),
                            "retrieved_at": datetime.now(UTC).isoformat(),
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                calls += 1
            observed = {}
            digest = retrieved = ""
            if path.exists():
                meta = json.loads(metadata.read_text(encoding="utf-8"))
                payload = path.read_bytes()
                digest = hashlib.sha256(payload).hexdigest()
                if digest != meta["sha256"] or p != meta["request"]:
                    raise ValueError("Traffic checkpoint hash or request mismatch")
                observed = _parse(payload, p)
                retrieved = meta["retrieved_at"]
            for domain in DOMAINS:
                visits.append(
                    {
                        "market_code": p["country"],
                        "year": int(p["month"][:4]),
                        "month": p["month"],
                        "domain": domain,
                        "device_type": "all",
                        "visits": observed.get(domain),
                        "status": "observed"
                        if domain in observed
                        else ("not_returned" if path.exists() else "access_pending"),
                        "source": "semrush_trends_summary",
                        "raw_sha256": digest,
                        "retrieved_at": retrieved,
                        "endpoint": ENDPOINT,
                        "unit": "estimated visits, not unique people",
                    }
                )
    finally:
        if owns_client:
            http.close()
    frame = pl.from_dicts(visits, infer_schema_length=None)
    frame.write_csv(output / "monthly-visits.csv")
    frame.write_parquet(output / "monthly-visits.parquet")
    totals = (
        frame.group_by("market_code", "year", "domain", "device_type")
        .agg(
            pl.len().alias("expected_months"),
            (pl.col("status") == "observed").sum().alias("observed_months"),
            pl.when((pl.col("status") == "observed").all())
            .then(pl.col("visits").sum())
            .otherwise(None)
            .alias("period_visits"),
        )
        .with_columns((pl.col("year") == 2022).alias("partial_year"))
    )
    totals.write_csv(output / "annual-visits.csv")
    result = {
        "provider": "semrush",
        "countries": frame["market_code"].n_unique(),
        "planned_requests": len(plan),
        "max_plan_summary_units": len(plan) * 3,
        "network_calls_this_run": calls,
        "observed_cells": frame.filter(pl.col("status") == "observed").height,
        "access": "configured" if api_key else "commercial_access_pending",
        "partial2022": "January-February only; not full corpus through March13",
    }
    (output / "status.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _parse(payload: bytes, request: dict[str, Any]) -> dict[str, float]:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    expected = {"target", "visits", "country", "display_date", "device_type"}
    if not expected.issubset(reader.fieldnames or []):
        raise ValueError("Invalid Semrush CSV or provider error; collection stopped")
    records = {}
    for r in reader:
        if (
            r["country"] != request["country"]
            or r["display_date"] != request["month"]
            or r["device_type"] != "all"
            or r["target"] not in DOMAINS
        ):
            raise ValueError("Traffic response country/month/device/domain mismatch")
        domain = r["target"]
        if domain in records:
            raise ValueError("Duplicate traffic domain")
        if r["visits"] in {"", "n/a", "N/A"}:
            continue
        value = float(r["visits"])
        if not math.isfinite(value) or value < 0:
            raise ValueError("Invalid estimated visits")
        records[domain] = value
    return records
