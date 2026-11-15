"""Recover missing texts in deficient country/year cells from immutable staging.

Availability is reported separately from identity/completeness approval. Existing
texts are never replaced and every result retains its exact candidate bindings.
"""

import argparse
import hashlib
import json
import msvcrt
import os
import sqlite3
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from chart_observatory.config import Settings
from chart_observatory.ingestion.import_quotas import recovery_targets
from chart_observatory.lyrics.identity_collisions import flag_shared_text_identities
from chart_observatory.lyrics.quota_acquisition import (
    AcquisitionStore,
    PacedHTTP,
    identity,
    recovery_cache_sources,
)
from chart_observatory.lyrics.quota_discovery import audit_saved_result, recover_with_fallback
from chart_observatory.lyrics.quota_staging import persist_lyric_staging
from chart_observatory.research_flow import load_selection
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]


def load_baseline(path, run_id):
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("source staging failed integrity check")
        rows = db.execute(
            "SELECT c.candidate_id,c.payload,c.source_result,c.audit,c.acquisition_status,"
            "c.text_sha256,b.body FROM quota_lyric_staging_candidates c "
            "LEFT JOIN quota_lyric_staging_blobs b ON c.text_sha256=b.sha256 WHERE c.run_id=?",
            (run_id,),
        )
        records, texts = {}, {}
        for key, payload, result, audit, status, digest, body in rows:
            if digest:
                if not isinstance(body, str) or hashlib.sha256(body.encode()).hexdigest() != digest:
                    raise ValueError("baseline text hash mismatch")
                texts[digest] = body
            records[key] = dict(
                candidate_id=key,
                payload=json.loads(payload),
                source_result=json.loads(result),
                audit=json.loads(audit),
                acquisition_status=status,
                text_sha256=digest,
            )
        if not records:
            raise ValueError("source staging run was not found")
        return records, texts


def merged_records(baseline, baseline_texts, store):
    records, texts = [], dict(baseline_texts)
    for key, previous in baseline.items():
        current = previous
        if not previous["text_sha256"]:
            row = store.conn.execute(
                "SELECT payload,result,status FROM tasks WHERE identity=?", (key,)
            ).fetchone()
            if row and row[1]:
                payload, result = json.loads(row[0]), json.loads(row[1])
                if payload != previous["payload"]:
                    raise ValueError("acquisition payload differs from frozen candidate")
                digest = result.get("text_sha256")
                if digest:
                    body = Path(result["text_path"]).read_bytes().decode("utf-8")
                    if hashlib.sha256(body.encode()).hexdigest() != digest:
                        raise ValueError("recovered text hash mismatch")
                    texts[digest] = body
                    current = dict(
                        candidate_id=key,
                        payload=payload,
                        source_result=result,
                        audit=audit_saved_result(payload, result),
                        acquisition_status=row[2],
                        text_sha256=digest,
                    )
        records.append(current)
    flag_shared_text_identities(records)
    return records, texts


def availability(records):
    cells = {}
    for record in records:
        for binding in record["payload"]["chart_bindings"]:
            cell = cells.setdefault((binding["country_code"], binding["year"]), Counter())
            cell["known_positions"] += 1
            cell["positions_with_text"] += bool(record["text_sha256"])
    return cells


def deficient(cells):
    return {
        key: (value["known_positions"] * 4 + 4) // 5 - value["positions_with_text"]
        for key, value in cells.items()
        if value["positions_with_text"] * 5 < value["known_positions"] * 4
    }


