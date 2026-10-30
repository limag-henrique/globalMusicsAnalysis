"""Read-only preparation: separate annual windows, evidence gates and cached recovery.

No database writes, model calls or automatic promotion of scraped candidates.
Use a fresh output directory; historical artifacts remain untouched.
"""

import argparse
import csv
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# This machine has little available RAM. Set before importing Polars.
os.environ.setdefault("POLARS_MAX_THREADS", "2")

import polars as pl
from import_web_chart_titles import validate_snapshot
from sqlalchemy import create_engine, text

from chart_observatory.config import Settings
from chart_observatory.ingestion.annual_selection import select_annual
from chart_observatory.lyrics.annual_cohort import select_annual_top80
from chart_observatory.lyrics.annual_eligibility import select_eligible
from chart_observatory.lyrics.identity_quarantine import load_suspended_sources
from chart_observatory.lyrics.repository import AUTHORIZED_RIGHTS
from chart_observatory.lyrics.review_evidence import load_review_evidence
from chart_observatory.sources.catalog import _country_aliases

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "data/derived/research_quality/annual-top80-20261024-v2"
RAW = ROOT / "data/raw/annual_top80/20261021"
CUTOFF = date(2026, 10, 21)


def jsonl(path):
    if not path.exists():
        return
    with path.open("rb") as handle:
        for line in handle:
            if not line.endswith(b"\n"):
                raise ValueError(f"incomplete ledger tail: {path}")
            if line.strip():
                yield json.loads(line)


def dump_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def csv_rows(path, rows):
    if rows:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def windows(year, end):
    if year < 2026:
        yield "full_year", date(year, 1, 1), date(year, 12, 31)
        yield "equivalent", date(year, 1, 1), date(year, end.month, end.day)
    else:
        yield "partial_2026", date(year, 1, 1), end


def database_metadata(profile=None):
    """Return only metadata in one read-only snapshot, without lyric bodies."""
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            suspended = load_suspended_sources()
            docs = {str(r["id"]): (str(r["canonical_track_id"]), r["content_sha256"])
                    for r in conn.execute(text(
                        "SELECT id, canonical_track_id, content_sha256, rights_status, source "
                        "FROM lyric_documents"
                    )).mappings()
                    if r["rights_status"] in AUTHORIZED_RIGHTS
                    and r["source"].upper() not in suspended}
            links = defaultdict(set)
            for row in conn.execute(text("""SELECT p.platform_code, p.native_id,
                l.canonical_track_id FROM platform_items p JOIN platform_item_track_links l
                ON l.platform_item_id=p.id""")).mappings():
                links[f'{row["platform_code"]}:{row["native_id"]}'].add(
                    str(row["canonical_track_id"]))
            counts = [dict(r) for r in conn.execute(text("""SELECT model_id, prompt_version,
                taxonomy_version, classification_status, count(*) AS count
                FROM lyric_classification_snapshots GROUP BY 1,2,3,4""")).mappings()]
            reusable = []
            # Historical rows lack normalization and resolved model configuration.
            # Their three-field signature cannot prove compatibility with revision v2.
            return docs, links, {"status": "available", "authorized_documents": len(docs),
                                 "classifications": counts}, reusable
    except Exception as exc:
        # Do not print credentials or connection URLs in exception messages.
        return {}, {}, {"status": "unavailable", "error_type": type(exc).__name__}, []
    finally:
        engine.dispose()


