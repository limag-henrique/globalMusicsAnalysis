"""Import acquisition progress for human review without starting another collector."""

import argparse
import csv
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

from chart_observatory.ingestion.quota_boundary import validate_display_only_refresh
from chart_observatory.runtime_status import publish_status


def validate_campaign_selection(selected, config):
    if hashlib.sha256(selected).hexdigest() == config["selection_sha256"]:
        return
    # Older collectors rewrote display enrichment into combined.jsonl. Verify
    # the entire ranked selection independently from its frozen source files.
    import polars as pl

    from chart_observatory.ingestion.import_quotas import load_quotas, provisional_selection

    for relative, digest in config["frozen_inputs"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("frozen acquisition source changed")
    final = [
        {**json.loads(line), "selection_status": "CALENDAR_ELIGIBLE", "coverage_status": "COMPLETE"}
        for line in (BASE / "selection/selected.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    with (BASE / "sources/source_coverage.csv").open(encoding="utf-8-sig") as handle:
        coverage = list(csv.DictReader(handle))
    ranks = pl.read_parquet(BASE / "sources/rankings.parquet").to_dicts()
    provisional = provisional_selection(
        ranks, coverage, load_quotas(BASE / "sources/country_quotas.csv"), final
    )
    validate_display_only_refresh(
        [json.loads(line) for line in selected.decode("utf-8").splitlines() if line],
        final + provisional,
    )


def needs_refresh(previous, observed, elapsed_seconds):
    if not previous:
        return True
    if previous["fingerprint"] == observed["fingerprint"]:
        return False
    return (
        abs(observed["with_text"] - previous["with_text"]) >= 100
        or observed.get("offline_proposals", 0) > previous.get("offline_proposals", 0)
        or elapsed_seconds >= 1800
    )


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
    proposals = 0
    for path in sorted((STORE / "offline-replay").glob("*.json")):
        if path.name.endswith(".outcome.json"):
            continue
        raw = path.read_bytes()
        replay = json.loads(raw)
        if replay.get("payload", {}).get("recording_id") in candidate_ids:
            proposals += 1
            checksum.update(path.name.encode())
            checksum.update(raw)
    return dict(
        fingerprint=checksum.hexdigest(),
        candidates=count,
        with_text=with_text,
        without_text=count - with_text,
        offline_proposals=proposals,
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
    validate_campaign_selection(selected, config)
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
