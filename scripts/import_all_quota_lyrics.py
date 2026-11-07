"""Supervise complete quota-candidate acquisition and pending-review import, without AI."""

import argparse
import hashlib
import json
import msvcrt
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031"
STORE = ROOT / "data/derived/lyrics/quota-20261030"


def run_job(command, directory, env):
    directory.mkdir(parents=True, exist_ok=True)
    with (
        (directory / "stdout.log").open("ab") as output,
        (directory / "stderr.log").open("ab") as errors,
    ):
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=errors,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        publish_status(
            directory / "process.json",
            dict(
                pid=process.pid,
                command=command,
                started_at=datetime.now(UTC).isoformat(),
            ),
        )
        code = process.wait()
    publish_status(
        directory / "exit.json", dict(returncode=code, finished_at=datetime.now(UTC).isoformat())
    )
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--hours", type=float, default=24)
    args = parser.parse_args()
    if not 0 < args.hours <= 24:
        parser.error("hours must be in (0,24]")
    state = args.state_root.resolve()
    if not state.is_relative_to((ROOT / "data/runtime").resolve()):
        parser.error("state must be inside project data/runtime")
    state.mkdir(parents=True, exist_ok=True)
    with (state / "supervisor.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        now = datetime.now(UTC)
        selection_raw = (BASE / "combined.jsonl").read_bytes()
        candidate_ids = {
            json.loads(line)["candidate_id"]
            for line in selection_raw.decode("utf-8").splitlines()
            if line
        }
        config_path = state / "campaign.json"
        if not config_path.exists():
            source = json.loads(
                (ROOT / "data/runtime/quota-supervisor-20261031/campaign.json").read_text()
            )
            config = dict(
                starts_at=now.isoformat(),
                ends_at=(now + timedelta(hours=args.hours)).isoformat(),
                frozen_inputs=source["frozen_inputs"],
                years=[2018, 2026],
                cutoff="2026-10-15",
                paid_calls_authorized=0,
                classification_ready=False,
                source_reference_is_analysis_input=False,
                candidate_count=len(candidate_ids),
                selection_sha256=hashlib.sha256(selection_raw).hexdigest(),
            )
            for relative, expected in config["frozen_inputs"].items():
                with (ROOT / relative).open("rb") as file:
                    if hashlib.file_digest(file, "sha256").hexdigest() != expected:
                        raise ValueError("frozen source changed: " + relative)
            publish_status(config_path, config)
        else:
            config = json.loads(config_path.read_text())
        remaining = (datetime.fromisoformat(config["ends_at"]) - now).total_seconds()
        if remaining <= 0:
            raise ValueError("campaign expired; inspect results before creating a new campaign")
        env = dict(
            os.environ,
            CHART_OBSERVATORY_CAMPAIGN_PATH=str(config_path),
            PYTHONIOENCODING="utf-8",
            POLARS_MAX_THREADS="2",
        )
        publish_status(
            state / "status.json", dict(stage="preparing_backup", pid=os.getpid(), paid_calls=0)
        )
        backup = state / "acquisition-before.sqlite"
        if not backup.exists():
            with (
                sqlite3.connect(
                    (STORE / "acquisition.sqlite").as_uri() + "?mode=ro", uri=True
                ) as source,
                sqlite3.connect(backup) as target,
            ):
                source.backup(target)
        with backup.open("rb") as file:
            backup_hash = hashlib.file_digest(file, "sha256").hexdigest()
        publish_status(state / "backup.json", dict(sha256=backup_hash, bytes=backup.stat().st_size))
        worker = [
            sys.executable,
            "-u",
            "scripts/autonomous_lyrics.py",
            "--base-root",
            str(BASE),
            "--state-root",
            str(state / "acquisition"),
            "--hours",
            str(min(args.hours, remaining / 3600)),
            "--rounds",
            "3",
            "--method-prefix",
            state.name,
        ]
        publish_status(
            state / "status.json",
            dict(
                stage="acquiring_all_candidates",
                pid=os.getpid(),
                total_candidates=len(candidate_ids),
                scope=(
                    "All frozen quota candidates; reuse existing texts "
                    "and recover absent/suspect texts"
                ),
                ends_at=config["ends_at"],
                paid_calls=0,
                classification_ready=False,
            ),
        )
        code = run_job(worker, state / "acquisition", env)
        publish_status(
            state / "status.json",
            dict(
                stage="staging_available_texts",
                pid=os.getpid(),
                acquisition_returncode=code,
                paid_calls=0,
                classification_ready=False,
            ),
        )
        stage_code = run_job(
            [
                sys.executable,
                "scripts/stage_quota_lyrics.py",
                "--base-root",
                str(BASE),
                "--state-root",
                str(state / "staging"),
            ],
            state / "staging",
            env,
        )
        audit_code = (
            run_job(
                [
                    sys.executable,
                    "scripts/audit_current_lyric_corpus.py",
                    "--output",
                    str(state / "final-audit"),
                ],
                state / "final-audit",
                env,
            )
            if stage_code == 0
            else None
        )
        publish_status(
            state / "status.json",
            dict(
                stage="finished_pending_human_validation"
                if code == stage_code == audit_code == 0
                else "finished_with_errors",
                pid=os.getpid(),
                acquisition_returncode=code,
                staging_returncode=stage_code,
                audit_returncode=audit_code,
                paid_calls=0,
                classification_ready=False,
                finished_at=datetime.now(UTC).isoformat(),
            ),
        )


if __name__ == "__main__":
    main()