def daily_candidates(markets, end, limit):
    paths = [ROOT / "data/normalized" / f"{name}_observations.parquet"
             for name in ("mgd", "kaggle_spotify")]
    source = pl.concat([pl.scan_parquet(p) for p in paths]).filter(
        (pl.col("origin_platform") == "SPOTIFY") & (pl.col("metric_type") == "STREAMS")
        & (pl.col("metric_value") >= 0) & (pl.col("period_start") == pl.col("period_end"))
        & pl.col("chart_name").str.to_lowercase().str.contains("top")
    ).with_columns(
        pl.col("country_code").replace(_country_aliases()).alias("market_code"),
        pl.col("period_start").dt.year().alias("year"),
        pl.col("native_id").str.extract(r"(?:/track/)?([A-Za-z0-9]{22})(?:\?.*)?$", 1)
        .alias("chart_track_id"),
    ).filter(pl.col("chart_track_id").is_not_null() & pl.col("market_code").is_in(markets))
    candidates, coverage = [], []
    for year in range(2017, 2027):
        yearly = source.filter(pl.col("year") == year)
        for window, start, stop in windows(year, end):
            scoped = yearly.filter(pl.col("period_start").is_between(start, stop))
            if not scoped.select(pl.len()).collect(engine="streaming").item():
                continue
            ranked = select_annual_top80(scoped, candidate_limit=limit)
            expected_days = (stop - start).days + 1
            for (market,), rows in ranked.partition_by("market_code", as_dict=True).items():
                days = rows["observed_days"][0]
                status = "COMPLETE" if days == expected_days else "INCOMPLETE"
                coverage.append(dict(country_code=market, year=year, platform="SPOTIFY",
                                     window=window, period_start=start, period_end=stop,
                                     expected_periods=expected_days, collected_periods=days,
                                     coverage_status=status, metric="STREAMS"))
                for row in rows.to_dicts():
                    candidates.append(dict(
                        country_code=market, year=year, platform="SPOTIFY", window=window,
                        position=row["annual_rank"],
                        candidate_id=f'SPOTIFY:{row["chart_track_id"]}',
                        recording_id=None, title=row["track_title"], artist=row["artist"],
                        metric_value=row["annual_streams"], coverage_status=status,
                        period_start=start, period_end=stop,
                    ))
        print(f"daily {year}: {len(candidates)} cumulative memberships", flush=True)
    return candidates, coverage


def weekly_candidates(markets, end, limit):
    inventory = json.loads((RAW / "inventory_manifest.json").read_text(encoding="utf-8"))
    available = set(inventory["available_markets"])
    paths = defaultdict(list)
    for path in sorted(RAW.glob("YOUTUBE_CHARTS_WEB_*.json")):
        parts = path.stem.split("_")
        paths[parts[3], int(parts[4][:4])].append(path)
    candidates, coverage = [], []
    for market in markets:
        for year in range(2017, 2027):
            docs = []
            for path in paths[market, year]:
                doc = validate_snapshot(json.loads(path.read_text(encoding="utf-8")))
                if doc.get("observed_country_code") == market:
                    docs.append({**doc, "provider": "YOUTUBE"})
            for window, start, stop in windows(year, end):
                # Native Top Songs weeks end on Thursday, including boundary weeks.
                day, required = start, set()
                while day <= stop:
                    if day.weekday() == 3:
                        required.add(day.isoformat())
                    day += timedelta(days=1)
                result = select_annual(docs, {(market, year, "YOUTUBE"): required},
                                       candidate_limit=limit, include_comparison=True)
                observed = next(r for r in result["coverage"] if r["platform"] == "YOUTUBE")
                status = observed["status"] if market in available else "UNAVAILABLE"
                coverage.append(dict(country_code=market, year=year, platform="YOUTUBE",
                                     window=window, period_start=start, period_end=stop,
                                     expected_periods=len(required),
                                     collected_periods=observed["collected_periods"],
                                     coverage_status=status, metric="VIEWS"))
                for row in result["selections"]:
                    key = json.dumps([row["title"], row["artist"]], ensure_ascii=False)
                    candidates.append({**row, "window": window, "recording_id": None,
                                       "candidate_id": ("YOUTUBE:" + row["native_id"]
                                                        if row.get("native_id") else
                                                        "YOUTUBE_METADATA:" + hashlib.sha256(
                                                            key.encode()).hexdigest()),
                                       "coverage_status": status,
                                       "period_start": start, "period_end": stop})
    return candidates, coverage


