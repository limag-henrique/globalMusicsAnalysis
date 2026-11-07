"""Durable Windows supervisor. No AI, paid calls, ranking edits or process termination."""

import argparse
import ctypes
import json
import msvcrt
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.quota_campaign import campaign, remaining_seconds, verify_frozen_inputs
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data/runtime/quota-supervisor-20261031"
BASE = "data/derived/annual_revision/reconciled-russia-2018-2026-20261031"
PYTHON = ROOT / ".venv/Scripts/python.exe"
FLAGS = subprocess.CREATE_NO_WINDOW


def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def inventory():
    # Read-only CIM: includes creation time and command; never infer death from a timeout.
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); "
            "@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' } | "
            "Select-Object ProcessId,CreationDate,CommandLine) | ConvertTo-Json -Compress",
        ],
        capture_output=True,
        check=True,
        timeout=45,
        creationflags=FLAGS,
    )
    return json.loads(result.stdout.decode("utf-8-sig")) or []


def active(processes, needle):
    root = str(ROOT).casefold()
    return [
        p
        for p in processes
        if root in (p.get("CommandLine") or "").casefold()
        and needle in (p.get("CommandLine") or "")
    ]


def jobs():
    return [
        (
            "native",
            "collect_native_spotify_metadata.py",
            ["scripts/collect_native_spotify_metadata.py", "--base-root", BASE, "--hours", "8"],
            ROOT / "data/runtime/native-spotify-metadata-20261031/status.json",
        ),
        (
            "duration",
            "priority-native-durations-20261031",
            read(ROOT / "data/runtime/priority-native-durations-20261031/dependency/status.json")[
                "command"
            ],
            ROOT / "data/runtime/priority-native-durations-20261031/dependency/child-exit.json",
        ),
        (
            "replay",
            "offline-after-priority-native-20261031",
            read(
                ROOT / "data/runtime/offline-after-priority-native-20261031/dependency/status.json"
            )["command"],
            ROOT / "data/runtime/offline-after-priority-native-20261031/dependency/child-exit.json",
        ),
        (
            "stage",
            "scripts/stage_quota_lyrics.py",
            ["scripts/stage_quota_lyrics.py", "--base-root", BASE],
            STATE / "stage-result.json",
        ),
        (
            "coverage",
            "scripts/report_quota_staging_coverage.py",
            ["scripts/report_quota_staging_coverage.py"],
            STATE / "coverage-result.json",
        ),
    ]


def tick(checkpoint, processes, launch):
    actions = []
    for name, needle, command, proof in jobs():
        if checkpoint.get(name) == "done":
            continue
        owners = active(processes, needle)
        if owners:
            actions.append(dict(job=name, stage="observing_existing", processes=owners))
            break
        evidence = read(STATE / f"{name}-result.json") or read(proof)
        if evidence.get("returncode", 0) != 0:
            raise RuntimeError(f"{name}: previous worker failed; inspect {proof}")
        terminal = (
            "returncode" in evidence
            if name != "native"
            else evidence.get("stage")
            in {
                "collected_pending_lyric_identity_review",
                "provider_access_paused",
                "time_window_ended_pending_metadata",
            }
        )
        if terminal:
            checkpoint[name] = "done"
            continue
        if name == "native" and evidence.get("stage") == "waiting_provider_cooldown":
            deadline = evidence.get("resume_not_before")
            if deadline and datetime.fromisoformat(deadline) > datetime.now(UTC):
                actions.append(dict(job=name, stage="respecting_provider_cooldown"))
                break
        actions.append(dict(job=name, stage="ready_to_resume", command=command))
        if launch:
            execute(name, command)
            checkpoint[name] = "done"
        break

    owners = active(processes, "scripts/autonomous_lyrics.py")
    if owners:
        actions.append(dict(job="lyrics", stage="observing_existing", processes=owners))
    elif launch:
        remaining = remaining_seconds()
        if remaining is not None and remaining <= 0:
            actions.append(dict(job="lyrics", stage="campaign_deadline_reached"))
            return actions
        previous_cycle = checkpoint.get("lyrics_cycle", 0)
        if previous_cycle:
            result = read(STATE / f"lyrics-{previous_cycle:04d}-result.json")
            previous = read(
                ROOT
                / "data/runtime/supervised-lyrics-20261031"
                / f"cycle-{previous_cycle:04d}/status.json"
            )
            failed = result.get("returncode", 0) or previous.get("stage") in {
                "failed",
                "finished_with_staging_error",
            }
            if failed:
                transient = previous.get("error_type") in {
                    "OperationalError",
                    "ReadTimeout",
                    "ConnectTimeout",
                    "TimeoutError",
                    "ConnectionError",
                    "OSError",
                    "PermissionError",
                }
                retries = checkpoint.get("transient_restarts", 0)
                if not transient or retries >= 3:
                    raise RuntimeError(
                        "lyrics: failed worker requires review; preserved all evidence"
                    )
                if checkpoint.get("failed_cycle_seen") != previous_cycle:
                    checkpoint["failed_cycle_seen"] = previous_cycle
                    checkpoint["retry_not_before"] = time.time() + 300
                if time.time() < checkpoint["retry_not_before"]:
                    actions.append(dict(job="lyrics", stage="transient_failure_cooldown"))
                    return actions
                checkpoint["transient_restarts"] = retries + 1
            elif (
                previous.get("stage") == "finished_with_pending_reviews"
                and checkpoint.get("reported_cycle") != previous_cycle
            ):
                execute("coverage", ["scripts/report_quota_staging_coverage.py"])
                execute("scope-audit", ["scripts/audit_quota_analysis_scope.py"])
                checkpoint["reported_cycle"] = previous_cycle
        verify_frozen_inputs()
        # New bounded runs retain acquisition history and all provider cache/cooldowns.
        cycle = checkpoint.get("lyrics_cycle", 0) + 1
        state = f"data/runtime/supervised-lyrics-20261031/cycle-{cycle:04d}"
        command = [
            "scripts/autonomous_lyrics.py",
            "--hours",
            str(min(8, remaining / 3600) if remaining is not None else 8),
            "--base-root",
            BASE,
            "--state-root",
            state,
            "--method-prefix",
            f"supervised-v2-{cycle}",
        ]
        checkpoint["lyrics_cycle"] = cycle
        publish_status(STATE / "checkpoint.json", checkpoint)
        # Detached worker is discovered by command + creation time on the next tick.
        with (STATE / f"lyrics-{cycle:04d}.log").open("ab") as log:
            subprocess.Popen(
                [
                    str(PYTHON),
                    "-u",
                    str(Path(__file__).resolve()),
                    "--worker",
                    f"lyrics-{cycle:04d}",
                    "--",
                    *command,
                ],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=FLAGS,
            )
        actions.append(dict(job="lyrics", stage="started", state_root=state))
    else:
        actions.append(dict(job="lyrics", stage="ready_to_resume"))
    return actions


