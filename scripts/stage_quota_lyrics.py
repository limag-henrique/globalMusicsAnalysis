"""Import an immutable pending-review snapshot into the project's PostgreSQL database."""

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("POLARS_MAX_THREADS", "2")
import polars as pl
from sqlalchemy import create_engine, func, select

from chart_observatory.config import Settings
from chart_observatory.ingestion.import_quotas import (
    apply_native_display_metadata,
    load_quotas,
    provisional_selection,
    recovery_targets,
)
from chart_observatory.ingestion.quota_boundary import (
    validate_quota_memberships,
    validate_ranking_positions,
)
from chart_observatory.lyrics.identity_collisions import flag_shared_text_identities
from chart_observatory.lyrics.quota_acquisition import identity
from chart_observatory.lyrics.quota_discovery import (
    audit_saved_result,
    usable_cached_repair,
    usable_cached_replay,
)
from chart_observatory.lyrics.quota_staging import blobs, candidates, persist_lyric_staging
from chart_observatory.lyrics.text_quality import prepare_lyric_derivative
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data/derived/lyrics/quota-20261030"
STATE = ROOT / "data/runtime/postgres-lyric-staging-20261031"


def report(stage, **details):
    STATE.mkdir(exist_ok=True)
    publish_status(
        STATE / "status.json",
        {
            **details,
            "stage": stage,
            "pid": os.getpid(),
            "updated_at": datetime.now(UTC).isoformat(),
            "paid_calls": 0,
            "classification_ready": False,
        },
    )