def prepare(output, limit, validation_path, profile=None, rankings_from=None,
            acquisition_rank=80):
    output.mkdir(parents=True, exist_ok=False)
    markets = pl.read_parquet(ROOT / "research/article/analysis-final/country-metrics.parquet")[
        "market_code"].to_list()
    inventory = json.loads((RAW / "inventory_manifest.json").read_text(encoding="utf-8"))
    end = min(CUTOFF, max(date.fromisoformat(p["end"]) for p in inventory["periods"]))
    if rankings_from:
        previous = json.loads((rankings_from / "manifest.json").read_text(encoding="utf-8"))
        if (previous["protocol"] != "annual-eligible-reserve-v2"
                or previous["candidate_limit"] != limit
                or previous["effective_cutoff"] != end.isoformat()):
            raise ValueError("cached ranking uses a different selection contract")
        candidates = list(jsonl(rankings_from / "candidates.jsonl"))
        with (rankings_from / "country-year-platform-coverage.csv").open(
            encoding="utf-8-sig", newline="",
        ) as handle:
            coverage = list(csv.DictReader(handle))
        for row in coverage:
            for field in ("year", "expected_periods", "collected_periods"):
                row[field] = int(row[field])
    else:
        candidates, coverage = daily_candidates(markets, end, limit)
        weekly, weekly_coverage = weekly_candidates(markets, end, limit)
        candidates.extend(weekly)
        coverage.extend(weekly_coverage)
    # Persist the costly rankings before optional database/ledger reconciliation.
    dump_rows(output / "candidates.jsonl", candidates)
    csv_rows(output / "country-year-platform-coverage.csv", coverage)
    present = {(r["country_code"], r["year"], r["window"]) for r in coverage
               if r["platform"] == "SPOTIFY"}
    for market in markets:
        for year in range(2017, 2027):
            for window, start, stop in windows(year, end):
                if (market, year, window) not in present:
                    coverage.append(dict(country_code=market, year=year, platform="SPOTIFY",
                                         window=window, period_start=start, period_end=stop,
                                         expected_periods=(stop-start).days+1, collected_periods=0,
                                         coverage_status="UNAVAILABLE", metric="STREAMS"))
    documents, links, database, reusable = database_metadata(profile)
    for row in candidates:
        identities = links.get(row["candidate_id"], set())
        row["recording_id"] = next(iter(identities)) if len(identities) == 1 else None
    validations = list(jsonl(validation_path)) if validation_path else []
    blocked = {(r["document_id"], r["lyrics_hash"]) for r in load_review_evidence()
               if r["status"] == "pending_adjudication"}
    quarantine = json.loads((ROOT / "config/lyrics_identity_quarantine.json").read_text(
        encoding="utf-8"))
    blocked.update((r["lyric_document_id"], r["lyrics_hash"]) for r in quarantine["entries"]
                   if r["decision"] != "confirmed_match")
    result = select_eligible(candidates, validations, current_documents=documents, blocked=blocked,
                             reusable_classifications=reusable)
    for task in result["classification_queue"]:
        task["classification_profile"] = profile
        task["status"] = "blocked_pending_complete_v2_signature"
        task["not_for_submission"] = True
    # Existing candidates are reusable for validation, never promoted to validated.
    old_targets = {r["recording_id"]: r for r in jsonl(HISTORICAL / "recovery-targets.jsonl")}
    acquired = {}
    ledger = HISTORICAL / "acquisition/acquisition.jsonl"
    ledger_statuses = Counter()
    for row in jsonl(ledger):
        ledger_statuses[row["status"]] += 1
        bindings = row.get("original_bindings") or [{"document_id": row["original_document_id"]}]
        for binding in bindings:
            acquired[binding["document_id"]] = row["status"]
        if row.get("recording_id"):
            acquired[row["recording_id"]] = row["status"]
    recovery, seen, reuse, grouped = [], set(), Counter(), defaultdict(list)
    for row in candidates:
        grouped[row["candidate_id"]].append(row)
    def acquisition_status(key):
        target = old_targets.get(key)
        document_id = target["document_id"] if target else f"chart:{key}"
        return acquired.get(key, acquired.get(document_id))

    # Known missing lyrics advance the reserve, but unknown validation never
    # triggers an eager fetch of the whole reserve. Keep the original positions.
    cell_rows = defaultdict(list)
    for row in candidates:
        if row["coverage_status"] == "COMPLETE":
            cell_rows[tuple(row[k] for k in
                            ("country_code", "year", "platform", "window"))].append(row)
    acquisition_frontiers = {}
    for cell, rows in cell_rows.items():
        frontier = acquisition_rank
        while True:
            unavailable = sum(r["position"] <= frontier and
                              acquisition_status(r["candidate_id"]) == "not_found" for r in rows)
            advanced = min(limit, max(acquisition_rank, 80 + unavailable))
            if advanced == frontier:
                break
            frontier = advanced
        acquisition_frontiers[cell] = frontier
    deferred = 0
    ordered = sorted(grouped.items(), key=lambda pair: min(
        (r["position"], r["country_code"], r["year"]) for r in pair[1]))
    for key, memberships in ordered:
        seen.add(key)
        required = [r for r in memberships if r["coverage_status"] == "COMPLETE"
                    and r["position"] <= acquisition_frontiers[tuple(r[k] for k in
                        ("country_code", "year", "platform", "window"))]]
        if not required:
            deferred += 1
            continue
        row = min(required, key=lambda r: (r["position"], r["country_code"], r["year"]))
        target = old_targets.get(key)
        document_id = target["document_id"] if target else f"chart:{key}"
        status = acquired.get(key, acquired.get(document_id))
        if status and status != "http_error":
            reuse[status] += 1
            continue
        task = dict(
            document_id=document_id, lyrics_hash=target["lyrics_hash"] if target else "",
            track_id=row["recording_id"], recording_id=key, title=row["title"],
            artist=row["artist"], chart_bindings=[{k: m[k] for k in
                ("country_code", "year", "platform", "window", "position")}
                for m in memberships],
            cohort_version="annual-eligible-reserve-v2",
        )
        recovery.append(task)
    dump_rows(output / "candidates.jsonl", candidates)
    for name, rows in result.items():
        dump_rows(output / f"{name}.jsonl", rows)
    dump_rows(output / "recovery-targets.jsonl", recovery)
    csv_rows(output / "country-year-platform-coverage.csv", coverage)
    manifest = dict(
        created_at=datetime.now(UTC).isoformat(), protocol="annual-eligible-reserve-v2",
        requested_cutoff=CUTOFF, effective_cutoff=end, years=[2017, 2026], markets=len(markets),
        candidate_limit=limit, eligible_target=80, candidate_memberships=len(candidates),
        unique_candidate_identities=len(seen), existing_acquisition_reused=dict(reuse),
        acquisition_rank=acquisition_rank, deferred_reserve_or_incomplete_identities=deferred,
        cells_with_acquisition_reserves=sum(v > 80 for v in acquisition_frontiers.values()),
        new_or_retry_acquisition_targets=len(recovery), source_ledger=str(ledger),
        source_ledger_rows=dict(ledger_statuses), database=database,
        eligible_memberships=len(result["eligible"]),
        classification_queue=len(result["classification_queue"]),
        classification_profile=profile,
        rankings_from=str(rankings_from) if rankings_from else None,
        paid_calls=0, database_writes=0, article_regenerated=False,
        identity_warning="Metadata-only YouTube identities require canonical reconciliation",
        validation_warning="No source success or cross-site agreement proves original integrity",
        polars_threads=os.environ["POLARS_MAX_THREADS"],
        disk_free_bytes=shutil.disk_usage(ROOT).free,
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str),
                                         encoding="utf-8")
    print(json.dumps(manifest, default=str), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-limit", type=int, choices=(120, 200), default=120)
    parser.add_argument("--validations", type=Path)
    parser.add_argument("--model-id")
    parser.add_argument("--taxonomy-version")
    parser.add_argument("--prompt-version")
    parser.add_argument("--rankings-from", type=Path,
                        help="Reuse frozen local rankings without repeating aggregation")
    parser.add_argument("--acquisition-rank", type=int, choices=(80, 120, 200), default=80,
                        help="Acquire original top 80 first; expand after validating losses")
    args = parser.parse_args()
    profile = {k: getattr(args, k) for k in ("model_id", "taxonomy_version", "prompt_version")}
    if (args.validations or any(profile.values())) and not all(profile.values()):
        parser.error("validations require model-id, taxonomy-version and prompt-version for reuse")
    if args.acquisition_rank > args.candidate_limit:
        parser.error("acquisition-rank cannot exceed candidate-limit")
    prepare(args.output, args.candidate_limit, args.validations,
            profile if all(profile.values()) else None, args.rankings_from, args.acquisition_rank)
