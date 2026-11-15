"""Import the explicit new global candidate delta through existing unpaid lyric recovery."""

import hashlib
import json
import msvcrt
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from import_all_quota_lyrics import run_job

from chart_observatory.lyrics.global_import import plan_global, seed_exact_native_results
from chart_observatory.lyrics.quota_acquisition import AcquisitionStore
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/global-2018-2026-20261108"
LEGACY = ROOT / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031"
STORE = ROOT / "data/derived/lyrics/global-20261108"
STATE = ROOT / "data/runtime/global-lyrics-20261108"
PREVIOUS = ROOT / "data/runtime/import-all-lyrics-20261108"


def report(stage, **extra):
    publish_status(
        STATE / "status.json",
        dict(stage=stage, pid=os.getpid(), paid_calls=0, classification_ready=False, **extra),
    )


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "owner.lock").open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            report("verifying_global_delta")
            tasks, delta, summary = plan_global(BASE, LEGACY)
            new = [p for p in tasks if p["recording_id"] in delta]
            if not 0 < len(new) <= 30000:
                raise ValueError("public acquisition requires a bounded explicit new-ID delta")
            ids = STATE / "new-candidates.jsonl"
            ids.write_text(
                "".join(json.dumps(dict(candidate_id=p["recording_id"])) + "\n" for p in new),
                encoding="utf-8",
            )
            manifest = json.loads((BASE / "manifest.json").read_text())
            frozen = {
                str((BASE / name).relative_to(ROOT)): digest
                for name, digest in manifest["output_hashes"].items()
            }
            frozen[str((BASE / "manifest.json").relative_to(ROOT))] = hashlib.sha256(
                (BASE / "manifest.json").read_bytes()
            ).hexdigest()
            frozen[str(ids.relative_to(ROOT))] = hashlib.sha256(ids.read_bytes()).hexdigest()
            config_path = STATE / "campaign.json"
            if not config_path.exists():
                previous = json.loads((PREVIOUS / "campaign.json").read_text())
                now = datetime.now(UTC)
                ends = max(now, datetime.fromisoformat(previous["ends_at"])) + timedelta(hours=12)
                publish_status(
                    config_path,
                    dict(
                        starts_at=now.isoformat(),
                        ends_at=ends.isoformat(),
                        frozen_inputs=frozen,
                        candidate_count=summary["unique_candidates"],
                        acquisition_scope_count=len(delta),
                        paid_calls_authorized=0,
                        explicit_user_requested_public_delta=True,
                        classification_ready=False,
                    ),
                )
            env = dict(
                os.environ,
                CHART_OBSERVATORY_CAMPAIGN_PATH=str(config_path),
                PYTHONIOENCODING="utf-8",
            )
            store = AcquisitionStore(STORE)
            reused = seed_exact_native_results(
                store, new, ROOT / "data/derived/lyrics/quota-20261030"
            )
            store.conn.close()
            publish_status(STATE / "intake.json", dict(**summary, reused_exact_native_ids=reused))
            report("recovering_global_delta_from_cache", selection=summary)
            replay = [
                sys.executable,
                "scripts/replay_cached_quota_lyrics.py",
                "--base-root",
                str(BASE),
                "--store-root",
                str(STORE),
                "--state-root",
                str(STATE / "offline"),
                "--candidate-ids-file",
                str(ids),
                "--include-flagged",
            ]
            if run_job(replay, STATE / "offline", env):
                raise RuntimeError("global offline recovery failed")
            stage = [
                sys.executable,
                "scripts/stage_quota_lyrics.py",
                "--base-root",
                str(BASE),
                "--store-root",
                str(STORE),
                "--state-root",
                str(STATE / "initial-staging"),
            ]
            report("staging_global_available_texts", selection=summary)
            if run_job(stage, STATE / "initial-staging", env):
                raise RuntimeError("global initial staging failed")
            previous_status = json.loads((PREVIOUS / "status.json").read_text())
            worker = [
                sys.executable,
                "scripts/autonomous_lyrics.py",
                "--base-root",
                str(BASE),
                "--store-root",
                str(STORE),
                "--state-root",
                str(STATE / "acquisition"),
                "--hours",
                "12",
                "--method-prefix",
                "global-delta-20261108",
                "--candidate-ids-file",
                str(ids),
                "--search-cache-max-age-hours",
                "6",
            ]
            if not previous_status.get("stage", "").startswith("finished"):
                worker.extend(["--wait-pid", str(previous_status["pid"])])
            report("waiting_and_acquiring_new_global_candidates", selection=summary)
            code = run_job(worker, STATE / "acquisition", env)
            stage[-1] = str(STATE / "final-staging")
            stage_code = run_job(stage, STATE / "final-staging", env)
            report(
                "finished_pending_identity_and_completeness"
                if code == stage_code == 0
                else "finished_with_errors",
                acquisition_returncode=code,
                staging_returncode=stage_code,
                selection=summary,
                finished_at=datetime.now(UTC).isoformat(),
            )
        except Exception as error:
            report("failed", error_type=type(error).__name__)
            raise


if __name__ == "__main__":
    main()
