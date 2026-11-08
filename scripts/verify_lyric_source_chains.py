"""Checkpointed verification of all staged lyrics against preserved web responses. No network."""

import argparse
import hashlib
import json
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
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
    try:
        with engine.connect() as conn, queue_part.open("w", encoding="utf-8") as queue:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout='120s'"))
            run = conn.execute(
                select(runs.c.id).order_by(runs.c.created_at.desc()).limit(1)
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
                            checked=sum(counts.values()),
                            counts=dict(counts),
                            network_requests=0,
                            paid_calls=0,
                        ),
                    )
            ledger.commit()
        queue_part.replace(args.output / "adjudication-queue.jsonl")
        publish_status(
            args.output / "status.json",
            dict(
                stage="completed",
                run_id=run,
                checked=sum(counts.values()),
                counts=dict(counts),
                observed_at=datetime.now(UTC).isoformat(),
                full_inventory=args.limit is None,
                identity_validated=0,
                completeness_validated=0,
                classification_ready=0,
                network_requests=0,
                paid_calls=0,
                production_writes=0,
                unchanged_results_reused=reused,
            ),
        )
    except Exception as exc:
        publish_status(
            args.output / "status.json",
            dict(
                stage="failed",
                error_type=type(exc).__name__,
                checked=sum(counts.values()),
                paid_calls=0,
            ),
        )
        raise
    finally:
        ledger.close()
        engine.dispose()


if __name__ == "__main__":
    main()
