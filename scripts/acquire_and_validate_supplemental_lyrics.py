"""Resumable acquisition, import, and strict validation of supplemental-series lyrics."""

import argparse
import hashlib
import json
import sqlite3
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import httpx

from chart_observatory.lyrics.automated_validation import assess_lyric_identity_completeness
from chart_observatory.lyrics.corpus_quality import assess_acquired_lyric
from chart_observatory.lyrics.language_identification import identify_language
from chart_observatory.lyrics.quota_acquisition import PacedHTTP
from chart_observatory.lyrics.quota_discovery import audit_saved_result, recover_with_fallback
from chart_observatory.lyrics.source_chain import verify_source_chain


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS supplemental_lyrics (
            song_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            matched_canonical_id TEXT,
            text_sha256 TEXT,
            text_path TEXT,
            source TEXT,
            validation_status TEXT NOT NULL,
            failure_category TEXT,
            inherited_audit_version TEXT,
            identity_status TEXT,
            completeness_status TEXT,
            source_integrity_status TEXT,
            language_code TEXT,
            flags_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            validation_json TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS supplemental_lyric_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id TEXT NOT NULL,
            previous_sha256 TEXT,
            new_sha256 TEXT,
            reason TEXT NOT NULL,
            recorded_at_utc TEXT NOT NULL
        );
        """
    )


def classify_failure(result: dict, assessment: dict) -> str:
    if result.get("instrumental") or (result.get("source_metadata") or {}).get("instrumental"):
        return "instrumental"
    errs = result.get("source_errors") or []
    err_str = " ".join(str(e) for e in errs)
    if "divergent_exact_lrclib_editions" in err_str:
        return "divergent_editions"
    if ":429" in err_str or ":403" in err_str or "Timeout" in err_str or "RequestError" in err_str:
        return "access_failed_rate_limited"
    if assessment.get("automated_overall") == "pending_review":
        return "incomplete_or_identity_pending"
    if ":404" in err_str or result.get("status") == "not_found_or_unverified":
        return "not_found_404"
    return "unavailable_other"


def validate_record(payload: dict, source_result: dict, text: str | None, sha: str | None, project: Path) -> dict:
    if text is None:
        return {
            "automated_overall": "unavailable",
            "identity": {"status": "pending"},
            "completeness": {"status": "pending"},
            "source_text_integrity": {"status": "unavailable"},
            "text_quality_flags": ["no_local_text"],
        }
    audit = audit_saved_result(payload, source_result)
    assessed = assess_acquired_lyric(payload, source_result, text, sha)
    flags = sorted(set(audit.get("text_quality_flags") or []) | set(assessed.get("flags") or []))
    audit["text_quality_flags"] = flags
    chain = verify_source_chain(payload, source_result, text, sha, project)
    record = {
        "payload": payload,
        "source_result": source_result,
        "text_sha256": sha,
        "audit": audit,
    }
    assessment = assess_lyric_identity_completeness(record, text, chain)
    assessment["language_identification"] = identify_language(
        text, source_metadata=source_result.get("source_metadata")
    )
    assessment["text_quality_flags"] = flags
    return assessment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path("data/runtime/supplemental-lyrics-20261118-01/supplemental-lyric-queue.jsonl"),
    )
    parser.add_argument(
        "--strict-audit",
        type=Path,
        default=Path("data/runtime/priority-full-verification-20261117-13-canonical-live-current-code/decisions.jsonl"),
    )
    parser.add_argument("--strict-audit-version", default="v13")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/runtime/supplemental-lyrics-20261118-01"),
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--max-batches", type=int, default=0, help="0 = run until actionable queue is exhausted")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--cache-only", action="store_true", default=False)
    parser.add_argument("--retry-rate-limited", action="store_true", default=False)
    args = parser.parse_args(argv)

    project = Path.cwd().resolve()
    args.root.mkdir(parents=True, exist_ok=True)
    texts_dir = args.root / "texts"
    texts_dir.mkdir(exist_ok=True)
    cache_dir = args.root / "http-cache"
    cache_dir.mkdir(exist_ok=True)

    fallback_caches = [
        p
        for p in (
            Path("data/runtime/final-pipeline/http-cache"),
            Path("data/runtime/final-pipeline-post-final-run-20261117-02/http-cache"),
            Path("data/runtime/supplemental-lyrics-20261117-02/http-cache"),
        )
        if p.is_dir()
    ]

    db_path = args.root / "supplemental-lyrics.sqlite"
    conn = sqlite3.connect(db_path)
    init_db(conn)

    already_done = {
        row[0]: (row[1], row[2])
        for row in conn.execute("SELECT song_id, validation_status, failure_category FROM supplemental_lyrics")
    }

    queue = [json.loads(l) for l in args.queue.read_text(encoding="utf-8").splitlines() if l.strip()]

    # 1. Link matched_canonical_validated and record unresolved_identity_missing_credit
    linked_now = 0
    unresolved_now = 0
    need_strict = any(
        item["state"] in ("matched_canonical_validated", "matched_canonical_needs_validation_or_correction")
        and item["song_id"] not in already_done
        for item in queue
    )
    strict_map = {}
    if need_strict:
        with args.strict_audit.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    strict_map[d["candidate_id"]] = d

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with conn:
        for item in queue:
            sid = item["song_id"]
            if sid in already_done:
                continue
            if item["state"] == "matched_canonical_validated":
                sa = strict_map.get(item["matched_canonical_id"])
                if not sa:
                    continue
                val = sa.get("validation") or {}
                flags = (sa.get("audit") or {}).get("text_quality_flags") or []
                conn.execute(
                    "INSERT OR REPLACE INTO supplemental_lyrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        sid,
                        item["state"],
                        item["matched_canonical_id"],
                        sa.get("text_sha256"),
                        None,
                        (sa.get("source_result") or {}).get("source"),
                        "inherited_canonical_strict_passed",
                        None,
                        args.strict_audit_version,
                        (val.get("identity") or {}).get("status"),
                        (val.get("completeness") or {}).get("status"),
                        (val.get("source_text_integrity") or {}).get("status"),
                        None,
                        json.dumps(flags),
                        json.dumps(sa.get("source_result") or {}, ensure_ascii=False),
                        json.dumps(val, ensure_ascii=False),
                        now,
                    ),
                )
                already_done[sid] = ("inherited_canonical_strict_passed", None)
                linked_now += 1
            elif item["state"] == "matched_canonical_needs_validation_or_correction":
                sa = strict_map.get(item["matched_canonical_id"])
                if not sa:
                    continue
                val = sa.get("validation") or {}
                flags = (sa.get("audit") or {}).get("text_quality_flags") or []
                overall = val.get("automated_overall") or "pending_review"
                conn.execute(
                    "INSERT OR REPLACE INTO supplemental_lyrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        sid,
                        item["state"],
                        item["matched_canonical_id"],
                        sa.get("text_sha256"),
                        None,
                        (sa.get("source_result") or {}).get("source"),
                        f"inherited_canonical_{overall}",
                        "canonical_needs_validation_or_correction",
                        args.strict_audit_version,
                        (val.get("identity") or {}).get("status"),
                        (val.get("completeness") or {}).get("status"),
                        (val.get("source_text_integrity") or {}).get("status"),
                        None,
                        json.dumps(flags),
                        json.dumps(sa.get("source_result") or {}, ensure_ascii=False),
                        json.dumps(val, ensure_ascii=False),
                        now,
                    ),
                )
                already_done[sid] = (f"inherited_canonical_{overall}", "canonical_needs_validation_or_correction")
                linked_now += 1
            elif item["state"] == "unresolved_identity_missing_credit":
                conn.execute(
                    "INSERT OR REPLACE INTO supplemental_lyrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        sid,
                        item["state"],
                        None,
                        None,
                        None,
                        None,
                        "unresolved_identity_missing_credit",
                        "missing_title_or_artist",
                        None,
                        "pending",
                        "pending",
                        "unavailable",
                        None,
                        "[]",
                        "{}",
                        "{}",
                        now,
                    ),
                )
                already_done[sid] = ("unresolved_identity_missing_credit", "missing_title_or_artist")
                unresolved_now += 1

    # 2. Build actionable acquisition list
    actionable_states = {
        "new_requires_acquisition",
        "matched_canonical_needs_validation_or_correction",
        "matched_canonical_missing_text",
        "identity_ambiguous_multiple_canonical",
    }
    todo = []
    for item in queue:
        if item["state"] not in actionable_states:
            continue
        sid = item["song_id"]
        if sid in already_done:
            st, fcat = already_done[sid]
            if not (args.retry_rate_limited and fcat == "access_failed_rate_limited"):
                continue
        todo.append(item)

    thread_local = threading.local()

    def get_http() -> PacedHTTP:
        if not hasattr(thread_local, "http"):
            if args.cache_only:
                transport = httpx.MockTransport(lambda req: httpx.Response(503, request=req))
                client = httpx.Client(transport=transport)
            else:
                client = httpx.Client(timeout=20, follow_redirects=True)
            thread_local.http = PacedHTTP(
                cache_dir,
                client,
                cache_sources=fallback_caches,
                interval=args.interval,
            )
        return thread_local.http

    def process_one(item: dict) -> tuple[dict, dict, str | None, str | None, str | None, dict]:
        sid = item["song_id"]
        dur_ms = item.get("duration_ms")
        meta_res = {"duration_ms": dur_ms} if dur_ms else {}
        payload = {
            "title": item["title"],
            "artist": item["artist_credit"],
            "candidate_id": sid,
            "metadata_resolution": meta_res,
        }
        try:
            result = recover_with_fallback(
                item["title"],
                item["artist_credit"],
                get_http(),
                first_time=True,
                metadata_resolution=meta_res,
            )
        except Exception as exc:
            result = {"status": "access_failed", "source_errors": [f"{type(exc).__name__}: {exc}"]}

        text = result.pop("text", None)
        sha = None
        text_path = None
        if text:
            sha = sha256_text(text)
            tp = texts_dir / f"{sha}.txt"
            if not tp.exists():
                tp.write_bytes(text.encode("utf-8"))
            text_path = str(tp.resolve())
            result["text_path"] = text_path
            result["text_sha256"] = sha

        assessment = validate_record(payload, result, text, sha, project)
        return item, result, sha, text_path, text, assessment

    total_acquired_session = 0
    batch_num = 0
    t_start = time.monotonic()

    for offset in range(0, len(todo), args.batch_size):
        if args.max_batches and batch_num >= args.max_batches:
            break
        batch = todo[offset : offset + args.batch_size]
        batch_num += 1
        b_start = time.monotonic()
        results = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = [pool.submit(process_one, it) for it in batch]
            for fut in as_completed(futs):
                results.append(fut.result())

        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with conn:
            for item, result, sha, text_path, _, assessment in results:
                sid = item["song_id"]
                overall = assessment.get("automated_overall") or result.get("status") or "unavailable"
                if result.get("instrumental") or (result.get("source_metadata") or {}).get("instrumental"):
                    overall = "instrumental"
                fcat = None if overall == "passed" else classify_failure(result, assessment)
                lang = (assessment.get("language_identification") or {}).get("language_code")
                conn.execute(
                    "INSERT OR REPLACE INTO supplemental_lyrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        sid,
                        item["state"],
                        item.get("matched_canonical_id"),
                        sha,
                        text_path,
                        result.get("source"),
                        overall,
                        fcat,
                        None,
                        (assessment.get("identity") or {}).get("status"),
                        (assessment.get("completeness") or {}).get("status"),
                        (assessment.get("source_text_integrity") or {}).get("status"),
                        lang,
                        json.dumps(assessment.get("text_quality_flags") or []),
                        json.dumps(result, ensure_ascii=False),
                        json.dumps(assessment, ensure_ascii=False),
                        now,
                    ),
                )
                conn.execute(
                    "INSERT INTO supplemental_lyric_ledger (song_id, previous_sha256, new_sha256, reason, recorded_at_utc) VALUES (?,?,?,?,?)",
                    (sid, None, sha, f"batch_{batch_num}:{overall}:{fcat or 'ok'}", now),
                )
                total_acquired_session += 1

        elapsed_b = max(0.01, time.monotonic() - b_start)
        counts = Counter(row[0] for row in conn.execute("SELECT validation_status FROM supplemental_lyrics"))
        fcats = Counter(row[0] for row in conn.execute("SELECT failure_category FROM supplemental_lyrics WHERE failure_category IS NOT NULL"))
        report = {
            "schema_version": "supplemental-lyrics-status-v2",
            "generated_at_utc": now,
            "strict_audit_version": args.strict_audit_version,
            "linked_canonical_session": linked_now,
            "unresolved_recorded_session": unresolved_now,
            "acquired_session": total_acquired_session,
            "remaining_actionable": max(0, len(todo) - (offset + len(batch))),
            "total_processed_in_db": sum(counts.values()),
            "total_in_queue": len(queue),
            "last_batch_num": batch_num,
            "last_batch_rate_per_min": round(len(batch) / (elapsed_b / 60.0), 1),
            "validation_status_counts": dict(counts),
            "failure_category_counts": dict(fcats),
        }
        (args.root / "acquisition-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"batch": batch_num, "processed": sum(counts.values()), "remaining": report["remaining_actionable"], "rate_per_min": report["last_batch_rate_per_min"], "statuses": dict(counts)}), flush=True)

    # Also write final report even if todo was empty
    counts = Counter(row[0] for row in conn.execute("SELECT validation_status FROM supplemental_lyrics"))
    fcats = Counter(row[0] for row in conn.execute("SELECT failure_category FROM supplemental_lyrics WHERE failure_category IS NOT NULL"))
    final_report = {
        "schema_version": "supplemental-lyrics-status-v2",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "strict_audit_version": args.strict_audit_version,
        "linked_canonical_session": linked_now,
        "unresolved_recorded_session": unresolved_now,
        "acquired_session": total_acquired_session,
        "remaining_actionable": max(0, len(todo) - total_acquired_session),
        "total_processed_in_db": sum(counts.values()),
        "total_in_queue": len(queue),
        "validation_status_counts": dict(counts),
        "failure_category_counts": dict(fcats),
    }
    (args.root / "acquisition-report.json").write_text(
        json.dumps(final_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    conn.close()
    print(json.dumps(final_report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
