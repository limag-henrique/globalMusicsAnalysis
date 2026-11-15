"""Resume unpaid global recovery serially with a new, immutable campaign window.

Existing stores and response evidence are preserved. Acquisition and current-web
comparison never run concurrently through this supervisor. No Vertex SDK is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import msvcrt
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, select, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.quota_staging import candidates, runs
from chart_observatory.pipeline_state import file_hash
from chart_observatory.research_flow import load_selection
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/global-2018-2026-20261108"
STORE = ROOT / "data/derived/lyrics/global-20261108"
WORKERS = (
    "autonomous_lyrics.py",
    "compare_all_lyrics_web.py",
    "import_all_quota_lyrics.py",
    "import_new_global_lyrics.py",
)


def active_workers():
    command = (
        "Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^python(w)?\\.exe$'} "
        "| Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    values = json.loads(result.stdout) if result.stdout.strip() else []
    values = [values] if isinstance(values, dict) else values
    return [
        {"pid": row["ProcessId"], "worker": name}
        for row in values
        if row["ProcessId"] != os.getpid()
        for name in WORKERS
        if name in (row.get("CommandLine") or "")
    ]


def snapshot_targets(base):
    _manifest, _cells, memberships, frozen = load_selection(base)
    wanted = {row["candidate_id"] for row in memberships}
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            run = conn.execute(
                select(runs.c.id)
                .where(runs.c.manifest["selection_root"].as_string() == str(base))
                .order_by(runs.c.created_at.desc(), runs.c.id.desc())
                .limit(1)
            ).scalar_one()
            records = (
                conn.execute(
                    select(
                        candidates.c.candidate_id, candidates.c.text_sha256, candidates.c.audit
                    ).where(candidates.c.run_id == run)
                )
                .mappings()
                .all()
            )
        ids = {row["candidate_id"] for row in records}
        if len(records) != len(ids) or ids != wanted:
            raise ValueError("staging candidate universe differs from frozen selection")
        targets = []
        for row in records:
            audit = row["audit"] or {}
            missing = row["text_sha256"] is None
            flagged = any(
                audit.get(key)
                for key in (
                    "text_quality_flags",
                    "source_quarantined",
                    "shared_text_identity_collision",
                    "identity_conflict",
                    "suspected_partial",
                )
            )
            if missing or flagged:
                targets.append(
                    {
                        "candidate_id": row["candidate_id"],
                        "reason": "text_missing" if missing else "quality_flagged",
                    }
                )
        return run, sorted(targets, key=lambda row: row["candidate_id"]), frozen
    finally:
        engine.dispose()


def freeze_campaign(state, base, *, hours, now=None, snapshot=snapshot_targets):
    if not 0 < hours <= 24:
        raise ValueError("campaign acquisition window must be in (0,24] hours")
    campaign_path = state / "campaign.json"
    if campaign_path.exists():
        campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
        if campaign["selection_root"] != str(base):
            raise ValueError("existing campaign belongs to a different selection")
        return campaign
    run, targets, frozen = snapshot(base)
    state.mkdir(parents=True, exist_ok=True)
    target_path = state / "candidate-ids.jsonl"
    target_path.write_text("".join(json.dumps(row) + "\n" for row in targets), encoding="utf-8")
    frozen[str(target_path)] = file_hash(target_path)
    now = now or datetime.now(UTC)
    campaign = dict(
        protocol="global-recovery-resume-v1",
        selection_root=str(base),
        staging_run_id=run,
        starts_at=now.isoformat(),
        ends_at=(now + timedelta(hours=hours)).isoformat(),
        frozen_inputs={
            str(Path(path).relative_to(ROOT)): digest for path, digest in frozen.items()
        },
        candidate_count=len(targets),
        scope="missing_or_quality_flagged_only",
        paid_calls_authorized=0,
        classification_ready=False,
        preserve_prior_campaigns=True,
    )
    publish_status(campaign_path, campaign)
    return campaign


def verify_campaign(campaign):
    for relative, digest in campaign["frozen_inputs"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or file_hash(path) != digest:
            raise ValueError("frozen recovery campaign input changed")
    if datetime.fromisoformat(campaign["ends_at"]) <= datetime.now(UTC):
        raise ValueError("campaign expired; preserve it and create an explicit new state root")


def run_job(command, directory, env):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "stdout.log").open("ab") as out, (directory / "stderr.log").open("ab") as err:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=out,
            stderr=err,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        publish_status(
            directory / "process.json",
            {
                "pid": process.pid,
                "command": command,
                "started_at": datetime.now(UTC).isoformat(),
            },
        )
        code = process.wait()
    publish_status(
        directory / "exit.json", {"returncode": code, "finished_at": datetime.now(UTC).isoformat()}
    )
    if code:
        raise RuntimeError("collector exited with a nonzero status; inspect private phase logs")


def phase_succeeded(directory):
    path = directory / "exit.json"
    return path.is_file() and json.loads(path.read_text(encoding="utf-8"))["returncode"] == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--base-root", type=Path, default=BASE)
    parser.add_argument("--store-root", type=Path, default=STORE)
    parser.add_argument("--hours", type=float, default=12)
    parser.add_argument("--comparison-hours", type=float, default=12)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    state, base, store = [
        path.resolve() for path in (args.state_root, args.base_root, args.store_root)
    ]
    if (
        not state.is_relative_to(ROOT / "data/runtime")
        or not base.is_relative_to(ROOT / "data/derived/annual_revision")
        or not store.is_relative_to(ROOT / "data/derived/lyrics")
        or not 0 < args.comparison_hours <= 24
    ):
        parser.error("use project runtime/selection/store paths and a bounded comparison window")
    state.mkdir(parents=True, exist_ok=True)
    with (ROOT / "data/runtime/research-provider-recovery.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)

        def status(stage, **extra):
            publish_status(
                state / "status.json",
                {
                    "stage": stage,
                    "pid": os.getpid(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "paid_calls": 0,
                    "classification_ready": False,
                    **extra,
                },
            )

        try:
            existing = active_workers()
            if existing:
                status("blocked_by_existing_collector", workers=existing)
                return 2
            status("freezing_current_missing_candidate_scope")
            campaign = freeze_campaign(state, base, hours=args.hours)
            verify_campaign(campaign)
            status(
                "prepared",
                candidates=campaign["candidate_count"],
                staging_run_id=campaign["staging_run_id"],
            )
            if args.prepare_only:
                return 0
            env = dict(
                os.environ,
                CHART_OBSERVATORY_CAMPAIGN_PATH=str(state / "campaign.json"),
                PYTHONIOENCODING="utf-8",
            )
            acquisition = state / "acquisition"
            if not phase_succeeded(acquisition) and campaign["candidate_count"]:
                status(
                    "recovering_missing_or_flagged_lyrics", candidates=campaign["candidate_count"]
                )
                run_job(
                    [
                        sys.executable,
                        "scripts/autonomous_lyrics.py",
                        "--base-root",
                        str(base),
                        "--store-root",
                        str(store),
                        "--state-root",
                        str(acquisition),
                        "--hours",
                        str(args.hours),
                        "--candidate-ids-file",
                        str(state / "candidate-ids.jsonl"),
                        "--method-prefix",
                        "resume-" + hashlib.sha256(str(state).encode()).hexdigest()[:12],
                        "--search-cache-max-age-hours",
                        "24",
                    ],
                    acquisition,
                    env,
                )
            status("comparing_current_web_sources")
            comparison = state / "comparison"
            if not phase_succeeded(comparison):
                run_job(
                    [
                        sys.executable,
                        "scripts/compare_all_lyrics_web.py",
                        "--base-root",
                        str(base),
                        "--store-root",
                        str(store),
                        "--state-root",
                        str(comparison),
                        "--hours",
                        str(args.comparison_hours),
                    ],
                    comparison,
                    env,
                )
            status("finished_pending_scientific_reviews")
            return 0
        except Exception as exc:
            status("failed", error_type=type(exc).__name__)
            raise
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    raise SystemExit(main())
