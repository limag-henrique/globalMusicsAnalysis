"""Import acquisition progress for human review without starting another collector."""

import argparse
import hashlib
import json
import msvcrt
import os
import sqlite3
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from import_all_quota_lyrics import BASE, ROOT, STORE, run_job

from chart_observatory.runtime_status import publish_status


def needs_refresh(previous, observed, elapsed_seconds):
    if not previous:
        return True
    if previous["fingerprint"] == observed["fingerprint"]:
        return False
    return abs(observed["with_text"] - previous["with_text"]) >= 100 or elapsed_seconds >= 1800


def observe(candidate_ids):
    checksum = hashlib.sha256()
    count = with_text = 0
    with sqlite3.connect((STORE / "acquisition.sqlite").as_uri() + "?mode=ro", uri=True) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        for key, payload, raw in conn.execute(
            "SELECT identity,payload,result FROM tasks ORDER BY identity"
        ):
            if key not in candidate_ids:
                continue
            result = json.loads(raw) if raw else {}
            count += 1
            with_text += bool(result.get("text_sha256") and result.get("text_path"))
            checksum.update(json.dumps([key, payload, raw], ensure_ascii=False).encode())
    if count != len(candidate_ids):
        raise ValueError("acquisition inventory does not match frozen selection")
    return dict(
        fingerprint=checksum.hexdigest(),
        candidates=count,
        with_text=with_text,
        without_text=count - with_text,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", required=True, type=Path)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    campaign_root = args.campaign_root.resolve()
    if not campaign_root.is_relative_to((ROOT / "data/runtime").resolve()):
        parser.error("campaign must be inside project data/runtime")
    config = json.loads((campaign_root / "campaign.json").read_text())
    selected = (BASE / "combined.jsonl").read_bytes()
    if hashlib.sha256(selected).hexdigest() != config["selection_sha256"]:
        raise ValueError("frozen acquisition selection changed")
    ids = {
        json.loads(line)["candidate_id"] for line in selected.decode("utf-8").splitlines() if line
    }
    state = campaign_root / "validation-updates"
    state.mkdir(exist_ok=True)
    with (state / "owner.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        checkpoint_path = state / "checkpoint.json"
        checkpoint = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {}
        deadline = datetime.fromisoformat(config["ends_at"]) + timedelta(minutes=15)
        while datetime.now(UTC) < deadline:
            observed = observe(ids)
            previous = checkpoint.get("observation")
            elapsed = (
                (
                    datetime.now(UTC) - datetime.fromisoformat(checkpoint["imported_at"])
                ).total_seconds()
                if checkpoint
                else 0
            )
            if needs_refresh(previous, observed, elapsed):
                cycle = checkpoint.get("cycle", 0) + 1
                output = state / f"cycle-{cycle:04d}"
                output.mkdir(exist_ok=True)
                publish_status(
                    state / "status.json",
                    dict(
                        stage="importing",
                        pid=os.getpid(),
                        cycle=cycle,
                        observation=observed,
                        paid_calls=0,
                    ),
                )
                stage_code = run_job(
                    [
                        sys.executable,
                        "scripts/stage_quota_lyrics.py",
                        "--base-root",
                        str(BASE),
                        "--state-root",
                        str(output / "staging"),
                    ],
                    output / "staging",
                    dict(os.environ),
                )
                if stage_code:
                    raise RuntimeError("validation staging failed; inspect cycle stderr")
                audit_code = run_job(
                    [
                        sys.executable,
                        "scripts/audit_current_lyric_corpus.py",
                        "--output",
                        str(output / "audit"),
                    ],
                    output / "audit",
                    dict(os.environ),
                )
                if audit_code:
                    raise RuntimeError("validation audit failed; inspect cycle stderr")
                staged = json.loads((output / "staging/status.json").read_text())
                audit = json.loads((output / "audit/summary.json").read_text())
                if staged["paid_ready_candidates"] or audit["classification_ready"]:
                    raise ValueError("unexpected classification release in validation import")
                checkpoint = dict(
                    cycle=cycle,
                    observation=observed,
                    imported_at=datetime.now(UTC).isoformat(),
                    staged_run_id=staged["run_id"],
                    audited_run_id=audit["run_id"],
                    states=audit["states"],
                    paid_calls=0,
                )
                publish_status(checkpoint_path, checkpoint)
            supervisor = json.loads((campaign_root / "status.json").read_text())
            finished = supervisor.get("stage", "").startswith("finished")
            publish_status(
                state / "status.json",
                dict(
                    stage="finished" if finished else "waiting_for_new_results",
                    pid=os.getpid(),
                    current_observation=observed,
                    last_import=checkpoint,
                    paid_calls=0,
                    updated_at=datetime.now(UTC).isoformat(),
                ),
            )
            if args.once or finished:
                return
            time.sleep(60)
        publish_status(
            state / "status.json", dict(stage="deadline_reached", pid=os.getpid(), paid_calls=0)
        )


if __name__ == "__main__":
    main()
