"""Replay newly published native evidence locally while metadata collection advances."""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from import_all_quota_lyrics import BASE, ROOT, run_job

from chart_observatory.runtime_status import publish_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    args = parser.parse_args()
    campaign = args.campaign_root.resolve()
    if not campaign.is_relative_to(ROOT / "data/runtime"):
        parser.error("campaign must remain in project data/runtime")
    config = json.loads((campaign / "campaign.json").read_text(encoding="utf-8"))
    deadline = datetime.fromisoformat(config["ends_at"])
    state = campaign / "native-replays"
    state.mkdir(exist_ok=True)
    signature, cycle = None, 0
    while datetime.now(UTC) < deadline:
        mapping = BASE / "native-display-metadata.json"
        current = hashlib.sha256(mapping.read_bytes()).hexdigest()
        if current != signature:
            cycle += 1
            output = state / f"cycle-{cycle:04d}"
            code = run_job(
                [
                    sys.executable,
                    "-u",
                    "scripts/replay_new_native_metadata.py",
                    "--base-root",
                    str(BASE),
                    "--state-root",
                    str(output),
                    "--since",
                    config["starts_at"],
                ],
                output,
                dict(os.environ),
            )
            if code:
                raise RuntimeError("native replay failed; inspect cycle logs")
            signature = current
        native = json.loads(
            (ROOT / "data/runtime/native-spotify-metadata-20261031/status.json").read_text()
        )
        finished = native.get("stage") in {
            "collected_pending_lyric_identity_review",
            "provider_access_paused",
            "time_window_ended_pending_metadata",
        }
        # A final publication can occur during replay. Process it before exiting.
        stable = hashlib.sha256(mapping.read_bytes()).hexdigest() == signature
        publish_status(
            state / "status.json",
            dict(
                stage="finished_pending_review" if finished and stable else "watching_metadata",
                pid=os.getpid(),
                cycle=cycle,
                network_requests=0,
                paid_calls=0,
                classification_ready=False,
                updated_at=datetime.now(UTC).isoformat(),
            ),
        )
        if finished and stable:
            return
        time.sleep(60)
    publish_status(state / "status.json", dict(stage="deadline_reached", paid_calls=0))


if __name__ == "__main__":
    main()
