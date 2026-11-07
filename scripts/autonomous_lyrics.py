"""Continuous bounded recovery of quota-selected lyrics, including labeled provisional cells."""

import argparse
import csv
import hashlib
import json
import msvcrt
import os
import subprocess
import sys
import time
import traceback
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path

import httpx
import polars as pl
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

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
from chart_observatory.lyrics.quota_acquisition import (
    AcquisitionStore,
    PacedHTTP,
    ranking_recovery_priority,
    reconcile_reindexed_task,
    reconcile_task_metadata,
)
from chart_observatory.lyrics.quota_acquisition import candidate as lyric_candidate
from chart_observatory.lyrics.quota_acquisition import identity as identity_key
from chart_observatory.lyrics.quota_discovery import (
    PublicBrowser,
    audit_saved_result,
    recover_with_fallback,
    settle_metadata_reconciliation,
)
from chart_observatory.lyrics.quota_replay_import import import_cached_candidates
from chart_observatory.quota_campaign import remaining_seconds
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/autonomous-2018-2026-20261031"
STATE = ROOT / "data/runtime/autonomous-lyrics-20261031"
OUTPUT = ROOT / "data/derived/lyrics/quota-20261030"
RETRIEVAL_DOMAINS = ("lrclib.net", "genius.com", "www.azlyrics.com", "www.musixmatch.com")


def report(stage, **details):
    STATE.mkdir(parents=True, exist_ok=True)
    payload = dict(
        stage=stage,
        pid=os.getpid(),
        updated_at=datetime.now(UTC).isoformat(),
        years=[2018, 2026],
        cutoff="2026-10-15",
        paid_calls=0,
        **details,
    )
    publish_status(STATE / "status.json", payload)


def wait_for_database(timeout=120):
    """Let PostgreSQL finish crash recovery before preparing or modifying the queue."""
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1")).scalar_one()
                return
            except OperationalError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("research database did not become ready") from None
                report("waiting_for_database", retry_in_seconds=min(2, remaining))
                time.sleep(min(2, remaining))
    finally:
        engine.dispose()


