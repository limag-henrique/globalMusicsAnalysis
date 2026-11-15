"""Read-only PostgreSQL/SQLite quality reconciliation; local checkpointed output only."""

import argparse
import csv
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, select, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.corpus_quality import QUALITY_AUDIT_VERSION, assess_acquired_lyric
from chart_observatory.lyrics.identity_collisions import flag_shared_text_identities
from chart_observatory.lyrics.quota_staging import blobs, candidates, runs
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data/derived/lyrics/quota-20261030"


def review_queue_record(run_id, candidate_id, text_sha256, provider, result, payload):
    """Build a lyrics-free, importable review row from the corpus audit result."""
    memberships = [
        {
            "country_code": binding["country_code"],
            "year": binding["year"],
            **({"position": binding["position"]} if binding.get("position") is not None else {}),
        }
        for binding in payload.get("chart_bindings", [])
    ]
    return {
        "run_id": run_id,
        "candidate_id": candidate_id,
        "text_sha256": text_sha256,
        "provider": provider,
        "flags": sorted(set(result.get("flags", []))),
        "quality_state": result["quality_state"],
        "memberships": memberships,
        "decision": "pending_human_review",
        "lyric_text_included": False,
    }


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--store-root", type=Path)
    parser.add_argument("--base-root", type=Path)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("limit must be positive")
    output = args.output.resolve()
    if output == STORE.resolve() or STORE.resolve() in output.parents:
        parser.error("audit output must be separate from the acquisition store")
    output.mkdir(parents=True, exist_ok=True)
    audit_sources = [
        Path(__file__),
        *[
            ROOT / "src/chart_observatory/lyrics" / name
            for name in ("corpus_quality.py", "quota_discovery.py", "text_quality.py")
        ],
    ]
    code_hash = hashlib.sha256(b"".join(p.read_bytes() for p in audit_sources)).hexdigest()
    checkpoint = sqlite3.connect(output / "audit-checkpoint.sqlite")
    checkpoint.execute(
        "CREATE TABLE IF NOT EXISTS results(run TEXT,id TEXT,fingerprint TEXT,"
        "result TEXT,PRIMARY KEY(run,id))"
    )
    store = args.store_root.resolve() if args.store_root else STORE
    if not store.is_relative_to(ROOT / "data/derived/lyrics"):
        parser.error("store outside project lyrics directory")
    local_results = {}
    sqlite_checks = []
    for source in dict.fromkeys((STORE, store)):
        with sqlite3.connect(
            (source / "acquisition.sqlite").as_uri() + "?mode=ro", uri=True
        ) as local:
            local.execute("PRAGMA query_only=ON")
            local_results.update(
                {
                    key: json.loads(value) if value else {}
                    for key, value in local.execute("SELECT identity,result FROM tasks")
                }
            )
            sqlite_checks.append(local.execute("PRAGMA quick_check").fetchone()[0])
    sqlite_check = "ok" if all(v == "ok" for v in sqlite_checks) else "failed"
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    totals, flags, providers, chain, lengths = (Counter() for _ in range(5))
    by_cell = defaultdict(Counter)
    identity_records = []
    review_count = 0
    queue_part = output / "review-queue.jsonl.part"
    queue_path = output / "review-queue.jsonl"
    seen = set()
    baseline = ROOT / "data/runtime/targeted-revision-20261103/repair-candidates.jsonl"
    previous_repair = {json.loads(x)["candidate_id"] for x in baseline.read_text().splitlines()}
    previous_states = Counter()
    try:
        with engine.connect() as conn:
            review_queue = queue_part.open("w", encoding="utf-8", newline="\n")
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout='120s'"))
            latest = select(runs.c.id)
            if args.base_root:
                latest = latest.where(
                    runs.c.manifest["selection_root"].as_string() == str(args.base_root.resolve())
                )
            run = conn.execute(latest.order_by(runs.c.created_at.desc()).limit(1)).scalar_one()
            query = (
                select(candidates, blobs.c.body)
                .outerjoin(blobs, blobs.c.sha256 == candidates.c.text_sha256)
                .where(candidates.c.run_id == run)
                .order_by(candidates.c.candidate_id)
            )
            if args.limit:
                query = query.limit(args.limit)
            for row in conn.execution_options(stream_results=True).execute(query).mappings():
                if any(
                    row[name]
                    for name in (
                        "identity_validated",
                        "completeness_validated",
                        "classification_ready",
                    )
                ):
                    raise ValueError(
                        "staging contract changed: independent validation audit required"
                    )
                key, body = row["candidate_id"], row["body"]
                fingerprint = hashlib.sha256(
                    json.dumps(
                        dict(
                            payload=row["payload"],
                            source=row["source_result"],
                            text_sha256=row["text_sha256"],
                            actual_sha256=hashlib.sha256(body.encode()).hexdigest()
                            if body
                            else None,
                            version=QUALITY_AUDIT_VERSION,
                            code_hash=code_hash,
                        ),
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode()
                ).hexdigest()
                previous = checkpoint.execute(
                    "SELECT result FROM results WHERE run=? AND id=? AND fingerprint=?",
                    (run, key, fingerprint),
                ).fetchone()
                result = (
                    json.loads(previous[0])
                    if previous
                    else assess_acquired_lyric(
                        row["payload"], row["source_result"], body, row["text_sha256"]
                    )
                )
                result.update(
                    candidate_id=key,
                    text_sha256=row["text_sha256"],
                    provider=row["source_result"].get("source", "UNKNOWN"),
                )
                review_queue.write(
                    json.dumps(
                        review_queue_record(
                            run,
                            key,
                            row["text_sha256"],
                            result["provider"],
                            result,
                            row["payload"],
                        ),
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
                review_count += 1
                local_result = local_results.get(key, {})
                result["local_chain"] = (
                    "same_text_hash"
                    if row["text_sha256"] and row["text_sha256"] == local_result.get("text_sha256")
                    else "different_or_missing_local_version"
                )
                if local_result.get("text_path") and result["local_chain"] == "same_text_hash":
                    path = Path(local_result["text_path"])
                    if not path.is_file():
                        result["local_chain"] = "missing_local_blob"
                    elif hashlib.sha256(path.read_bytes()).hexdigest() != row["text_sha256"]:
                        result["local_chain"] = "local_blob_hash_mismatch"
                checkpoint.execute(
                    "INSERT OR REPLACE INTO results VALUES (?,?,?,?)",
                    (run, key, fingerprint, json.dumps(result, ensure_ascii=False)),
                )
                totals[result["quality_state"]] += 1
                flags.update(result["flags"])
                providers[result["provider"]] += 1
                chain[result["local_chain"]] += 1
                lengths[
                    "missing"
                    if body is None
                    else "short"
                    if len(body) < 300
                    else "long"
                    if len(body) > 10000
                    else "standard"
                ] += 1
                if key in previous_repair:
                    previous_states[result["quality_state"]] += 1
                seen.add(key)
                for binding in row["payload"].get("chart_bindings", []):
                    by_cell[binding["country_code"], binding["year"]][result["quality_state"]] += 1
                if row["text_sha256"]:
                    identity_records.append(
                        dict(
                            candidate_id=key,
                            text_sha256=row["text_sha256"],
                            payload=row["payload"],
                            audit={},
                        )
                    )
                if len(seen) % 250 == 0:
                    checkpoint.commit()
                    publish_status(
                        output / "status.json",
                        dict(
                            stage="auditing",
                            checked=len(seen),
                            run_id=run,
                            network_requests=0,
                            paid_calls=0,
                        ),
                    )
            checkpoint.commit()
            review_queue.close()
            queue_part.replace(queue_path)
        collisions = flag_shared_text_identities(identity_records)
        summary = dict(
            observed_at=datetime.now(UTC).isoformat(),
            run_id=run,
            audit_version=QUALITY_AUDIT_VERSION,
            code_sha256=code_hash,
            candidates=len(seen),
            states=dict(totals),
            flags=dict(flags),
            providers=dict(providers),
            character_buckets=dict(lengths),
            local_chain=dict(chain),
            sqlite_quick_check=sqlite_check,
            collision_groups=len(collisions),
            previous_suspect_candidates=len(previous_repair),
            previous_suspects_in_scope=len(seen & previous_repair),
            previous_suspect_current_states=dict(previous_states),
            verified_complete=0,
            classification_ready=0,
            language="UNKNOWN_NOT_INFERRED_FROM_COUNTRY",
            full_inventory=args.limit is None,
            review_queue="review-queue.jsonl",
            review_queue_records=review_count,
            review_queue_sha256=sha256_file(queue_path),
            review_queue_contains_lyrics=False,
            network_requests=0,
            paid_calls=0,
            production_writes=0,
            caveat=(
                "States are source/heuristic screening, not confirmed error or completeness rates."
            ),
        )
        publish_status(output / "summary.json", summary)
        publish_status(
            output / "collisions.json", dict(groups=collisions, automatic_resolution=False)
        )
        country_year_path = output / "country-year-quality.csv"
        with country_year_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["country_code", "year", "state", "memberships"])
            for (country, year), counts in sorted(by_cell.items()):
                for state, count in sorted(counts.items()):
                    writer.writerow([country, year, state, count])
        summary_path = output / "summary.json"
        artifact_paths = [summary_path, queue_path, output / "collisions.json", country_year_path]
        publish_status(
            output / "manifest.json",
            {
                "run_id": run,
                "audit_version": QUALITY_AUDIT_VERSION,
                "audit_code_sha256": code_hash,
                "candidate_count": len(seen),
                "artifacts": {
                    path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
                    for path in artifact_paths
                },
                "lyrics_included_in_review_queue": False,
                "network_requests": 0,
                "paid_calls": 0,
                "production_writes": 0,
            },
        )
        publish_status(output / "status.json", dict(stage="completed", **summary))
        print(json.dumps(summary, ensure_ascii=False))
    finally:
        if "review_queue" in locals() and not review_queue.closed:
            review_queue.close()
        checkpoint.close()
        engine.dispose()


if __name__ == "__main__":
    main()
