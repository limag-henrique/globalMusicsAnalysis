"""Wait for annual import, reuse local lyrics, then acquire unique selected candidates."""

import json
import msvcrt
import os
import time
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.quota_acquisition import (
    AcquisitionStore,
    PacedHTTP,
    candidate,
    fetch_candidate,
    identity,
)

ROOT = Path(__file__).resolve().parents[1]
CHART_STATE = ROOT / "data/runtime/overnight-chart-import-20261030"
STATE = ROOT / "data/runtime/quota-lyrics-20261030"
OUTPUT = ROOT / "data/derived/lyrics/quota-20261030"


def status(stage, **details):
    STATE.mkdir(parents=True, exist_ok=True)
    part = STATE / "status.part"
    part.write_text(
        json.dumps(
            dict(
                stage=stage,
                pid=os.getpid(),
                observed_at=datetime.now(UTC).isoformat(),
                paid_calls=0,
                identity_validated=False,
                completeness_validated=False,
                **details,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    part.replace(STATE / "status.json")


def local_documents(targets):
    """Use exact platform links only, and keep ambiguous canonical mappings separate."""
    by_platform, mappings, docs = defaultdict(list), defaultdict(set), defaultdict(list)
    for key in targets:
        platform, _, native = key.partition(":")
        if platform in ("SPOTIFY", "YOUTUBE") and native and not native.startswith("T:"):
            by_platform[platform].append(native)
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            for platform, ids in by_platform.items():
                for offset in range(0, len(ids), 500):
                    rows = conn.execute(
                        text("""SELECT p.native_id, l.canonical_track_id,
                        t.title, d.source, d.text, d.content_sha256, d.id AS document_id,
                        d.rights_status FROM platform_items p JOIN platform_item_track_links l
                        ON l.platform_item_id=p.id JOIN canonical_tracks t
                        ON t.id=l.canonical_track_id LEFT JOIN lyric_documents d
                        ON d.canonical_track_id=t.id
                        WHERE p.platform_code=:platform AND p.native_id=ANY(:ids)"""),
                        dict(platform=platform, ids=ids[offset : offset + 500]),
                    ).mappings()
                    for row in rows:
                        key = f"{platform}:{row['native_id']}"
                        if identity(row["title"]) != identity(targets[key]["title"]):
                            continue
                        canonical = str(row["canonical_track_id"])
                        mappings[key].add(canonical)
                        if row["text"]:
                            docs[canonical].append(dict(row))
            # This recovered database has lyric documents but can lack platform
            # links. Exact title AND credited artist can reuse a cached candidate,
            # without asserting a canonical recording association.
            wanted = defaultdict(list)
            for key, target in targets.items():
                wanted[identity(target["title"]), identity(target["artist"])].append(key)
            matched = defaultdict(list)
            metadata = conn.execute(
                text("""SELECT t.id::text AS track_id, t.title,
                string_agg(a.name,' | ' ORDER BY a.name) AS artist FROM canonical_tracks t
                JOIN track_artists x ON x.track_id=t.id JOIN artists a ON a.id=x.artist_id
                GROUP BY t.id,t.title""")
            ).mappings()
            for row in metadata:
                keys = wanted.get((identity(row["title"]), identity(row["artist"])), [])
                if keys:
                    matched[row["track_id"]].extend(keys)
            ids = list(matched)
            for offset in range(0, len(ids), 300):
                rows = conn.execute(
                    text("""SELECT canonical_track_id::text AS track_id,
                    source,text,content_sha256,id AS document_id,rights_status
                    FROM lyric_documents
                    WHERE canonical_track_id=ANY(CAST(:ids AS uuid[]))"""),
                    dict(ids=ids[offset : offset + 300]),
                ).mappings()
                for row in rows:
                    if row["text"]:
                        document = dict(row)
                        document["metadata_only_cached_match"] = True
                        for key in matched[row["track_id"]]:
                            docs["candidate:" + key].append(document)
    finally:
        engine.dispose()
    return mappings, docs


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "owner.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            while True:
                result_path = CHART_STATE / "result.json"
                if result_path.exists():
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                    break
                chart = CHART_STATE / "status.json"
                current = json.loads(chart.read_text(encoding="utf-8")) if chart.exists() else {}
                if current.get("status") == "failed":
                    status("blocked_by_chart_failure", reason=current.get("error"))
                    return
                status("waiting_for_annual_import", chart_stage=current.get("stage"))
                time.sleep(20)
            selection = Path(result["selection_directory"])
            targets = {
                r["recording_id"]: r
                for line in (selection / "recovery-targets.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
                for r in [json.loads(line)]
            }
            status("reconciling_local_library", selected_candidates=len(targets))
            mappings, documents = local_documents(targets)
            store = AcquisitionStore(OUTPUT)
            tasks = {}
            for key, row in targets.items():
                known = mappings.get(key, set())
                task_key = "recording:" + next(iter(known)) if len(known) == 1 else key
                task = tasks.setdefault(
                    task_key, {**row, "candidate_ids": [], "chart_bindings": []}
                )
                task["candidate_ids"].append(key)
                task["chart_bindings"].extend(row["chart_bindings"])
            import hashlib

            from chart_observatory.lyrics.identity_quarantine import load_suspended_sources
            from chart_observatory.lyrics.repository import AUTHORIZED_RIGHTS

            suspended = load_suspended_sources()
            quarantine = json.loads(
                (ROOT / "config/lyrics_identity_quarantine.json").read_text(encoding="utf-8")
            )
            blocked_documents = {
                entry["lyric_document_id"]
                for entry in quarantine["entries"]
                if entry.get("decision") != "confirmed_match"
            }
            for key, task in tasks.items():
                store.enqueue(key, task)
                canonical = key.removeprefix("recording:") if key.startswith("recording:") else None
                existing = list(documents.get(canonical, []))
                for candidate_id in task["candidate_ids"]:
                    existing.extend(documents.get("candidate:" + candidate_id, []))
                for doc in existing:
                    if (
                        doc["source"].upper() in suspended
                        or str(doc["document_id"]) in blocked_documents
                        or doc["rights_status"] not in AUTHORIZED_RIGHTS
                        or hashlib.sha256(doc["text"].encode()).hexdigest() != doc["content_sha256"]
                    ):
                        continue
                    value = candidate(
                        doc["text"], doc["source"], existing_document_id=str(doc["document_id"])
                    )
                    if value and not value["text_quality_flags"] and store.claim(key):
                        if doc.get("metadata_only_cached_match"):
                            value["identity_check"] = (
                                "cached_exact_metadata_not_recording_validation"
                            )
                        store.finish(key, {**value, "status": "reused_pending_validation"})
                        break
            # Reuse earlier acquisition ledgers without silently promoting their candidates.
            legacy = (
                ROOT / "data/derived/annual_revision/20261025-final/acquisition/acquisition.jsonl"
            )
            if legacy.exists():
                lookup = {c: key for key, task in tasks.items() for c in task["candidate_ids"]}
                with legacy.open(encoding="utf-8") as handle:
                    for line in handle:
                        if not line.endswith("\n") or not line.strip():
                            continue
                        old = json.loads(line)
                        key = lookup.get(old.get("recording_id"))
                        if (
                            key
                            and old.get("text")
                            and old.get("source", "").upper() not in suspended
                            and identity(old.get("title", "")) == identity(tasks[key]["title"])
                            and identity(old.get("artist", "")) == identity(tasks[key]["artist"])
                        ):
                            value = candidate(
                                old["text"],
                                old.get("source", "UNKNOWN"),
                                existing_acquisition=str(legacy),
                            )
                            if value and store.claim(key):
                                store.finish(key, {**value, "status": "reused_pending_validation"})
            pending = [
                (key, tasks[key])
                for (key,) in store.conn.execute(
                    "SELECT identity FROM tasks WHERE status='pending'"
                )
                if key in tasks
            ]
            status("acquiring", unique_tasks=len(tasks), counters=store.summary(), workers=6)
            with httpx.Client(
                timeout=20,
                follow_redirects=True,
                headers={"User-Agent": "ChartObservatory/0.1 lyrics research"},
            ) as client:
                http = PacedHTTP(OUTPUT / "http-cache", client)

                def acquire(row):
                    try:
                        return fetch_candidate(row["title"], row["artist"], http)
                    except Exception as exc:
                        return dict(status="error_pending_review", error_type=type(exc).__name__)

                with ThreadPoolExecutor(6) as pool:
                    active, iterator = {}, iter(pending)
                    while True:
                        while len(active) < 6:
                            item = next(iterator, None)
                            if item is None:
                                break
                            key, row = item
                            if store.claim(key):
                                active[pool.submit(acquire, row)] = key
                        if not active:
                            break
                        done, _ = wait(active, timeout=15, return_when=FIRST_COMPLETED)
                        for future in done:
                            store.finish(active.pop(future), future.result())
                        status(
                            "acquiring",
                            unique_tasks=len(tasks),
                            counters=store.summary(),
                            workers=6,
                        )
            status(
                "acquisition_finished_pending_validation",
                counters=store.summary(),
                unique_tasks=len(tasks),
                note="No completeness or recording adjudication inferred",
            )
            store.conn.close()
        except Exception as exc:
            status("failed", error_type=type(exc).__name__)
            raise
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    main()
