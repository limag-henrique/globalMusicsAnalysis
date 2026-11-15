"""Read-only audit of staged lyric hashes absent from or different in local stores."""

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, select, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.quota_staging import blobs, candidates, runs
from chart_observatory.lyrics.source_chain import verify_source_chain
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "data/derived/annual_revision/global-2018-2026-20261108"
DEFAULT_STORE = ROOT / "data/derived/lyrics/quota-20261030"
DEFAULT_CURRENT_STORE = ROOT / "data/derived/lyrics/global-20261108"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def memberships(payload):
    return [
        {
            "country_code": item["country_code"],
            "year": item["year"],
            **({"position": item["position"]} if item.get("position") is not None else {}),
        }
        for item in payload.get("chart_bindings", [])
    ]


def exact_replay_record(candidate_id, text_sha256, evidence_sha256, source_url, body, payload):
    if hashlib.sha256(body.encode()).hexdigest() != text_sha256:
        raise ValueError("body does not reproduce the staged text hash")
    if not isinstance(evidence_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", evidence_sha256):
        raise ValueError("preserved evidence response hash is invalid")
    return {
        "candidate_id": candidate_id,
        "text_sha256": text_sha256,
        "evidence_response_sha256": evidence_sha256,
        "source_url": source_url,
        "body": body,
        "memberships": memberships(payload),
        "identity_review": "pending",
        "completeness_review": "pending",
        "rights_review": "pending",
        "canonical": False,
        "classification_ready": False,
    }


def _load_store(path):
    if not path.is_relative_to(ROOT / "data/derived/lyrics"):
        raise ValueError("lyrics store must stay under data/derived/lyrics")
    with sqlite3.connect((path / "acquisition.sqlite").as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        check = db.execute("PRAGMA quick_check").fetchone()[0]
        tasks = {
            key: json.loads(value) if value else {}
            for key, value in db.execute("SELECT identity,result FROM tasks")
        }
    return tasks, check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-root", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--run-id")
    parser.add_argument("--store-root", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--current-store-root", type=Path, default=DEFAULT_CURRENT_STORE)
    parser.add_argument("--reconciliation-output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if (
        output == (ROOT / "data/derived/lyrics").resolve()
        or (ROOT / "data/derived/lyrics").resolve() in output.parents
    ):
        parser.error("audit output must be separate from acquisition stores")
    output.mkdir(parents=True, exist_ok=True)
    script_hash = sha256_file(Path(__file__))
    reconciliation_dir = (
        args.reconciliation_output.resolve() if args.reconciliation_output else None
    )
    reconciliation_part = None
    reconciliation_file = None
    if reconciliation_dir:
        if not reconciliation_dir.is_relative_to(ROOT / "data/runtime"):
            parser.error("reconciliation output must stay under data/runtime")
        if reconciliation_dir.exists():
            parser.error("reconciliation output already exists; use a new immutable run directory")
        reconciliation_dir.mkdir(parents=True)
        reconciliation_part = reconciliation_dir / "exact-byte-replays.jsonl.part"
        reconciliation_file = reconciliation_dir / "exact-byte-replays.jsonl"

    legacy, local_check = _load_store(args.store_root.resolve())
    current, current_check = _load_store(args.current_store_root.resolve())
    merged = {**legacy, **current}
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    counts, providers, evidence_hashes = Counter(), Counter(), set()
    queue_path = output / "review-queue.jsonl"
    try:
        replay_count = 0
        with (
            engine.connect() as conn,
            queue_path.open("w", encoding="utf-8", newline="\n") as queue,
        ):
            replay_writer = (
                reconciliation_part.open("w", encoding="utf-8", newline="\n")
                if reconciliation_part
                else None
            )
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout='120s'"))
            run_query = select(runs.c.id).where(
                runs.c.manifest["selection_root"].as_string() == str(args.base_root.resolve())
            )
            if args.run_id:
                run_query = run_query.where(runs.c.id == args.run_id)
            run = conn.execute(run_query.order_by(runs.c.created_at.desc()).limit(1)).scalar_one()
            query = (
                select(candidates, blobs.c.body)
                .outerjoin(blobs, blobs.c.sha256 == candidates.c.text_sha256)
                .where(candidates.c.run_id == run)
                .order_by(candidates.c.candidate_id)
            )
            for row in conn.execution_options(stream_results=True).execute(query).mappings():
                candidate_id = row["candidate_id"]
                local_hash = merged.get(candidate_id, {}).get("text_sha256")
                db_hash = row["text_sha256"]
                if not db_hash:
                    counts["local_only_db_missing" if local_hash else "no_text_db_or_store"] += 1
                    continue
                if db_hash == local_hash:
                    counts["same_text_hash"] += 1
                    continue
                category = "db_only_local_missing" if not local_hash else "db_local_hash_differs"
                counts[category] += 1
                legacy_hash = legacy.get(candidate_id, {}).get("text_sha256")
                current_hash = current.get(candidate_id, {}).get("text_sha256")
                if legacy_hash == db_hash and current_hash and current_hash != db_hash:
                    counts["legacy_match_overwritten_by_current"] += 1
                check = verify_source_chain(
                    row["payload"], row["source_result"], row["body"], db_hash, ROOT
                )
                counts[f"source_chain:{check['status']}"] += 1
                if check.get("exact_text_hash_match"):
                    counts["source_reproduced_exact_bytes"] += 1
                    if (
                        check["status"] == "source_chain_matched"
                        and not check.get("metadata_flags")
                        and hashlib.sha256(row["body"].encode()).hexdigest() == db_hash
                    ):
                        counts["exact_byte_reconciliation_eligible"] += 1
                        if replay_writer:
                            replay_writer.write(
                                json.dumps(
                                    exact_replay_record(
                                        candidate_id,
                                        db_hash,
                                        check["evidence_sha256"],
                                        check["source_url"],
                                        row["body"],
                                        row["payload"],
                                    ),
                                    ensure_ascii=False,
                                    sort_keys=True,
                                )
                                + "\n"
                            )
                            replay_count += 1
                elif check.get("extracted_text_sha256"):
                    counts["source_reproduced_normalized_only"] += 1
                if isinstance(check.get("evidence_sha256"), str):
                    evidence_hashes.add(check["evidence_sha256"])
                providers[row["source_result"].get("source", "UNKNOWN")] += 1
                queue.write(
                    json.dumps(
                        {
                            "run_id": run,
                            "candidate_id": candidate_id,
                            "text_sha256": db_hash,
                            "local_text_sha256": local_hash,
                            "provider": row["source_result"].get("source", "UNKNOWN"),
                            "memberships": memberships(row["payload"]),
                            "source_chain_status": check["status"],
                            "exact_text_hash_match": check.get("exact_text_hash_match", False),
                            "extracted_text_sha256": check.get("extracted_text_sha256"),
                            "metadata_flags": check.get("metadata_flags", []),
                            "evidence_response_sha256": check.get("evidence_sha256"),
                            "source_url": check.get("source_url"),
                            "errors": check.get("errors", []),
                            "decision": "pending_human_review",
                            "classification_ready": False,
                            "lyric_text_included": False,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )
            if replay_writer:
                replay_writer.close()
                reconciliation_part.replace(reconciliation_file)
        mismatch_total = counts["db_only_local_missing"] + counts["db_local_hash_differs"]
        db_only_count = counts["db_only_local_missing"]
        differing_count = counts["db_local_hash_differs"]
        local_only_count = counts["local_only_db_missing"]
        summary = {
            "observed_at": datetime.now(UTC).isoformat(),
            "run_id": run,
            "scope": "DB text hashes absent from or different in merged local stores",
            "same_text_hash": counts.pop("same_text_hash", 0),
            "db_only_local_missing": counts.pop("db_only_local_missing", 0),
            "db_local_hash_differs": counts.pop("db_local_hash_differs", 0),
            "local_only_db_missing": counts.pop("local_only_db_missing", 0),
            "local_hash_nonmatches": differing_count + local_only_count,
            "net_db_minus_local_hash_count": db_only_count - local_only_count,
            "no_text_db_or_store": counts.pop("no_text_db_or_store", 0),
            "legacy_match_overwritten_by_current": counts.pop(
                "legacy_match_overwritten_by_current", 0
            ),
            "mismatched_db_candidates": mismatch_total,
            "source_chain_counts": {
                key.removeprefix("source_chain:"): value
                for key, value in counts.items()
                if key.startswith("source_chain:")
            },
            "source_reproduced_exact_bytes": counts["source_reproduced_exact_bytes"],
            "source_reproduced_normalized_only": counts["source_reproduced_normalized_only"],
            "providers": dict(providers),
            "distinct_preserved_response_hashes": len(evidence_hashes),
            "preserved_response_sha256": sorted(evidence_hashes),
            "local_store_quick_checks": [local_check, current_check],
            "review_queue": queue_path.name,
            "review_queue_sha256": sha256_file(queue_path),
            "review_queue_contains_lyrics": False,
            "exact_byte_replay_records": replay_count,
            "exact_byte_reconciliation_eligible": counts["exact_byte_reconciliation_eligible"],
            "identity_approval": 0,
            "completeness_approval": 0,
            "classification_ready": 0,
            "network_requests": 0,
            "paid_calls": 0,
            "production_writes": 0,
        }
        publish_status(output / "summary.json", summary)
        publish_status(
            output / "manifest.json",
            {
                "run_id": run,
                "base_root": str(args.base_root.resolve()),
                "script_sha256": script_hash,
                "artifacts": {
                    path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
                    for path in (output / "summary.json", queue_path)
                },
                "lyrics_included": False,
                "network_requests": 0,
                "paid_calls": 0,
                "production_writes": 0,
            },
        )
        if reconciliation_dir and reconciliation_file:
            reconciliation_manifest = {
                "run_id": run,
                "artifact_type": "quarantined exact-byte source replays",
                "record_count": replay_count,
                "file": reconciliation_file.name,
                "sha256": sha256_file(reconciliation_file),
                "bytes": reconciliation_file.stat().st_size,
                "identity_review": "pending",
                "completeness_review": "pending",
                "rights_review": "pending",
                "canonical_import": False,
                "classification_ready": False,
                "network_requests": 0,
                "paid_calls": 0,
                "production_writes": 0,
            }
            publish_status(reconciliation_dir / "manifest.json", reconciliation_manifest)
            publish_status(
                reconciliation_dir / "status.json",
                {"stage": "quarantined_not_canonical", **reconciliation_manifest},
            )
        print(json.dumps(summary, ensure_ascii=False))
    finally:
        if "replay_writer" in locals() and replay_writer and not replay_writer.closed:
            replay_writer.close()
        engine.dispose()


if __name__ == "__main__":
    main()
