"""Recover exact-ID gaps of a rebuilt selection without requiring legacy preservation.

All writes are isolated acquisition or immutable pending-review staging. This
worker serializes its network phase before restarting a checkpoint comparator.
"""

import argparse
import hashlib
import json
import msvcrt
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from chart_observatory.config import Settings
from chart_observatory.ingestion.import_quotas import recovery_targets
from chart_observatory.lyrics.global_import import seed_exact_native_results
from chart_observatory.lyrics.identity_collisions import flag_shared_text_identities
from chart_observatory.lyrics.quota_acquisition import AcquisitionStore, PacedHTTP, identity
from chart_observatory.lyrics.quota_discovery import audit_saved_result, recover_with_fallback
from chart_observatory.lyrics.quota_staging import persist_lyric_staging
from chart_observatory.research_flow import load_selection
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]


def read_snapshot(path):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        return {
            key: (json.loads(payload), json.loads(result), body, digest)
            for key, payload, result, body, digest in db.execute(
                "SELECT id,payload,baseline,body,digest FROM inputs"
            )
        }


def stage_records(targets, snapshot, store):
    records, texts = [], {}
    for payload in targets:
        key = payload["recording_id"]
        if key in snapshot:
            previous, result, body, digest = snapshot[key]
            status = "inherited_exact_candidate_pending_review"
        else:
            row = store.conn.execute(
                "SELECT payload,result,status FROM tasks WHERE identity=?", (key,)
            ).fetchone()
            previous = json.loads(row[0]) if row else payload
            result = json.loads(row[1]) if row and row[1] else {}
            status = row[2] if row else "not_enqueued"
            digest, body = result.get("text_sha256"), None
            if digest:
                body = Path(result["text_path"]).read_bytes().decode("utf-8")
        if digest and (
            not isinstance(body, str) or hashlib.sha256(body.encode()).hexdigest() != digest
        ):
            raise ValueError("snapshot/delta text hash mismatch")
        audit = audit_saved_result(payload, result)
        if any(identity(previous.get(f)) != identity(payload.get(f)) for f in ("title", "artist")):
            audit["text_quality_flags"].append("retrieval_metadata_requires_reconciliation")
        if digest:
            texts[digest] = body
        records.append(
            dict(
                candidate_id=key,
                payload=payload,
                source_result=result,
                audit=audit,
                acquisition_status=status,
                text_sha256=digest,
            )
        )
    flag_shared_text_identities(records)
    return records, texts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--resume-comparison", required=True, type=Path)
    parser.add_argument("--hours", type=float, default=4)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    args = parser.parse_args()
    for name in ("selection", "snapshot", "state", "store", "resume_comparison"):
        value = getattr(args, name).resolve()
        if not value.is_relative_to(ROOT) or not 0 < args.hours <= 24:
            raise ValueError("use project-local paths and a bounded window")
        setattr(args, name, value)
    args.state.mkdir(parents=True, exist_ok=True)
    owner = (args.state / "owner.lock").open("a+b")
    owner.seek(0)
    if not owner.read(1):
        owner.write(b"0")
        owner.flush()
    owner.seek(0)
    msvcrt.locking(owner.fileno(), msvcrt.LK_NBLCK, 1)

    def report(stage, **kw):
        publish_status(
            args.state / "status.json",
            dict(
                stage=stage,
                pid=os.getpid(),
                updated_at=datetime.now(UTC).isoformat(),
                paid_calls=0,
                approvals=0,
                classification_ready=False,
                **kw,
            ),
        )

    manifest, _, members, hashes = load_selection(args.selection)
    targets = recovery_targets(members)
    snapshot = read_snapshot(args.snapshot)
    delta = [p for p in targets if p["recording_id"] not in snapshot]
    store = AcquisitionStore(args.store)
    # The exclusive owner lock is held; a prior interrupted owner's unfinished
    # transaction/request may be retried using preserved response cache.
    with store.conn:
        store.conn.execute("UPDATE tasks SET status='pending' WHERE status='running'")
    for payload in delta:
        store.enqueue(payload["recording_id"], payload)
    reused = 0
    for legacy in ("global-20261108", "quota-20261030"):
        reused += seed_exact_native_results(store, delta, ROOT / "data/derived/lyrics" / legacy)
    (args.state / "delta-candidates.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in delta), encoding="utf-8"
    )
    report(
        "prepared",
        delta_candidates=len(delta),
        delta_positions=sum(len(p["chart_bindings"]) for p in delta),
        reused=reused,
    )
    records, texts = stage_records(targets, snapshot, store)
    cell_counts = {}
    for r in records:
        for b in r["payload"]["chart_bindings"]:
            cell = (b["country_code"], b["year"])
            c = cell_counts.setdefault(cell, Counter())
            c["known"] += 1
            c["text"] += bool(r["text_sha256"])
    low = {k for k, v in cell_counts.items() if v["text"] * 5 < v["known"] * 4}
    with sqlite3.connect(args.snapshot.as_uri() + "?mode=ro", uri=True) as db:
        differences = {
            k: json.loads(v)
            for k, v in db.execute(
                "SELECT id,result FROM results "
                "WHERE json_extract(result,'$.status')='web_text_differs'"
            )
        }
    queue = []
    for r in records:
        bindings = r["payload"]["chart_bindings"]
        reasons = []
        if not r["text_sha256"] and any((b["country_code"], b["year"]) in low for b in bindings):
            reasons.append("missing_text_in_cell_below_80_availability")
        if r["candidate_id"] in differences:
            reasons.append("web_text_differs_requires_full_edition_review")
        if reasons:
            queue.append(
                dict(
                    candidate_id=r["candidate_id"],
                    text_sha256=r["text_sha256"],
                    chart_bindings=bindings,
                    reasons=reasons,
                    approvals=[],
                    reviewer_count_required=2,
                    classification_ready=False,
                )
            )
    (args.state / "validation-queue.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in queue), encoding="utf-8"
    )
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 10})

    def stage(phase):
        records, texts = stage_records(targets, snapshot, store)
        summary = dict(
            selection_root=str(args.selection),
            global_manifest_sha256=hashes[str(args.selection / "manifest.json")],
            memberships=manifest["memberships"],
            unique_candidates=len(targets),
            text_candidates=sum(bool(r["text_sha256"]) for r in records),
            source_comparison_snapshot=str(args.snapshot),
            source_comparison_sha256=hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
            phase=phase,
            state="pending_identity_integrity_and_rights_review",
        )
        local_engine = create_engine("sqlite:///" + str(args.state / "pending-staging.sqlite"))
        try:
            local_result = persist_lyric_staging(local_engine, summary, records, texts)
        finally:
            local_engine.dispose()
        try:
            result = persist_lyric_staging(engine, summary, records, texts)
            database_state = "persisted_pending_review"
        except OperationalError as error:
            result = local_result
            database_state = "pending_database"
            report(
                "database_temporarily_unavailable_local_staging_preserved",
                error_type=type(error).__name__,
            )
        publish_status(
            args.state / f"staging-{phase}.json",
            {
                **result,
                **summary,
                "database_state": database_state,
                "local_staging_run_id": local_result["run_id"],
            },
        )

    try:
        stage("initial")
        deadline = datetime.now(UTC) + timedelta(hours=args.hours)
        with httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "ChartObservatory/0.1 public lyric recovery"},
        ) as client:
            http = PacedHTTP(
                args.store / "http-cache",
                client,
                interval=1.5,
                cache_sources=[ROOT / "data/derived/lyrics/global-20261108/http-cache"],
                cooldown_path=ROOT
                / "data/derived/lyrics/quota-20261030/http-cache/provider-cooldowns.sqlite",
            )

            def acquire(payload):
                try:
                    http.start_trace()
                    return recover_with_fallback(
                        payload["title"],
                        payload["artist"],
                        http,
                        first_time=True,
                        metadata_resolution=payload.get("metadata_resolution"),
                    )
                except (httpx.RequestError, ValueError) as error:
                    return dict(status="retrieval_error", error_type=type(error).__name__)

            pending = iter(delta)
            examined = sum(store.summary().values()) - store.summary().get("pending", 0)
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                inflight, exhausted = {}, False
                while inflight or not exhausted:
                    while len(inflight) < args.workers and not exhausted:
                        if datetime.now(UTC) >= deadline:
                            exhausted = True
                            break
                        payload = next(pending, None)
                        if payload is None:
                            exhausted = True
                        elif store.claim(payload["recording_id"]):
                            inflight[executor.submit(acquire, payload)] = payload["recording_id"]
                    if not inflight:
                        break
                    done, _ = wait(inflight, timeout=30, return_when=FIRST_COMPLETED)
                    for future in done:
                        store.finish(inflight.pop(future), future.result())
                        examined += 1
                        if examined % 50 == 0:
                            stage(f"checkpoint-{examined:04d}")
                    report(
                        "recovering_delta",
                        examined=examined,
                        total=len(delta),
                        states=store.summary(),
                        inflight=len(inflight),
                        workers=args.workers,
                    )
        stage("recovered")
        records, _ = stage_records(targets, snapshot, store)
        coverage = {}
        for r in records:
            for b in r["payload"]["chart_bindings"]:
                count = coverage.setdefault((b["country_code"], b["year"]), Counter())
                count["known_positions"] += 1
                count["positions_with_text"] += bool(r["text_sha256"])
        weighted = dict(
            known_positions=len(members),
            positions_with_text=sum(c["positions_with_text"] for c in coverage.values()),
            cells=[dict(country_code=k[0], year=k[1], **v) for k, v in sorted(coverage.items())],
            scientifically_approved_positions=0,
            classification_ready=False,
        )
        publish_status(args.state / "weighted-availability-recovered.json", weighted)
        publish_status(
            args.state / "outcome.json",
            dict(
                acquisition_states=store.summary(),
                validation_candidates=len(queue),
                delta_candidates=len(delta),
                low_initial_availability_cells=len(low),
                pending_review=True,
                paid_calls=0,
                approvals=0,
            ),
        )
        report(
            "finished_pending_reviews",
            states=store.summary(),
            validation_candidates=len(queue),
            low_availability_cells=len(low),
        )
    finally:
        engine.dispose()
        store.conn.close()
        # Only this worker owns the provider slot; restart the original comparator
        # after acquisition even when staging/network processing fails.
        report("resuming_comparison_after_delta")
        subprocess.Popen(
            [
                sys.executable,
                "scripts/compare_all_lyrics_web.py",
                "--state-root",
                str(args.resume_comparison),
                "--base-root",
                str(ROOT / "data/derived/annual_revision/global-2018-2026-20261108"),
                "--store-root",
                str(ROOT / "data/derived/lyrics/global-20261108"),
                "--hours",
                "24",
            ],
            cwd=ROOT,
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=(args.state / "comparison-stdout.log").open("ab"),
            stderr=(args.state / "comparison-stderr.log").open("ab"),
        )


if __name__ == "__main__":
    main()