def execute(name, command):
    with (STATE / f"{name}.log").open("ab") as log:
        result = subprocess.run(
            [str(PYTHON), "-u", *command],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=FLAGS,
        )
    publish_status(STATE / f"{name}-result.json", dict(returncode=result.returncode))
    if result.returncode:
        raise RuntimeError(f"{name}: exit {result.returncode}; inspect local log")


def ensure_chart_discovery(processes):
    script = "scripts/discover_quota_chart_gaps.py"
    state = ROOT / "data/runtime/chart-gap-discovery-20261101"
    if (state / "checkpoint.json").exists():
        with (state / "reports.log").open("ab") as log:
            subprocess.run(
                [str(PYTHON), script, "--report-only"],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                creationflags=FLAGS,
            )
    if active(processes, script):
        return
    status = read(state / "status.json")
    if status.get("stage") == "attention_required":
        return
    retry = False
    if status.get("stage") == "finished_with_pending_ranking_review":
        checkpoint = read(state / "checkpoint.json")
        history = read(state / "timeout-retry-history.json") or []
        elapsed = (datetime.now(UTC) - datetime.fromisoformat(status["updated_at"])).total_seconds()
        retry = (
            len(history) < 2
            and elapsed >= 6 * 3600
            and any(v.get("error") == "TimeoutError" for v in checkpoint.values())
        )
        if not retry:
            return
    state.mkdir(parents=True, exist_ok=True)
    with (state / "stdout.log").open("ab") as stdout, (state / "stderr.log").open("ab") as stderr:
        subprocess.Popen(
            [str(PYTHON), "-u", script, "--hours", "8", *(["--retry-timeouts"] if retry else [])],
            cwd=ROOT,
            stdout=stdout,
            stderr=stderr,
            creationflags=FLAGS,
        )


def main(once=False):
    STATE.mkdir(parents=True, exist_ok=True)
    if (STATE / "safety-hold.json").exists():
        return
    with (STATE / "owner.lock").open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return  # A watchdog invocation must adopt the existing owner, never duplicate it.
        verify_frozen_inputs()
        # A process-scoped request prevents idle sleep; no persistent power-plan changes.
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        while True:
            checkpoint = read(STATE / "checkpoint.json")
            try:
                processes = inventory()
                remaining = remaining_seconds()
                if not once and (remaining is None or remaining > 0):
                    ensure_chart_discovery(processes)
                actions = tick(checkpoint, processes, not once)
                publish_status(STATE / "checkpoint.json", checkpoint)
                publish_status(
                    STATE / "status.json",
                    dict(
                        stage="monitoring",
                        pid=os.getpid(),
                        updated_at=datetime.now(UTC).isoformat(),
                        actions=actions,
                        paid_calls=0,
                        classification_ready=False,
                        campaign=campaign(),
                    ),
                )
                if (
                    remaining is not None
                    and remaining <= 0
                    and not active(processes, "scripts/autonomous_lyrics.py")
                ):
                    execute("coverage", ["scripts/report_quota_staging_coverage.py"])
                    execute("scope-audit", ["scripts/audit_quota_analysis_scope.py"])
                    publish_status(
                        STATE / "campaign-finished.json",
                        dict(
                            stage="time_budget_finished_pending_scientific_review",
                            updated_at=datetime.now(UTC).isoformat(),
                            classification_ready=False,
                        ),
                    )
                    return
            except Exception as exc:
                publish_status(
                    STATE / "attention-required.json",
                    dict(
                        stage="attention_required",
                        error_type=type(exc).__name__,
                        error=str(exc),
                        updated_at=datetime.now(UTC).isoformat(),
                    ),
                )
                if isinstance(
                    exc,
                    (
                        subprocess.TimeoutExpired,
                        subprocess.CalledProcessError,
                        ConnectionError,
                        OSError,
                    ),
                ):
                    time.sleep(60)
                    continue
                # Scientific/integrity failures remain blocked across watchdog restarts.
                publish_status(
                    STATE / "safety-hold.json",
                    dict(
                        error_type=type(exc).__name__,
                        error=str(exc),
                        updated_at=datetime.now(UTC).isoformat(),
                    ),
                )
                raise
            if once:
                return
            time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect-once", action="store_true")
    parser.add_argument("--worker")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.worker:
        execute(args.worker, args.command[1:] if args.command[:1] == ["--"] else args.command)
    else:
        main(args.inspect_once)
