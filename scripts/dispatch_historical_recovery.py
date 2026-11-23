"""Lease disjoint country/year research tasks; never modifies annual selections.

Claims are discovery assignments, not evidence of an annual ranking or AI readiness.
Workers must publish preserved sources and verification in their own output directory.
"""

import argparse
import hashlib
import json
import sqlite3
import time
from pathlib import Path


def connect(path):
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY, payload TEXT NOT NULL, priority INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', owner TEXT, lease_until REAL,
        available_after REAL NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0,
        outcome TEXT, evidence_manifest TEXT)""")
    conn.execute("CREATE TABLE IF NOT EXISTS inputs (path TEXT PRIMARY KEY, sha256 TEXT NOT NULL)")
    return conn


def initialize(conn, selection):
    paths = [selection / "manifest.json", selection / "country_years.jsonl"]
    digests = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    conn.execute("BEGIN IMMEDIATE")
    try:
        saved = dict(conn.execute("SELECT path,sha256 FROM inputs"))
        if saved and saved != digests:
            raise ValueError("dispatcher belongs to different or modified frozen inputs")
        for path, digest in digests.items():
            conn.execute("INSERT OR IGNORE INTO inputs VALUES (?,?)", (path, digest))
        for line in paths[1].read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            missing = row.get("missing_complete_annual_positions")
            if missing is None:
                missing = row.get("missing_positions")
            if not missing or row.get("quota") is None:
                continue
            task_id = f"{row['country_code']}-{row['year']}"
            payload = {**row, "task_id": task_id,
                       "selection": str(selection.resolve()),
                       "annual_rank_certified": False, "classification_ready": False,
                       "required_evidence": ["publisher geography", "reported annual period",
                                             "methodology", "published depth and rank semantics",
                                             "original response bytes and checksum",
                                             "native recording identities"]}
            conn.execute("INSERT OR IGNORE INTO tasks(task_id,payload,priority) VALUES (?,?,?)",
                         (task_id, json.dumps(payload, ensure_ascii=False), int(missing)))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def claim(conn, owner, limit, lease_seconds, now=None, countries=(), task_ids=()):
    if not owner or limit < 1 or lease_seconds < 1:
        raise ValueError("owner, positive limit and positive lease required")
    now = time.time() if now is None else now
    conn.execute("BEGIN IMMEDIATE")
    try:
        country_filter = ""
        if countries:
            country_filter = " AND substr(task_id,1,2) IN (" + ",".join("?" for _ in countries) + ")"
        exact_filter = ""
        if task_ids:
            if len(set(task_ids)) != len(task_ids) or len(task_ids) > limit:
                raise ValueError("exact task set must be unique and fit limit")
            exact_filter = " AND task_id IN (" + ",".join("?" for _ in task_ids) + ")"
        rows = conn.execute("""SELECT * FROM tasks
            WHERE (status='pending' OR (status='claimed' AND lease_until<=?))
              AND available_after<=?
            """ + country_filter + exact_filter + " ORDER BY priority DESC, attempts ASC, task_id ASC LIMIT ?",
                            (now, now, *countries, *task_ids, limit)).fetchall()
        if task_ids and {r["task_id"] for r in rows} != set(task_ids):
            raise ValueError("exact task set unavailable; no claims changed")
        for row in rows:
            conn.execute("""UPDATE tasks SET status='claimed',owner=?,lease_until=?,attempts=attempts+1
                            WHERE task_id=?""", (owner, now + lease_seconds, row["task_id"]))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return [{**json.loads(r["payload"]), "owner": owner, "lease_until": now + lease_seconds,
             "attempt": r["attempts"] + 1} for r in rows]


def transfer(conn, task_ids, expected_owner, new_owner, lease_seconds, now=None):
    """Atomically transfer exactly the specified live claims, never substitute tasks."""
    if not task_ids or len(set(task_ids)) != len(task_ids) or not expected_owner or not new_owner or lease_seconds < 1:
        raise ValueError("unique tasks, both owners and positive lease required")
    now = time.time() if now is None else now
    conn.execute("BEGIN IMMEDIATE")
    try:
        rows = conn.execute("SELECT * FROM tasks WHERE task_id IN (" +
                            ",".join("?" for _ in task_ids) + ")", tuple(task_ids)).fetchall()
        if len(rows) != len(task_ids) or any(r["owner"] != expected_owner or
                r["status"] != "claimed" or r["lease_until"] <= now for r in rows):
            raise ValueError("exact transfer requires current owner and live claims; no claims changed")
        for row in rows:
            conn.execute("UPDATE tasks SET owner=?,lease_until=? WHERE task_id=?",
                         (new_owner, now + lease_seconds, row["task_id"]))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return [{**json.loads(r["payload"]), "previous_owner": expected_owner,
             "owner": new_owner, "lease_until": now + lease_seconds,
             "attempt": r["attempts"]} for r in rows]


def finish(conn, task_id, owner, outcome, evidence_manifest, retry_seconds):
    if outcome not in {"evidence_ready", "retry", "unresolved"} or retry_seconds < 0:
        raise ValueError("invalid outcome or retry delay")
    # A ready handoff requires actual bytes; publication remains separate from promotion.
    evidence = Path(evidence_manifest).resolve() if evidence_manifest else None
    if outcome == "evidence_ready" and (evidence is None or not evidence.is_file()):
        raise ValueError("evidence_ready requires an existing evidence manifest")
    now = time.time()
    result = conn.execute("""UPDATE tasks SET status=?, outcome=?, evidence_manifest=?,
        available_after=?, lease_until=NULL WHERE task_id=? AND owner=?
        AND status='claimed' AND lease_until>?""",
                          ("pending" if outcome == "retry" else "handoff" if outcome == "evidence_ready" else "unresolved",
                           outcome, str(evidence) if evidence else None, now + retry_seconds,
                           task_id, owner, now))
    if result.rowcount != 1:
        raise ValueError("claim missing, expired or owned by another worker")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    commands = parser.add_subparsers(dest="action", required=True)
    init = commands.add_parser("init")
    init.add_argument("--selection", type=Path, required=True)
    work = commands.add_parser("claim")
    work.add_argument("--owner", required=True)
    work.add_argument("--limit", type=int, default=3)
    work.add_argument("--lease-seconds", type=int, default=3600)
    work.add_argument("--output", type=Path, required=True)
    work.add_argument("--countries", nargs="*", default=[])
    work.add_argument("--task-ids", nargs="+", default=[])
    move = commands.add_parser("transfer")
    move.add_argument("--task-ids", nargs="+", required=True)
    move.add_argument("--expected-owner", required=True)
    move.add_argument("--new-owner", required=True)
    move.add_argument("--lease-seconds", type=int, default=3600)
    move.add_argument("--output", type=Path, required=True)
    done = commands.add_parser("finish")
    done.add_argument("--task-id", required=True)
    done.add_argument("--owner", required=True)
    done.add_argument("--outcome", choices=("evidence_ready", "retry", "unresolved"), required=True)
    done.add_argument("--evidence-manifest")
    done.add_argument("--retry-seconds", type=int, default=3600)
    commands.add_parser("status")
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with connect(args.db) as conn:
        if args.action == "init":
            initialize(conn, args.selection)
        elif args.action == "claim":
            # Refuse an overwrite before claiming work, so a prior assignment stays visible.
            with args.output.open("x", encoding="utf-8") as stream:
                for row in claim(conn, args.owner, args.limit, args.lease_seconds,
                                 countries=args.countries, task_ids=args.task_ids):
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        elif args.action == "transfer":
            with args.output.open("x", encoding="utf-8") as stream:
                for row in transfer(conn, args.task_ids, args.expected_owner,
                                    args.new_owner, args.lease_seconds):
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        elif args.action == "finish":
            finish(conn, args.task_id, args.owner, args.outcome,
                   args.evidence_manifest, args.retry_seconds)
        print(json.dumps({r[0]: r[1] for r in conn.execute("SELECT status,count(*) FROM tasks GROUP BY status")}))


if __name__ == "__main__":
    main()
