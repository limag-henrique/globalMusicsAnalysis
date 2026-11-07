"""Replay only newly published native metadata candidates, using local responses only."""

import argparse
import hashlib
import json
import msvcrt
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.lyrics.native_replay_targets import recent_native_targets
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]


def run(base, state, since):
    state.mkdir(parents=True, exist_ok=True)
    with (state / "owner.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        selected_raw = (base / "combined.jsonl").read_bytes()
        selected_ids = {
            json.loads(line)["candidate_id"]
            for line in selected_raw.decode("utf-8").splitlines()
            if line.strip()
        }
        mapping_raw = (base / "native-display-metadata.json").read_bytes()
        targets = recent_native_targets(selected_ids, json.loads(mapping_raw), since)
        raw = "".join(json.dumps(row) + "\n" for row in targets).encode("utf-8")
        target_path = state / "candidate-ids.jsonl"
        target_path.write_bytes(raw)
        plan = dict(
            pid=os.getpid(),
            observed_at=datetime.now(UTC).isoformat(),
            since=since.isoformat(),
            selection_sha256=hashlib.sha256(selected_raw).hexdigest(),
            metadata_map_sha256=hashlib.sha256(mapping_raw).hexdigest(),
            filter_sha256=hashlib.sha256(raw).hexdigest(),
            candidates=len(targets),
            network_requests=0,
            paid_calls=0,
            ranking_changes=0,
        )
        publish_status(state / "plan.json", plan)
        if not targets:
            publish_status(state / "status.json", dict(plan, stage="no_new_native_metadata"))
            return 0
        publish_status(state / "status.json", dict(plan, stage="replaying_local_candidates"))
        child = subprocess.run(
            [
                sys.executable,
                "-u",
                str(ROOT / "scripts/replay_cached_quota_lyrics.py"),
                "--base-root",
                str(base),
                "--state-root",
                str(state / "replay"),
                "--candidate-ids-file",
                str(target_path),
                "--include-flagged",
            ],
            cwd=ROOT,
            check=False,
        )
        publish_status(
            state / "status.json",
            dict(
                plan,
                stage="finished_pending_import_and_review" if child.returncode == 0 else "failed",
                returncode=child.returncode,
            ),
        )
        return child.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--since", required=True, help="ISO timestamp including timezone")
    args = parser.parse_args()
    raise SystemExit(
        run(args.base_root.resolve(), args.state_root.resolve(), datetime.fromisoformat(args.since))
    )
