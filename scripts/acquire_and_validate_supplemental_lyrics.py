"""Resumable acquisition, import, and strict validation of supplemental-series lyrics."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
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
        default=Path("data/runtime/supplemental-lyrics-20261117-01/supplemental-lyric-queue.jsonl"),
    )
    parser.add_argument(
        "--v08",
        type=Path,
        default=Path("data/runtime/priority-full-verification-20261117-08-v10-post-import/decisions.jsonl"),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/runtime/supplemental-lyrics-20261117-01"),
    )
    parser.add_argument("--acquire-limit", type=int, default=100)
    parser.add_argument("--link-canonical", action="store_true", default=True)
    parser.add_argument("--retry-unavailable", action="store_true", default=False)
    parser.add_argument(
        "--supp-db",
        type=Path,
        default=Path("data/derived/annual_revision/provider_series/supplemental-catalog-20261117-39.sqlite"),
    )
    args = parser.parse_args(argv)

    project = Path.cwd().resolve()
    args.root.mkdir(parents=True, exist_ok=True)
    db_path = args.root / "supplemental-lyrics.sqlite"
    conn = sqlite3.connect(db_path)
    init_db(conn)

    # Load duration_ms per song_id from supplemental_memberships.raw_json when available
    duration_by_song: dict[str, int] = {}
    if args.supp_db.exists():
        sdb = sqlite3.connect(args.supp_db.resolve().as_uri() + "?mode=ro", uri=True)
        for sid, raw_j in sdb.execute("SELECT song_id, raw_json FROM supplemental_memberships"):
            if sid in duration_by_song:
                continue
            try:
                raw = json.loads(raw_j)
            except Exception:
                continue
            if raw.get("duration_ms"):
                duration_by_song[sid] = int(raw["duration_ms"])
            elif isinstance(raw.get("source_entry"), dict):
                dur = ((raw["source_entry"].get("track") or {}).get("duration"))
                if dur:
                    duration_by_song[sid] = int(float(dur) * 1000)
        sdb.close()

    already_done = {
        row[0]: row[1]
        for row in conn.execute("SELECT song_id, validation_status FROM supplemental_lyrics")
    }

    queue = [json.loads(l) for l in args.queue.read_text(encoding="utf-8").splitlines() if l.strip()]

    # 1. Link matched_canonical_validated
    linked_now = 0
    if args.link_canonical:
        v08_map = {}
        with args.v08.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    v08_map[d["candidate_id"]] = d
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with conn:
            for item in queue:
                if item["state"] != "matched_canonical_validated":
                    continue
                sid = item["song_id"]
                if sid in already_done:
                    continue
                v8 = v08_map.get(item["matched_canonical_id"])
                if not v8:
                    continue
                val = v8.get("validation") or {}
                flags = (v8.get("audit") or {}).get("text_quality_flags") or []
                conn.execute(
                    "INSERT OR REPLACE INTO supplemental_lyrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        sid,
                        item["state"],
                        item["matched_canonical_id"],
                        v8.get("text_sha256"),
                        None,
                        (v8.get("source_result") or {}).get("source"),
                        "passed_canonical_v08",
                        (val.get("identity") or {}).get("status"),
                        (val.get("completeness") or {}).get("status"),
                        (val.get("source_text_integrity") or {}).get("status"),
                        None,
                        json.dumps(flags),
                        json.dumps(v8.get("source_result") or {}, ensure_ascii=False),
                        json.dumps(val, ensure_ascii=False),
                        now,
                    ),
                )
                already_done[sid] = "passed_canonical_v08"
                linked_now += 1

    # 2. Acquire new_requires_acquisition up to acquire_limit
    acquired_now = 0
    cache_dir = args.root / "http-cache"
    texts_dir = args.root / "texts"
    texts_dir.mkdir(exist_ok=True)
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        http = PacedHTTP(cache_dir, client)
        for item in queue:
            if acquired_now >= args.acquire_limit:
                break
            if item["state"] != "new_requires_acquisition":
                continue
            sid = item["song_id"]
            if sid in already_done and not (args.retry_unavailable and already_done[sid] == "unavailable"):
                continue
            dur_ms = duration_by_song.get(sid)
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
                    http,
                    first_time=True,
                    metadata_resolution=meta_res,
                )
            except Exception as exc:
                result = {"status": "access_failed", "error": f"{type(exc).__name__}: {exc}"}

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
            overall = assessment.get("automated_overall") or result.get("status") or "unavailable"
            if result.get("instrumental") or (result.get("source_metadata") or {}).get("instrumental"):
                overall = "instrumental"
            lang = (assessment.get("language_identification") or {}).get("language_code")
            now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO supplemental_lyrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        sid,
                        item["state"],
                        None,
                        sha,
                        text_path,
                        result.get("source"),
                        overall,
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
                    (sid, None, sha, f"initial_acquisition:{overall}", now),
                )
            acquired_now += 1
            if acquired_now % 20 == 0:
                print(json.dumps({"acquired_now": acquired_now, "last_song": sid, "status": overall}), flush=True)

    counts = Counter(
        row[0] for row in conn.execute("SELECT validation_status FROM supplemental_lyrics")
    )
    conn.close()
    summary = {
        "schema_version": "supplemental-lyrics-status-v1",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "linked_canonical_now": linked_now,
        "acquired_now": acquired_now,
        "total_processed_in_db": sum(counts.values()),
        "validation_status_counts": dict(counts),
    }
    (args.root / "acquisition-report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