def rows(path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def bundle():
    selection = BASE / "selection"
    command = [
        sys.executable,
        "scripts/prepare_quota_import.py",
        "--source",
        str(BASE / "sources"),
        "--output",
        str(selection),
        "--start-year",
        "2018",
        "--end-year",
        "2026",
        "--metadata-only-overflow",
        "--apply",
    ]
    if (selection / "manifest.json").exists():
        command.append("--prepared")
    subprocess.run(command, cwd=ROOT, check=True)
    final = [
        {**r, "selection_status": "CALENDAR_ELIGIBLE", "coverage_status": "COMPLETE"}
        for r in rows(selection / "selected.jsonl")
    ]
    with (BASE / "sources/source_coverage.csv").open(encoding="utf-8-sig") as handle:
        coverage = list(csv.DictReader(handle))
    rankings = pl.read_parquet(BASE / "sources/rankings.parquet").to_dicts()
    quotas = load_quotas(BASE / "sources/country_quotas.csv")
    provisional = provisional_selection(rankings, coverage, quotas, final)
    combined = final + provisional
    validate_quota_memberships(combined, quotas)
    validate_ranking_positions(combined, rankings)
    enrichment_path = BASE / "metadata-enrichment.json"
    if enrichment_path.exists():
        enrichment = json.loads(enrichment_path.read_text(encoding="utf-8")).get("resolved", {})
        for row in combined:
            value = enrichment.get(row["candidate_id"])
            if value and (not row.get("title") or not row.get("artist")):
                row["original_display_metadata"] = {k: row.get(k) for k in ("title", "artist")}
                for field in ("title", "artist"):
                    if not row.get(field):
                        row[field] = value[field]
                row["metadata_resolution"] = value
    display_path = BASE / "native-display-metadata.json"
    if display_path.exists():
        apply_native_display_metadata(
            combined, json.loads(display_path.read_text(encoding="utf-8"))
        )
    for name, data in (("provisional", provisional), ("combined", combined)):
        with (BASE / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for row in data:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    tasks = recovery_targets(combined)
    native_path = BASE / "youtube-native-evidence/native-identity-map.jsonl"
    if native_path.exists():
        native = {row["candidate_id"]: row for row in rows(native_path)}
        native_hash = hashlib.sha256(native_path.read_bytes()).hexdigest()
        for task in tasks:
            proof = native.get(task["recording_id"])
            if proof:
                task["chart_video_evidence"] = {
                    key: proof[key]
                    for key in (
                        "video_ids",
                        "expected_source_rows",
                        "verified_source_rows",
                        "all_source_rows_verified",
                        "identity_scope",
                    )
                }
                task["chart_video_evidence"].update(
                    evidence_file=str(native_path),
                    evidence_sha256=native_hash,
                    recording_validated=False,
                    lyrics_validated=False,
                )
    summary = dict(
        definitive_memberships=len(final),
        provisional_memberships=len(provisional),
        unique_candidates=len(tasks),
        country_year_cells=68 * 9,
        quotas_sum_per_year=sum(quotas.values()),
        provisional_not_an_annual_ranking=True,
    )
    (BASE / "combined-manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return tasks, summary


def refresh_native_metadata(store, wanted, path):
    raw = path.read_bytes()
    resolutions = json.loads(raw)
    payloads, displays = {}, []
    for key, payload in store.conn.execute("SELECT identity,payload FROM tasks").fetchall():
        if key in wanted and key in resolutions:
            value = json.loads(payload)
            payloads[key] = value
            displays.append(
                dict(candidate_id=key, title=value.get("title"), artist=value.get("artist"))
            )
    apply_native_display_metadata(displays, resolutions)
    updates, changed = [], 0
    for display in displays:
        key = display["candidate_id"]
        before = payloads[key]
        after = reconcile_task_metadata(before, display)
        changed += any(
            identity_key(before.get(field)) != identity_key(after.get(field))
            for field in ("title", "artist")
        )
        if before != after:
            updates.append((json.dumps(after, ensure_ascii=False), key))
    with store.conn:
        store.conn.executemany("UPDATE tasks SET payload=? WHERE identity=?", updates)
    return dict(
        signature=hashlib.sha256(raw).hexdigest(),
        updated_payloads=len(updates),
        changed_names=changed,
    )


def refresh_pending_native_metadata(store, wanted, path, pending):
    """Called only with drained futures under the acquisition owner lock."""
    refreshed = refresh_native_metadata(store, wanted, path)
    keys = {item[0] for item in pending}
    current = {
        key: (json.loads(payload), state, result)
        for key, payload, state, result in store.conn.execute(
            "SELECT identity,payload,status,result FROM tasks"
        ).fetchall()
        if key in keys
    }
    updated = []
    changed = 0
    for key, payload, _state, _result in pending:
        new_payload, new_state, new_result = current[key]
        changed += payload != new_payload
        updated.append((key, new_payload, new_state, new_result))
    return updated, {**refreshed, "updated_queued_candidates": changed}


def filter_targeted_candidates(targets, path):
    raw = Path(path).read_bytes()
    requested = {
        json.loads(line)["candidate_id"]
        for line in raw.decode("utf-8").splitlines()
        if line.strip()
    }
    available = {row["recording_id"] for row in targets}
    if not requested or not requested <= available:
        raise ValueError("targeted candidate IDs must be nonempty and within current selection")
    return [row for row in targets if row["recording_id"] in requested], hashlib.sha256(
        raw
    ).hexdigest()


def main(
    hours=8,
    method_prefix="exact-discovery-v2",
    wait_pid=None,
    candidate_ids_file=None,
    rounds=3,
    search_cache_max_age_hours=None,
):
    STATE.mkdir(parents=True, exist_ok=True)
    if wait_pid:
        import ctypes

        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        dependency = kernel.OpenProcess(0x100000, False, wait_pid)
        if dependency:
            try:
                report("waiting_for_previous_owner", dependency_pid=wait_pid)
                while True:
                    outcome = kernel.WaitForSingleObject(dependency, 15000)
                    if outcome == 0:
                        break
                    if outcome != 258:
                        raise OSError("unable to verify previous owner termination")
                    report("waiting_for_previous_owner", dependency_pid=wait_pid)
            finally:
                kernel.CloseHandle(dependency)
        elif kernel.GetLastError() != 87:
            raise OSError("unable to open previous owner process handle")
    lock_path = ROOT / "data/runtime/quota-lyrics-20261030/owner.lock"
    with lock_path.open("r+b") as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            wait_for_database()
            report("preparing_selection")
            targets, summary = bundle()
            if candidate_ids_file:
                targets, filter_hash = filter_targeted_candidates(targets, candidate_ids_file)
                summary = dict(
                    summary, scoped_candidates=len(targets), candidate_filter_sha256=filter_hash
                )
            store = AcquisitionStore(OUTPUT)
            store.conn.executescript("""
                CREATE TABLE IF NOT EXISTS recovery_attempts(
                    identity TEXT, method TEXT, state TEXT NOT NULL,
                    previous_result TEXT, result TEXT,
                    PRIMARY KEY(identity,method));
                CREATE TABLE IF NOT EXISTS evidence_audits(
                    identity TEXT PRIMARY KEY, audit TEXT NOT NULL);
            """)
            # No previous writer owns the shared lock. Preserve interrupted tasks,
            # then reconcile via a different discovery method and the response cache.
            with store.conn:
                store.conn.execute(
                    "UPDATE tasks SET status='interrupted_pending_review' WHERE status='running'"
                )
            wanted = set()
            for indexed, task in enumerate(targets, 1):
                key = task["recording_id"]
                wanted.add(key)
                previous = store.conn.execute(
                    "SELECT payload FROM tasks WHERE identity=?", (key,)
                ).fetchone()
                if previous:
                    before = json.loads(previous[0])
                    task = reconcile_reindexed_task(before, task)
                store.enqueue(key, task)
                with store.conn:
                    store.conn.execute(
                        "UPDATE tasks SET payload=? WHERE identity=?",
                        (json.dumps(task, ensure_ascii=False), key),
                    )
                if indexed % 500 == 0:
                    report("indexing_queue", indexed=indexed, total=len(targets), selection=summary)
            store.set_scope(wanted)
            report("importing_offline_candidates", selection=summary)
            imported_offline = import_cached_candidates(
                store,
                wanted,
                OUTPUT / "offline-replay",
                progress=lambda counts: report(
                    "importing_offline_candidates", selection=summary, **counts
                ),
            )
            publish_status(
                STATE / "offline-import.json",
                dict(**imported_offline, observed_at=datetime.now(UTC).isoformat(), paid_calls=0),
            )
            report("imported_offline_candidates", selection=summary, **imported_offline)
            # Reconcile newly added provisional identities with the existing
            # library before any provider request, just as for the original set.
            from acquire_quota_lyrics import local_documents

            from chart_observatory.lyrics.identity_quarantine import load_suspended_sources
            from chart_observatory.lyrics.repository import AUTHORIZED_RIGHTS

            pending_targets = {
                key: json.loads(payload)
                for key, payload in store.conn.execute(
                    "SELECT identity,payload FROM tasks WHERE status='pending'"
                )
                if key in wanted
            }
            if pending_targets:
                report(
                    "reconciling_new_candidates", candidates=len(pending_targets), selection=summary
                )
                mappings, documents = local_documents(pending_targets)
                suspended = load_suspended_sources()
                quarantine = json.loads(
                    (ROOT / "config/lyrics_identity_quarantine.json").read_text(encoding="utf-8")
                )
                blocked = {
                    r["lyric_document_id"]
                    for r in quarantine["entries"]
                    if r.get("decision") != "confirmed_match"
                }
                for key in pending_targets:
                    matches = list(documents.get("candidate:" + key, []))
                    known = mappings.get(key, set())
                    if len(known) == 1:
                        matches.extend(documents.get(next(iter(known)), []))
                    for doc in matches:
                        if (
                            doc["source"].upper() in suspended
                            or str(doc["document_id"]) in blocked
                            or doc["rights_status"] not in AUTHORIZED_RIGHTS
                            or hashlib.sha256(doc["text"].encode()).hexdigest()
                            != doc["content_sha256"]
                        ):
                            continue
                        value = lyric_candidate(
                            doc["text"], doc["source"], existing_document_id=str(doc["document_id"])
                        )
                        if value and not value["text_quality_flags"] and store.claim(key):
                            value["identity_check"] = (
                                "cached_exact_metadata_not_recording_validation"
                            )
                            store.finish(key, {**value, "status": "reused_pending_validation"})
                            break
            deadline = time.monotonic() + hours * 3600
            remaining = remaining_seconds()
            if remaining is not None:
                deadline = min(deadline, time.monotonic() + remaining)
            browser = PublicBrowser(maximum_pages=200)
            with httpx.Client(
                timeout=20,
                follow_redirects=True,
                headers={"User-Agent": "ChartObservatory/0.1 lyrics research"},
            ) as client:
                quality_root = ROOT / "data/derived/research_quality"
                old_caches = list(quality_root.glob("corpus-revision-*/*/http-cache"))
                old_caches.extend(quality_root.glob("recovery-expanded-*/http-cache"))
                old_caches.extend(
                    (ROOT / "data/derived/annual_revision").glob("*/acquisition/http-cache")
                )
                cache = OUTPUT / "http-cache"
                if search_cache_max_age_hours is not None:
                    # Refresh only old discovery responses in an isolated cache;
                    # preserve raw evidence and share all existing provider pauses.
                    old_caches.insert(0, cache)
                    cache = STATE / "http-cache"
                http = PacedHTTP(
                    cache,
                    client,
                    cache_sources=old_caches,
                    search_cache_max_age_seconds=(
                        search_cache_max_age_hours * 3600
                        if search_cache_max_age_hours is not None
                        else None
                    ),
                    cooldown_path=OUTPUT / "http-cache/provider-cooldowns.sqlite",
                )
                native_signature = None
                for round_number in range(1, rounds + 1):
                    display_path = BASE / "native-display-metadata.json"
                    if (
                        display_path.exists()
                        and hashlib.sha256(display_path.read_bytes()).hexdigest()
                        != native_signature
                    ):
                        refreshed = refresh_native_metadata(store, wanted, display_path)
                        native_signature = refreshed["signature"]
                        report(
                            "native_metadata_refreshed",
                            round=round_number,
                            selection=summary,
                            counters=store.summary(),
                            **refreshed,
                        )
                    report(
                        "auditing_saved_results",
                        round=round_number,
                        selection=summary,
                        counters=store.summary(),
                    )
                    method = f"{method_prefix}-round{round_number}"
                    collision_file = OUTPUT / "identity-audit/repair-targets.jsonl"
                    suspicious = (
                        {r["identity"]: r["text_sha256"] for r in rows(collision_file)}
                        if collision_file.exists()
                        else {}
                    )
                    shared_collision_file = (
                        OUTPUT / "identity-audit/shared-text-repair-targets.jsonl"
                    )
                    if shared_collision_file.exists():
                        suspicious.update(
                            {
                                row["identity"]: row["text_sha256"]
                                for row in rows(shared_collision_file)
                            }
                        )
                    pending = []
                    for key, raw_payload, state, raw_result in store.conn.execute(
                        "SELECT identity,payload,status,result FROM tasks"
                    ).fetchall():
                        if key not in wanted:
                            continue
                        payload = json.loads(raw_payload)
                        result = json.loads(raw_result) if raw_result else {}
                        if result.get("text_path"):
                            audit = audit_saved_result(payload, result)
                            collision = suspicious.get(key) == result.get("text_sha256")
                            if collision:
                                audit["shared_text_identity_collision"] = True
                            if payload.get("requires_metadata_reconciliation"):
                                audit["ranking_metadata_changed"] = True
                            with store.conn:
                                store.conn.execute(
                                    "INSERT OR REPLACE INTO evidence_audits VALUES (?,?)",
                                    (key, json.dumps(audit, ensure_ascii=False)),
                                )
                            if (
                                not audit["source_quarantined"]
                                and not audit["text_quality_flags"]
                                and not collision
                                and not payload.get("requires_metadata_reconciliation")
                            ):
                                continue
                        if round_number > 1:
                            last = store.conn.execute(
                                "SELECT result FROM recovery_attempts "
                                "WHERE identity=? AND method=?",
                                (key, f"{method_prefix}-round{round_number - 1}"),
                            ).fetchone()
                            errors = (
                                json.loads(last[0]).get("source_errors", [])
                                if last and last[0]
                                else []
                            )
                            if not payload.get("requires_metadata_reconciliation") and not any(
                                any(
                                    code in str(error)
                                    for code in (
                                        ":429",
                                        ":500",
                                        ":502",
                                        ":503",
                                        ":504",
                                        "Timeout",
                                        "Connect",
                                    )
                                )
                                for error in errors
                            ):
                                continue
                        if store.conn.execute(
                            "SELECT 1 FROM recovery_attempts WHERE identity=? AND method=?",
                            (key, method),
                        ).fetchone():
                            continue
                        pending.append((key, payload, state, raw_result))
                    pending.sort(
                        key=lambda item: (
                            item[0] not in suspicious,
                            not item[1].get("requires_metadata_reconciliation", False),
                            item[2] != "pending",
                            ranking_recovery_priority(item[1]),
                            item[0],
                        )
                    )
                    if not pending or time.monotonic() >= deadline:
                        break
                    if round_number > 1:
                        report(
                            "waiting_provider_cooldown",
                            round=round_number,
                            candidates=len(pending),
                            counters=store.summary(),
                            selection=summary,
                        )
                        for _ in range(60):
                            if time.monotonic() >= deadline:
                                break
                            time.sleep(15)

                    def acquire(payload, first_time):
                        try:
                            return recover_with_fallback(
                                payload["title"],
                                payload["artist"],
                                http,
                                first_time=first_time,
                                browser=browser,
                                metadata_resolution=payload.get("metadata_resolution"),
                            )
                        except Exception as exc:
                            return dict(
                                status="error_pending_review",
                                error_type=type(exc).__name__,
                                error_frames=[
                                    f"{Path(f.filename).name}:{f.lineno}:{f.name}"
                                    for f in traceback.extract_tb(exc.__traceback__)
                                ],
                            )

                    pending_queue, active = deque(pending), {}
                    metadata_check_at = time.monotonic() + 60
                    with ThreadPoolExecutor(6) as pool:
                        while time.monotonic() < deadline or active:
                            if not active and time.monotonic() >= metadata_check_at:
                                metadata_check_at = time.monotonic() + 60
                                if (
                                    display_path.exists()
                                    and hashlib.sha256(display_path.read_bytes()).hexdigest()
                                    != native_signature
                                ):
                                    refreshed_pending, refreshed = refresh_pending_native_metadata(
                                        store, wanted, display_path, pending_queue
                                    )
                                    pending_queue = deque(refreshed_pending)
                                    native_signature = refreshed["signature"]
                                    report(
                                        "native_metadata_refreshed_at_queue_boundary",
                                        round=round_number,
                                        selection=summary,
                                        counters=store.summary(),
                                        **refreshed,
                                    )
                            while pending_queue and len(active) < 6 and time.monotonic() < deadline:
                                if http.search_retry_delay(RETRIEVAL_DOMAINS) > 0:
                                    break
                                item = pending_queue.popleft()
                                key, payload, previous_state, previous_result = item
                                with store.conn:
                                    store.conn.execute(
                                        "INSERT INTO recovery_attempts VALUES "
                                        "(?,?,'reserved',?,NULL)",
                                        (key, method, previous_result),
                                    )
                                    store.conn.execute(
                                        "UPDATE tasks SET status='running' WHERE identity=?", (key,)
                                    )
                                active[
                                    pool.submit(
                                        acquire,
                                        payload,
                                        previous_state == "pending"
                                        or not (
                                            json.loads(previous_result) if previous_result else {}
                                        ).get("text_path"),
                                    )
                                ] = item
                            if not active:
                                if pending_queue and time.monotonic() < deadline:
                                    delay = http.search_retry_delay(RETRIEVAL_DOMAINS)
                                    if delay > 0:
                                        report(
                                            "waiting_provider_cooldown",
                                            round=round_number,
                                            candidates=len(pending_queue),
                                            retry_in_seconds=round(delay, 1),
                                            provider_retry_in_seconds=http.provider_retry_delays(),
                                            counters=store.summary(),
                                            selection=summary,
                                        )
                                        time.sleep(
                                            max(0, min(15, delay, deadline - time.monotonic()))
                                        )
                                        continue
                                break
                            done, _ = wait(active, timeout=15, return_when=FIRST_COMPLETED)
                            for future in done:
                                key, payload, previous_state, previous_result = active.pop(future)
                                result = future.result()
                                old = json.loads(previous_result) if previous_result else {}
                                if result.get("text") or not old.get("text_path"):
                                    store.finish(key, result)
                                else:
                                    with store.conn:
                                        store.conn.execute(
                                            "UPDATE tasks SET status=?,result=? WHERE identity=?",
                                            (previous_state, previous_result, key),
                                        )
                                reconciled_payload = settle_metadata_reconciliation(payload, result)
                                if reconciled_payload != payload:
                                    payload = reconciled_payload
                                    with store.conn:
                                        store.conn.execute(
                                            "UPDATE tasks SET payload=? WHERE identity=?",
                                            (json.dumps(payload, ensure_ascii=False), key),
                                        )
                                record = {k: v for k, v in result.items() if k != "text"}
                                with store.conn:
                                    store.conn.execute(
                                        "UPDATE recovery_attempts SET state='finished',"
                                        "result=? WHERE identity=? AND method=?",
                                        (json.dumps(record, ensure_ascii=False), key, method),
                                    )
                                    audit = audit_saved_result(
                                        payload, result if result.get("text") else old
                                    )
                                    store.conn.execute(
                                        "INSERT OR REPLACE INTO evidence_audits VALUES (?,?)",
                                        (key, json.dumps(audit, ensure_ascii=False)),
                                    )
                            report(
                                "recovering",
                                round=round_number,
                                counters=store.summary(),
                                selection=summary,
                                browser_pages=browser.pages,
                            )
            report("staging_postgres_snapshot", counters=store.summary(), selection=summary)
            staged = subprocess.run(
                [sys.executable, "scripts/stage_quota_lyrics.py", "--base-root", str(BASE)],
                cwd=ROOT,
                check=False,
            )
            report(
                "finished_with_pending_reviews"
                if staged.returncode == 0
                else "finished_with_staging_error",
                counters=store.summary(),
                selection=summary,
                browser_pages=browser.pages,
                classification_ready=False,
                postgres_staging_returncode=staged.returncode,
            )
            store.conn.close()
        except Exception as exc:
            report("failed", error_type=type(exc).__name__)
            raise
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=float, default=8)
    parser.add_argument("--method-prefix", default="exact-discovery-v2")
    parser.add_argument("--wait-pid", type=int)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--base-root", type=Path)
    parser.add_argument("--candidate-ids-file", type=Path)
    parser.add_argument("--search-cache-max-age-hours", type=float)
    parser.add_argument("--rounds", type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    if not 0 < args.hours <= 24:
        parser.error("hours must be in (0,24]")
    if args.search_cache_max_age_hours is not None and args.search_cache_max_age_hours <= 0:
        parser.error("search cache age must be positive")
    if args.state_root:
        STATE = args.state_root.resolve()
    if args.base_root:
        BASE = args.base_root.resolve()
    main(
        args.hours,
        args.method_prefix,
        args.wait_pid,
        args.candidate_ids_file,
        args.rounds,
        args.search_cache_max_age_hours,
    )
