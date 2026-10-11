"""Original browser CSV batches, shared scales and explicit pending coverage."""

import calendar
import csv
import hashlib
import io
import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from chart_observatory.analysis.country_context import FIELDS, export_context


def prepare_browser_queue(annual: Path, output: Path) -> list[dict[str, Any]]:
    export_context(annual, output / "plan")
    with (output / "plan/query-plan.csv").open(encoding="utf-8-sig", newline="") as handle:
        queries = list(csv.DictReader(handle))
    markets: dict[str, list[dict[str, str]]] = defaultdict(list)
    for query in queries:
        markets[query["country_iso2"]].append(query)
    queue = []
    for country in sorted(markets, key=lambda c: (c != "BR", c)):
        records = markets[country]
        start = min(q["period_start"] for q in records)
        end = max(q["period_end"] for q in records)
        terms = list(dict.fromkeys(q["term"] for q in records if q["term"] != "porn"))
        for i in range(0, len(terms), 4):
            batch_terms = ["porn", *terms[i : i + 4]]
            identity = json.dumps([country, start, end, batch_terms], ensure_ascii=False)
            queue.append(
                {
                    "batch_id": hashlib.sha256(identity.encode()).hexdigest()[:20],
                    "country_iso2": country,
                    "period_start": start,
                    "period_end": end,
                    "terms": batch_terms,
                    "source_url": "https://trends.google.com/trends/explore?"
                    + urlencode(
                        {"date": f"{start} {end}", "geo": country, "q": ",".join(batch_terms)}
                    ),
                    "queries": [q for q in records if q["term"] in batch_terms],
                }
            )
    (output / "browser-queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return queue


def export_browser_results(
    annual: Path,
    output: Path,
    downloads: list[dict[str, str]],
) -> dict[str, Any]:
    queue = prepare_browser_queue(annual, output)
    batches = {b["batch_id"]: b for b in queue}
    manifest_path = output / "browser-downloads.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    raw_dir = output / "raw-browser"
    raw_dir.mkdir(exist_ok=True)
    for download in downloads:
        batch_id = download["batch_id"]
        if batch_id not in batches:
            raise ValueError("Unknown browser batch")
        raw = Path(download["path"]).read_bytes()
        target = raw_dir / f"{batch_id}.csv"
        target.write_bytes(raw)
        manifest[batch_id] = {
            "path": str(target.resolve()),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "source_url": batches[batch_id]["source_url"],
            "retrieved_at": datetime.now(UTC).isoformat(),
        }
    records: list[dict[str, Any]] = []
    for batch in queue:
        batch_id = batch["batch_id"]
        if batch_id not in manifest:
            records.extend(
                {**q, "value": "", "status": "pending_browser_export", "comparison_group": batch_id}
                for q in batch["queries"]
            )
            continue
        entry = manifest[batch_id]
        raw = Path(entry["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Browser export hash mismatch")
        lines = raw.decode("utf-8-sig").splitlines()
        header_index = next(
            (
                i
                for i, line in enumerate(lines)
                if line
                and next(csv.reader([line]), [""])[0]
                in {"Week", "Month", "Day", "Semana", "Mês", "Dia"}
            ),
            None,
        )
        if header_index is None:
            raise ValueError("No supported date column in browser CSV")
        reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))
        assert reader.fieldnames
        date_column = reader.fieldnames[0]
        term_columns = {}
        for term in batch["terms"]:
            columns = [c for c in reader.fieldnames[1:] if c.startswith(term + ":")]
            if len(columns) != 1:
                raise ValueError(f"Browser export missing or duplicate term {term}")
            term_columns[term] = columns[0]
        observations: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in reader:
            sample_text = row[date_column]
            sample = date.fromisoformat(
                sample_text + "-01" if len(sample_text) == 7 else sample_text
            )
            if date_column in {"Month", "Mês"}:
                bucket_end = sample.replace(day=calendar.monthrange(sample.year, sample.month)[1])
            elif date_column in {"Week", "Semana"}:
                bucket_end = sample + timedelta(days=6)
            else:
                bucket_end = sample
            boundary_bucket = str(bucket_end > date.fromisoformat(batch["period_end"])).lower()
            if (
                not date.fromisoformat(batch["period_start"])
                <= sample
                <= date.fromisoformat(batch["period_end"])
            ):
                continue
            for term, column in term_columns.items():
                raw_value = row[column].strip()
                status = "observed_relative_index"
                value: float | str = ""
                if raw_value == "<1":
                    status = "below_reporting_threshold"
                elif raw_value in {"", "NA", "N/A"}:
                    status = "not_reported"
                else:
                    value = float(raw_value)
                    if not 0 <= value <= 100:
                        raise ValueError("Invalid browser Trends index")
                observations[(term, str(sample.year))].append(
                    {
                        "value": value,
                        "raw_value": raw_value,
                        "sample_date": sample.isoformat(),
                        "status": status,
                        "aggregation": date_column,
                        "boundary_bucket": boundary_bucket,
                    }
                )
        for query in batch["queries"]:
            samples = observations.get((query["term"], query["year"]), [])
            for measurement in samples or [{"value": "", "status": "no_reported_samples"}]:
                records.append(
                    {
                        **query,
                        **measurement,
                        "comparison_group": batch_id,
                        "period_start": batch["period_start"],
                        "period_end": batch["period_end"],
                        "source_url": batch["source_url"],
                        "raw_sha256": entry["sha256"],
                        "retrieved_at": entry["retrieved_at"],
                        "scale": "google_trends_batch_0_100",
                    }
                )
    with (output / "trends-browser-observations.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[*FIELDS, "comparison_group", "aggregation", "boundary_bucket"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(records)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "planned_batches": len(queue),
        "completed_batches": len(set(manifest) & set(batches)),
        "countries": len({b["country_iso2"] for b in queue}),
        "observed_rows": sum(bool(r.get("sample_date")) for r in records),
        "completed_countries": sorted(
            {
                b["country_iso2"]
                for b in queue
                if all(
                    x["batch_id"] in manifest
                    for x in queue
                    if x["country_iso2"] == b["country_iso2"]
                )
            }
        ),
        "csv_sha256": hashlib.sha256(
            (output / "trends-browser-observations.csv").read_bytes()
        ).hexdigest(),
        "notes": [
            "Up to five terms share a scale within each browser batch",
            "Annual assignment uses sample year; scale covers the full query window",
            "Common porn term repeats as anchor; do not count anchor repetitions twice",
            "boundary_bucket marks nominal months/weeks extending beyond the requested end",
            "No cross-country calibration or national consumption ranking",
        ],
    }
    (output / "browser-status.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
