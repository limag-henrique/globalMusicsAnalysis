"""Checkpointed verification of all staged lyrics against preserved web responses. No network."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, func, select, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.quota_staging import blobs, candidates, runs
from chart_observatory.lyrics.source_chain import verify_source_chain
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--base-root", type=Path)
    parser.add_argument(
        "--run-id", help="verify this exact staged run; never resolve it by recency"
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("limit must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    ledger = sqlite3.connect(args.output / "checkpoint.sqlite")
    ledger.execute(
        "CREATE TABLE IF NOT EXISTS results(run TEXT,id TEXT,signature TEXT,result TEXT,"
        "PRIMARY KEY(run,id))"
    )
    ledger.execute("CREATE INDEX IF NOT EXISTS results_signature ON results(id,signature)")
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    counts = Counter()
    evidence_hashes = {}
    reused = 0
    code_hash = hashlib.sha256(
        (ROOT / "src/chart_observatory/lyrics/source_chain.py").read_bytes()
    ).hexdigest()
    queue_part = args.output / "adjudication-queue.jsonl.part"
    run = None
    selection_root = None
    expected_candidates = 0
    try:
        with engine.connect() as conn, queue_part.open("w", encoding="utf-8") as queue:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout='120s'"))
            if args.run_id:
                selected = (
                    conn.execute(select(runs.c.id, runs.c.manifest).where(runs.c.id == args.run_id))
                    .mappings()
                    .one_or_none()
                )
                if selected is None:
                    raise ValueError(f"staged run does not exist: {args.run_id}")
                run = selected["id"]
                selection_root = (selected["manifest"] or {}).get("selection_root")
                if not selection_root:
                    raise ValueError(f"staged run has no selection_root: {run}")
                if args.base_root and Path(selection_root).resolve() != args.base_root.resolve():
                    raise ValueError(
                        "staged run selection mismatch: "
                        f"{selection_root} != {args.base_root.resolve()}"
                    )
            else:
                latest = select(runs.c.id, runs.c.manifest)
                if args.base_root:
                    latest = latest.where(
                        runs.c.manifest["selection_root"].as_string()
                        == str(args.base_root.resolve())
                    )
                selected = (
                    conn.execute(latest.order_by(runs.c.created_at.desc()).limit(1))
                    .mappings()
                    .one_or_none()
                )
                if selected is None:
                    raise ValueError("no staged run matches the requested selection")
                run = selected["id"]
                selection_root = (selected["manifest"] or {}).get("selection_root")
                if not selection_root:
                    raise ValueError(f"staged run has no selection_root: {run}")
                if args.base_root and Path(selection_root).resolve() != args.base_root.resolve():
                    raise ValueError(
                        "staged run selection mismatch: "
                        f"{selection_root} != {args.base_root.resolve()}"
                    )
            expected_candidates = conn.execute(
                select(func.count()).select_from(candidates).where(candidates.c.run_id == run)
            ).scalar_one()
            query = (
                select(candidates, blobs.c.body)
                .outerjoin(blobs, blobs.c.sha256 == candidates.c.text_sha256)
                .where(candidates.c.run_id == run)
                .order_by(candidates.c.candidate_id)
            )
            if args.limit:
                query = query.limit(args.limit)
            for row in conn.execution_options(stream_results=True).execute(query).mappings():
                # Resume only when the preserved responses still contain the same bytes.
                # Check them again in each invocation, including unchanged staged rows.
                evidence = []
                for event in row["source_result"].get("http_evidence", []):
                    if not event.get("cache_path"):
                        continue
                    path = Path(event["cache_path"]).resolve()
                    if path not in evidence_hashes:
                        try:
                            evidence_hashes[path] = (
                                hashlib.sha256(path.read_bytes()).hexdigest()
                                if path.is_relative_to(ROOT)
                                else "outside_project"
                            )
                        except OSError:
                            evidence_hashes[path] = "unavailable"
                    evidence.append((str(path), evidence_hashes[path]))
                signature = hashlib.sha256(
                    json.dumps(
                        dict(
                            code=code_hash,
                            evidence=evidence,
                            payload=row["payload"],
                            result=row["source_result"],
                            digest=row["text_sha256"],
                            actual=hashlib.sha256(row["body"].encode()).hexdigest()
                            if row["body"] is not None
                            else None,
                        ),
                        sort_keys=True,
                    ).encode()
                ).hexdigest()
                previous = ledger.execute(
                    "SELECT result FROM results WHERE id=? AND signature=? LIMIT 1",
                    (row["candidate_id"], signature),
                ).fetchone()
                reused += previous is not None
                checked = (
                    json.loads(previous[0])
                    if previous
                    else verify_source_chain(
                        row["payload"], row["source_result"], row["body"], row["text_sha256"], ROOT
                    )
                )
                counts[checked["status"]] += 1
                queue.write(
                    json.dumps(
                        dict(
                            run_id=run,
                            selection_root=selection_root,
                            candidate_id=row["candidate_id"],
                            title=row["payload"].get("title"),
                            artist=row["payload"].get("artist"),
                            lyrics_sha256=row["text_sha256"],
                            source_result_signature=signature,
                            source_check=checked,
                            decision="pending",
                            approval_evidence_required=(
                                "official_transcription_or_human_audio_verification"
                            ),
                            classification_ready=False,
                        ),
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                ledger.execute(
                    "INSERT OR REPLACE INTO results VALUES (?,?,?,?)",
                    (run, row["candidate_id"], signature, json.dumps(checked)),
                )
                if sum(counts.values()) % 100 == 0:
                    ledger.commit()
                    publish_status(
                        args.output / "status.json",
                        dict(
                            stage="verifying_web_evidence",
                            run_id=run,
                            selection_root=selection_root,
                            checked=sum(counts.values()),
                            expected_candidates=expected_candidates,
                            full_inventory=args.limit is None,
                            counts=dict(counts),
                            network_requests=0,
                            paid_calls=0,
                        ),
                    )
            ledger.commit()
        queue_part.replace(args.output / "adjudication-queue.jsonl")
        queue_path = args.output / "adjudication-queue.jsonl"
        checked_count = sum(counts.values())
        full_inventory = args.limit is None and checked_count == expected_candidates
        publish_status(
            args.output / "status.json",
            dict(
                stage="completed" if full_inventory else "partial",
                run_id=run,
                selection_root=selection_root,
                checked=checked_count,
                expected_candidates=expected_candidates,
                counts=dict(counts),
                observed_at=datetime.now(UTC).isoformat(),
                full_inventory=args.limit is None,
                complete=full_inventory,
                identity_validated=0,
                completeness_validated=0,
                classification_ready=0,
                network_requests=0,
                paid_calls=0,
                production_writes=0,
                unchanged_results_reused=reused,
            ),
        )
        publish_status(
            args.output / "manifest.json",
            {
                "run_id": run,
                "selection_root": selection_root,
                "expected_candidates": expected_candidates,
                "checked": checked_count,
                "complete": full_inventory,
                "source_chain_code_sha256": code_hash,
                "queue": {
                    "file": queue_path.name,
                    "sha256": hashlib.sha256(queue_path.read_bytes()).hexdigest(),
                    "bytes": queue_path.stat().st_size,
                },
                "network_requests": 0,
                "paid_calls": 0,
                "production_writes": 0,
            },
        )
    except Exception as exc:
        publish_status(
            args.output / "status.json",
            dict(
                stage="failed",
                error_type=type(exc).__name__,
                run_id=run,
                selection_root=selection_root,
                expected_candidates=expected_candidates,
                checked=sum(counts.values()),
                full_inventory=False,
                paid_calls=0,
            ),
        )
        raise
    finally:
        ledger.close()
        engine.dispose()


if __name__ == "__main__":
    main()