def enrich_matching_proofs(baseline, proofs, evidence_file, evidence_hash):
    """Add duration only with an exact native URI and unchanged display identity."""
    enriched, conflicts = [], []
    for key, record in baseline.items():
        if record["text_sha256"] or key not in proofs:
            continue
        proof = proofs[key]
        metadata = proof.get("metadata") or {}
        native = key.removeprefix("SPOTIFY:")
        if (
            not key.startswith("SPOTIFY:")
            or proof.get("status") != 200
            or proof.get("source_url") != f"https://open.spotify.com/embed/track/{native}"
            or metadata.get("uri") != f"spotify:track:{native}"
        ):
            raise ValueError("native proof refers to another recording")
        if any(
            identity(record["payload"].get(field)) != identity(metadata.get(field))
            for field in ("title", "artist")
        ):
            conflicts.append(dict(candidate_id=key, frozen=record["payload"], proof=proof))
            continue
        duration = metadata.get("duration_ms")
        if isinstance(duration, int) and not isinstance(duration, bool) and duration > 0:
            record["payload"] = {
                **record["payload"],
                "metadata_resolution": dict(
                    basis="exact_native_uri_public_spotify_metadata",
                    evidence_file=str(evidence_file),
                    evidence_sha256=evidence_hash,
                    evidence_key=key,
                    uri=metadata["uri"],
                    duration_ms=duration,
                    recording_and_text_validation=False,
                ),
            }
            enriched.append(key)
    return enriched, conflicts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-staging", required=True, type=Path)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--prior-store", type=Path)
    parser.add_argument("--metadata-proofs", type=Path)
    parser.add_argument("--hours", type=float, default=8)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    args = parser.parse_args()
    for name in ("source_staging", "selection", "state", "store"):
        value = getattr(args, name).resolve()
        if not value.is_relative_to(ROOT):
            raise ValueError("all paths must remain inside this project")
        setattr(args, name, value)
    if not 0 < args.hours <= 24:
        raise ValueError("hours must be in (0,24]")
    args.state.mkdir(parents=True, exist_ok=True)
    args.store.mkdir(parents=True, exist_ok=True)
    loaded_source = Path(__file__).read_bytes()
    (args.state / "producer-loaded.py").write_bytes(loaded_source)
    owner = (args.store / "owner.lock").open("a+b")
    owner.seek(0)
    if not owner.read(1):
        owner.write(b"0")
        owner.flush()
    owner.seek(0)
    msvcrt.locking(owner.fileno(), msvcrt.LK_NBLCK, 1)
    manifest, _, members, hashes = load_selection(args.selection)
    baseline, baseline_texts = load_baseline(args.source_staging, args.source_run_id)
    expected = {p["recording_id"]: p for p in recovery_targets(members)}
    if set(expected) != set(baseline):
        raise ValueError("source staging differs from frozen selection candidate scope")
    for key, payload in expected.items():
        prior = baseline[key]["payload"]
        if prior["chart_bindings"] != payload["chart_bindings"] or any(
            identity(prior.get(field)) != identity(payload.get(field))
            for field in ("title", "artist")
        ):
            raise ValueError("source staging bindings or identity differ from selection")
    prior_store_info = {}
    if args.prior_store:
        prior_path = args.prior_store.resolve()
        if not prior_path.is_relative_to(ROOT):
            raise ValueError("prior acquisition store outside project")
        prior = AcquisitionStore(prior_path)
        try:
            current, baseline_texts = merged_records(baseline, baseline_texts, prior)
            baseline = {r["candidate_id"]: r for r in current}
            prior_store_info = dict(
                prior_store=str(prior_path),
                prior_acquisition_sha256=hashlib.sha256(
                    (prior_path / "acquisition.sqlite").read_bytes()
                ).hexdigest(),
            )
        finally:
            prior.conn.close()
    native_info = {}
    if args.metadata_proofs:
        proof_path = args.metadata_proofs.resolve()
        if not proof_path.is_relative_to(ROOT):
            raise ValueError("metadata evidence outside project")
        raw = proof_path.read_bytes()
        proof_hash = hashlib.sha256(raw).hexdigest()
        enriched, conflicts = enrich_matching_proofs(
            baseline, json.loads(raw), proof_path, proof_hash
        )
        publish_status(
            args.state / "native-display-conflicts.json", {"items": conflicts, "approvals": 0}
        )
        native_info = dict(
            metadata_proof_file=str(proof_path),
            metadata_proof_sha256=proof_hash,
            metadata_enriched_candidates=len(enriched),
            display_conflict_candidates=len(conflicts),
        )
    store = AcquisitionStore(args.store)
    records, _ = merged_records(baseline, baseline_texts, store)
    cells = availability(records)
    low = deficient(cells)
    pending = [
        record["payload"]
        for record in records
        if not record["text_sha256"]
        and any((b["country_code"], b["year"]) in low for b in record["payload"]["chart_bindings"])
    ]
    pending.sort(
        key=lambda p: (
            not bool((p.get("metadata_resolution") or {}).get("duration_ms")),
            -sum((b["country_code"], b["year"]) in low for b in p["chart_bindings"]),
            min(b["position"] for b in p["chart_bindings"]),
            p["recording_id"],
        )
    )
    for payload in pending:
        store.enqueue(payload["recording_id"], payload)
    store.set_scope(p["recording_id"] for p in pending)
    with store.conn:
        store.conn.execute("UPDATE tasks SET status='pending' WHERE status='running'")
    input_info = dict(
        producer_sha256=hashlib.sha256(loaded_source).hexdigest(),
        acquisition_store=str(args.store),
        **native_info,
        **prior_store_info,
        source_staging=str(args.source_staging),
        source_staging_sha256=hashlib.sha256(args.source_staging.read_bytes()).hexdigest(),
        source_run_id=args.source_run_id,
        selection_root=str(args.selection),
        global_manifest_sha256=hashes[str(args.selection / "manifest.json")],
        memberships=manifest["memberships"],
        candidate_count=len(baseline),
        target_candidates=len(pending),
        initial_deficient_cells=len(low),
        initial_position_deficit=sum(low.values()),
        approvals=0,
        paid_calls=0,
    )
    publish_status(args.state / "campaign.json", input_info)
    pg = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})

    def report(stage):
        current, _ = merged_records(baseline, baseline_texts, store)
        coverage = availability(current)
        gaps = deficient(coverage)
        value = dict(
            stage=stage,
            pid=os.getpid(),
            updated_at=datetime.now(UTC).isoformat(),
            known_positions=sum(v["known_positions"] for v in coverage.values()),
            positions_with_text=sum(v["positions_with_text"] for v in coverage.values()),
            occupied_cells=len(coverage),
            cells_at_80_availability=len(coverage) - len(gaps),
            deficient_cells=len(gaps),
            position_deficit=sum(gaps.values()),
            acquisition_states=store.summary(),
            scientifically_approved_positions=0,
            approvals=0,
            paid_calls=0,
            classification_ready=False,
        )
        publish_status(args.state / "status.json", value)
        return value

    def stage(phase):
        current, texts = merged_records(baseline, baseline_texts, store)
        summary = {
            **input_info,
            "phase": phase,
            "text_candidates": sum(bool(r["text_sha256"]) for r in current),
        }
        local = create_engine("sqlite:///" + str(args.state / "pending-staging.sqlite"))
        try:
            saved = persist_lyric_staging(local, summary, current, texts)
        finally:
            local.dispose()
        try:
            database = persist_lyric_staging(pg, summary, current, texts)
        except OperationalError:
            database = {"state": "pending_database"}
        publish_status(
            args.state / f"staging-{phase}.json",
            {"local": saved, "database": database, "manifest": summary},
        )
        coverage = availability(current)
        publish_status(
            args.state / "weighted-availability.json",
            {
                **report(phase),
                "cells": [
                    dict(country_code=k[0], year=k[1], **v) for k, v in sorted(coverage.items())
                ],
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
                cache_sources=recovery_cache_sources(
                    ROOT, ROOT / "data/derived/lyrics/global-20261108/http-cache"
                ),
                cooldown_path=ROOT
                / "data/derived/lyrics/quota-20261030/http-cache/provider-cooldowns.sqlite",
            )

            def acquire(payload):
                http.start_trace()
                try:
                    return recover_with_fallback(
                        payload["title"],
                        payload["artist"],
                        http,
                        first_time=True,
                        metadata_resolution=payload.get("metadata_resolution"),
                    )
                except (httpx.RequestError, ValueError) as error:
                    return dict(status="retrieval_error", error_type=type(error).__name__)

            iterator = iter(pending)
            examined = sum(store.summary().values()) - store.summary().get("pending", 0)
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                inflight, exhausted = {}, False
                while inflight or not exhausted:
                    while len(inflight) < args.workers and not exhausted:
                        if datetime.now(UTC) >= deadline:
                            exhausted = True
                            break
                        payload = next(iterator, None)
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
                        if examined % 200 == 0:
                            stage(f"checkpoint-{examined:04d}")
                    report("recovering_missing_texts")
        stage("final")
        report(
            "completed_pending_reviews"
            if not store.summary().get("pending")
            else "paused_pending_acquisition"
        )
    except Exception as error:
        publish_status(
            args.state / "status.json",
            dict(
                stage="failed",
                pid=os.getpid(),
                updated_at=datetime.now(UTC).isoformat(),
                error_type=type(error).__name__,
                approvals=0,
                paid_calls=0,
                classification_ready=False,
            ),
        )
        raise
    finally:
        pg.dispose()
        store.conn.close()
        owner.close()


if __name__ == "__main__":
    main()
