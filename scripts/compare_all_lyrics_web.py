"""Checkpointed fresh web comparison of every staged candidate. Never approves or calls Vertex."""

import argparse
import hashlib
import json
import msvcrt
import os
import sqlite3
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from import_all_quota_lyrics import BASE, run_job
from sqlalchemy import create_engine, select, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.quota_acquisition import PacedHTTP
from chart_observatory.lyrics.quota_staging import blobs, candidates, runs
from chart_observatory.lyrics.web_comparison import compare_lrclib
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data/derived/lyrics/quota-20261030"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--hours", type=float, default=24)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--wait-campaign", type=Path)
    args = parser.parse_args()
    state = args.state_root.resolve()
    if not state.is_relative_to(ROOT / "data/runtime") or not 0 < args.hours <= 24:
        parser.error("state must be in project data/runtime; hours must be in (0,24]")
    state.mkdir(parents=True, exist_ok=True)
    with (state / "owner.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            if args.wait_campaign:
                previous = args.wait_campaign.resolve()
                if not previous.is_relative_to(ROOT / "data/runtime"):
                    raise ValueError("dependency campaign outside project runtime")
                previous_config = json.loads((previous / "campaign.json").read_text())
                wait_deadline = datetime.fromisoformat(previous_config["ends_at"]) + timedelta(
                    minutes=30
                )
                while datetime.now(UTC) < wait_deadline:
                    previous_status = json.loads((previous / "status.json").read_text())
                    if previous_status.get("stage", "").startswith("finished"):
                        break
                    publish_status(
                        state / "status.json",
                        dict(
                            stage="waiting_for_acquisition_to_share_provider_budget",
                            pid=os.getpid(),
                            total=previous_config["candidate_count"],
                            checked=0,
                            approvals=0,
                            paid_calls=0,
                            full_inventory=True,
                            updated_at=datetime.now(UTC).isoformat(),
                        ),
                    )
                    time.sleep(15)
                else:
                    raise TimeoutError("dependency campaign did not finish within its deadline")
            run(state, args)
        except Exception as error:
            publish_status(
                state / "status.json",
                dict(
                    stage="failed",
                    error_type=type(error).__name__,
                    paid_calls=0,
                    approvals=0,
                ),
            )
            raise


def run(state, args):
    db = sqlite3.connect(state / "comparison.sqlite")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS inputs(id TEXT PRIMARY KEY,payload TEXT,baseline TEXT,
            body TEXT,digest TEXT,flagged INTEGER,priority INTEGER,done INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS pending_comparison ON inputs(done,priority,id);
        CREATE TABLE IF NOT EXISTS results(id TEXT PRIMARY KEY,result TEXT);
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
    """)
    config_path = state / "campaign.json"
    if not config_path.exists():
        if db.execute("SELECT count(*) FROM inputs").fetchone()[0]:
            raise ValueError("incomplete comparison snapshot; inspect state before resuming")
        engine = create_engine(Settings.load(ROOT).database_url)
        try:
            with engine.connect() as conn:
                conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
                run = conn.execute(
                    select(runs.c.id)
                    .where(runs.c.manifest["selection_root"].as_string() == str(BASE))
                    .order_by(runs.c.created_at.desc())
                    .limit(1)
                ).scalar_one()
                query = (
                    select(candidates, blobs.c.body)
                    .outerjoin(blobs, candidates.c.text_sha256 == blobs.c.sha256)
                    .where(candidates.c.run_id == run)
                    .order_by(candidates.c.candidate_id)
                )
                if args.limit:
                    query = query.limit(args.limit)
                for row in conn.execution_options(stream_results=True).execute(query).mappings():
                    flagged = bool(
                        row["audit"].get("text_quality_flags")
                        or row["audit"].get("source_quarantined")
                        or row["audit"].get("shared_text_identity_collision")
                    )
                    db.execute(
                        "INSERT INTO inputs VALUES (?,?,?,?,?,?,?,0)",
                        (
                            row["candidate_id"],
                            json.dumps(row["payload"]),
                            json.dumps(row["source_result"]),
                            row["body"],
                            row["text_sha256"],
                            flagged,
                            0 if row["body"] is None else 1 if flagged else 2,
                        ),
                    )
                if args.limit is None:
                    expected = {
                        json.loads(line)["candidate_id"]
                        for line in (BASE / "combined.jsonl")
                        .read_text(encoding="utf-8")
                        .splitlines()
                        if line
                    }
                    actual = {r[0] for r in db.execute("SELECT id FROM inputs")}
                    if actual != expected:
                        raise ValueError(
                            "web comparison snapshot differs from frozen candidate scope"
                        )
                db.commit()
            now = datetime.now(UTC)
            publish_status(
                config_path,
                dict(
                    run_id=run,
                    starts_at=now.isoformat(),
                    ends_at=(now + timedelta(hours=args.hours)).isoformat(),
                    full_inventory=args.limit is None,
                    paid_calls_authorized=0,
                    total=db.execute("SELECT count(*) FROM inputs").fetchone()[0],
                    comparison_is_not_adjudication=True,
                ),
            )
        finally:
            engine.dispose()
    config = json.loads(config_path.read_text())
    deadline = datetime.fromisoformat(config["ends_at"])
    proposals = state / "proposals"
    proposals.mkdir(exist_ok=True)
    cooldowns = STORE / "http-cache/provider-cooldowns.sqlite"
    counts = Counter(json.loads(r)["status"] for (r,) in db.execute("SELECT result FROM results"))
    proposal_count = db.execute(
        "SELECT count(*) FROM results WHERE json_extract(result,'$.proposal_file') IS NOT NULL"
    ).fetchone()[0]
    published = int(
        (db.execute("SELECT value FROM meta WHERE key='published'").fetchone() or [0])[0]
    )

    def publish_proposals():
        nonlocal published
        directory = state / "publication" / f"cycle-{sum(counts.values()):06d}"
        command = [
            sys.executable,
            "scripts/publish_source_checked_replays.py",
            "--proposals",
            str(proposals),
            "--report",
            str(directory / "checks.json"),
        ]
        if run_job(command, directory, dict(os.environ)):
            raise RuntimeError("source-checked proposal publication failed")
        staging = directory / "staging"
        if run_job(
            [
                sys.executable,
                "scripts/stage_quota_lyrics.py",
                "--base-root",
                str(BASE),
                "--state-root",
                str(staging),
            ],
            staging,
            dict(os.environ),
        ):
            raise RuntimeError("web comparison staging failed")
        published = proposal_count
        db.execute("INSERT OR REPLACE INTO meta VALUES ('published',?)", (str(published),))
        db.commit()

    def report(stage, **extra):
        publish_status(
            state / "status.json",
            dict(
                stage=stage,
                pid=os.getpid(),
                run_id=config["run_id"],
                total=config["total"],
                checked=sum(counts.values()),
                counts=dict(counts),
                paid_calls=0,
                approvals=0,
                proposals=proposal_count,
                published_proposals=published,
                classification_ready=False,
                updated_at=datetime.now(UTC).isoformat(),
                **extra,
            ),
        )

    stop_reason = {}
    with httpx.Client(
        timeout=20,
        follow_redirects=True,
        headers={"User-Agent": "ChartObservatoryWebComparison/0.1 music research"},
    ) as client:
        # No old response directories are borrowed: successful responses come from
        # this comparison campaign, while provider pauses remain shared.
        http = PacedHTTP(
            state / "acquisition/http-cache", client, interval=1.5, cooldown_path=cooldowns
        )
        report("comparing_current_web_sources")
        while True:
            if datetime.now(UTC) >= deadline:
                break
            pending = db.execute(
                "SELECT id,payload,baseline,body,digest,flagged,priority FROM inputs "
                "WHERE done=0 ORDER BY priority,id LIMIT 1"
            ).fetchone()
            if pending is None:
                break
            key, raw_payload, raw_baseline, body, digest, flagged, _priority = pending
            payload, baseline = json.loads(raw_payload), json.loads(raw_baseline)
            while datetime.now(UTC) < deadline:
                with sqlite3.connect(cooldowns.as_uri() + "?mode=ro", uri=True) as pauses:
                    pause = pauses.execute(
                        "SELECT until_epoch FROM provider_cooldowns WHERE domain='lrclib.net'"
                    ).fetchone()
                delay = max(0, pause[0] - time.time()) if pause else 0
                if not delay:
                    break
                report("waiting_provider_cooldown", retry_in_seconds=round(delay))
                time.sleep(min(15, delay))
            if datetime.now(UTC) >= deadline:
                break
            metadata = baseline.get("source_metadata") or {}
            provider_id = metadata.get("id") if baseline.get("source") == "LRCLIB" else None
            http.start_trace()
            try:
                if not payload.get("title") or not payload.get("artist"):
                    checked, candidate = dict(status="metadata_unresolved"), None
                else:
                    response = (
                        http.get(f"https://lrclib.net/api/get/{provider_id}")
                        if type(provider_id) is int and provider_id > 0
                        else http.get(
                            "https://lrclib.net/api/search",
                            params={
                                "track_name": payload["title"],
                                "artist_name": payload["artist"].split("|", 1)[0].strip(),
                            },
                        )
                    )
                    if response.status_code in (401, 403, 429, 500, 502, 503, 504):
                        report(
                            "provider_paused_request_not_completed",
                            http_status=response.status_code,
                        )
                        # Keep this candidate pending; retry only after the shared pause.
                        if response.status_code in (401, 403):
                            stop_reason = dict(
                                provider="lrclib.net",
                                http_status=response.status_code,
                                reason="provider_access_blocked",
                            )
                            break
                        continue
                    if response.status_code != 200:
                        checked, candidate = (
                            dict(status="web_unavailable", http_status=response.status_code),
                            None,
                        )
                    else:
                        rows = response.json()
                        rows = rows if isinstance(rows, list) else [rows]
                        if provider_id and any(
                            r.get("id") != provider_id for r in rows if isinstance(r, dict)
                        ):
                            checked, candidate = dict(status="provider_record_id_mismatch"), None
                        else:
                            checked, candidate = compare_lrclib(
                                payload, baseline, body, digest, rows, list(http.trace)
                            )
            except (httpx.RequestError, ValueError) as error:
                checked, candidate = (
                    dict(status="comparison_error", error_type=type(error).__name__),
                    None,
                )
            checked.update(
                candidate_id=key,
                identity_validated=False,
                completeness_validated=False,
                classification_ready=False,
                compared_at=datetime.now(UTC).isoformat(),
            )
            if candidate and (body is None or flagged):
                proposal = dict(
                    payload=payload,
                    result=candidate,
                    network_requests=1,
                    replay_kind="missing_text" if body is None else "flagged_repair",
                    replaces_text_sha256=digest,
                    recovered_at=datetime.now(UTC).isoformat(),
                )
                raw = json.dumps(proposal, ensure_ascii=False).encode()
                path = proposals / (hashlib.sha256(raw).hexdigest() + ".json")
                path.write_bytes(raw)
                checked["proposal_file"] = str(path)
                proposal_count += 1
            db.execute("INSERT OR REPLACE INTO results VALUES (?,?)", (key, json.dumps(checked)))
            db.execute("UPDATE inputs SET done=1 WHERE id=?", (key,))
            db.commit()
            counts[checked["status"]] += 1
            report("comparing_current_web_sources")
            if proposal_count - published >= 25:
                publish_proposals()
    if proposal_count > published:
        publish_proposals()
    report(
        "completed" if sum(counts.values()) == config["total"] else "paused_pending_comparisons",
        **stop_reason,
    )
    db.close()


if __name__ == "__main__":
    main()