def stage(base):
    report("verifying_immutable_selection")
    manifest_path = base / "selection/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for folder, hashes in (
        ("sources", manifest["source_hashes"]),
        ("selection", manifest["output_hashes"]),
    ):
        for name, expected in hashes.items():
            with (base / folder / name).open("rb") as handle:
                if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                    raise ValueError("immutable selection/source hash mismatch")
    selected = [
        {**json.loads(line), "selection_status": "CALENDAR_ELIGIBLE", "coverage_status": "COMPLETE"}
        for line in (base / "selection/selected.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    with (base / "sources/source_coverage.csv").open(encoding="utf-8-sig") as handle:
        coverage = list(csv.DictReader(handle))
    rankings = pl.read_parquet(base / "sources/rankings.parquet").to_dicts()
    selected += provisional_selection(
        rankings, coverage, load_quotas(base / "sources/country_quotas.csv"), selected
    )
    validate_quota_memberships(selected, load_quotas(base / "sources/country_quotas.csv"))
    validate_ranking_positions(selected, rankings)
    enrichment = json.loads((base / "metadata-enrichment.json").read_text(encoding="utf-8"))[
        "resolved"
    ]
    for row in selected:
        if metadata := enrichment.get(row["candidate_id"]):
            for field in ("title", "artist"):
                if not row.get(field):
                    row[field] = metadata[field]
            row["metadata_resolution"] = metadata
    display = base / "native-display-metadata.json"
    display_signature = None
    if display.exists():
        raw = display.read_bytes()
        display_signature = hashlib.sha256(raw).hexdigest()
        apply_native_display_metadata(selected, json.loads(raw))
    payloads = recovery_targets(selected)
    with sqlite3.connect(
        f"file:{(STORE / 'acquisition.sqlite').as_posix()}?mode=ro", uri=True
    ) as conn:
        acquired = {
            key: (json.loads(payload), status, json.loads(result) if result else {})
            for key, payload, status, result in conn.execute(
                "SELECT identity,payload,status,result FROM tasks"
            )
        }
    offline = defaultdict(list)
    for path in sorted((STORE / "offline-replay").glob("*.json")):
        raw = path.read_bytes()
        replay = json.loads(raw)
        offline[replay["payload"]["recording_id"]].append(
            (path, hashlib.sha256(raw).hexdigest(), replay)
        )
    records, texts = [], {}
    overlay_count, overlay_conflicts, repair_count = 0, 0, 0
    for index, payload in enumerate(payloads, 1):
        key = payload["recording_id"]
        previous, status, result = acquired.get(key, ({}, "not_enqueued", {}))
        options = {}
        for path, evidence_hash, replay in offline.get(key, []):
            accepted = usable_cached_replay(payload, result, replay) or usable_cached_repair(
                payload, result, replay
            )
            if accepted:
                digest = hashlib.sha256(accepted["text"].encode()).hexdigest()
                options[digest] = path, evidence_hash, replay, accepted
        conflict = len(options) > 1
        if len(options) == 1:
            digest, (path, evidence_hash, replay, accepted) = next(iter(options.items()))
            previous_result = None
            if result.get("text_sha256"):
                old_raw = Path(result["text_path"]).read_bytes()
                if hashlib.sha256(old_raw).hexdigest() != result["text_sha256"]:
                    raise ValueError("previous repair candidate hash mismatch")
                previous_result = dict(result)
                repair_count += 1
            texts[digest] = accepted["text"]
            previous, status = replay["payload"], "candidate_pending_validation"
            result = {key: value for key, value in accepted.items() if key != "text"}
            result.update(
                text_sha256=digest,
                offline_replay_evidence_file=str(path),
                offline_replay_evidence_sha256=evidence_hash,
            )
            if previous_result:
                result["replaced_unverified_result"] = previous_result
            overlay_count += 1
        if conflict:
            overlay_conflicts += 1
            result = {
                **result,
                "conflicting_offline_alternatives": [
                    dict(
                        candidate_id=key,
                        text_sha256=option_digest,
                        source=option[3]["source"],
                        replay_evidence_file=str(option[0]),
                        replay_evidence_sha256=option[1],
                    )
                    for option_digest, option in sorted(options.items())
                ],
            }
        audit = audit_saved_result(payload, result)
        if conflict:
            audit["text_quality_flags"].append("conflicting_offline_replays")
        if any(
            identity(previous.get(field)) != identity(payload.get(field))
            for field in ("title", "artist")
        ):
            audit["text_quality_flags"].append("retrieval_metadata_requires_reconciliation")
        digest = result.get("text_sha256")
        if digest:
            if digest not in texts:
                raw = Path(result["text_path"]).read_bytes()
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise ValueError("lyric blob hash mismatch; staging transaction not started")
                texts[digest] = raw.decode("utf-8")
            quality = prepare_lyric_derivative(texts[digest], result.get("source", "UNKNOWN"))
            audit["text_quality_flags"] = sorted(
                set(audit["text_quality_flags"]) | set(quality.flags)
            )
            audit["text_quality_version"] = quality.version
        records.append(
            dict(
                candidate_id=key,
                text_sha256=digest,
                acquisition_status=status,
                payload=payload,
                source_result=result,
                audit=audit,
            )
        )
        if index % 250 == 0:
            report(
                "verifying_lyric_blobs",
                candidates=index,
                total=len(payloads),
                unique_texts=len(texts),
            )
    flag_shared_text_identities(records)
    source = dict(
        selection_root=str(base),
        selection_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        display_metadata_sha256=display_signature,
        candidates=len(records),
        memberships=len(selected),
        text_candidates=sum(bool(r["text_sha256"]) for r in records),
        unique_texts=len(texts),
        offline_cache_candidates=overlay_count,
        offline_cache_repairs=repair_count,
        repaired_candidates=sum(
            bool(record["source_result"].get("replaced_unverified_result")) for record in records
        ),
        conflicting_offline_candidates=overlay_conflicts,
        state="pending_identity_integrity_and_rights_review",
        ranking_metric_basis="sum_observed_chart_metrics",
    )
    report("persisting_pending_snapshot", **source)
    engine = create_engine(Settings.load(ROOT).database_url)
    try:
        persisted = persist_lyric_staging(engine, source, records, texts)
        with engine.connect() as conn:
            count = conn.execute(
                select(func.count())
                .select_from(candidates)
                .where(candidates.c.run_id == persisted["run_id"])
            ).scalar_one()
            ready = conn.execute(
                select(func.count())
                .select_from(candidates)
                .where(
                    candidates.c.run_id == persisted["run_id"], candidates.c.classification_ready
                )
            ).scalar_one()
            stored_texts = conn.execute(select(func.count()).select_from(blobs)).scalar_one()
        if count != len(records) or ready:
            raise ValueError("staged snapshot verification failed")
        report(
            "staged_pending_review",
            **persisted,
            verified_candidates=count,
            paid_ready_candidates=ready,
            total_deduplicated_blobs=stored_texts,
        )
        return persisted
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, help="Separate status directory for this snapshot")
    args = parser.parse_args()
    if args.state_root:
        STATE = args.state_root.resolve()
    import msvcrt

    STATE.mkdir(exist_ok=True)
    with (STATE / "owner.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        while True:
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(5)
        try:
            print(json.dumps(stage(args.base_root.resolve())))
        except Exception as exc:
            report("failed", error_type=type(exc).__name__)
            raise
