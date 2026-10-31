"""Wait on a real Windows process handle, then import and run the latest worker code."""

import argparse
import ctypes
import json
import msvcrt
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]


def run(pid, state, command):
    state.mkdir(parents=True, exist_ok=True)
    with (state / "dependency.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle and kernel.GetLastError() != 87:
            raise OSError("previous process could not be observed")
        try:
            while handle:
                publish_status(
                    state / "status.json",
                    dict(
                        stage="waiting_for_previous_owner",
                        pid=os.getpid(),
                        dependency_pid=pid,
                        updated_at=datetime.now(UTC).isoformat(),
                        command=command,
                    ),
                )
                outcome = kernel.WaitForSingleObject(handle, 15000)
                if outcome == 0:
                    break
                if outcome != 258:
                    raise OSError("process wait failed; refusing an unverified start")
        finally:
            if handle:
                kernel.CloseHandle(handle)
        child = subprocess.run([sys.executable, "-u", *command], cwd=ROOT, check=False)
        (state / "child-exit.json").write_text(
            json.dumps(
                dict(returncode=child.returncode, observed_at=datetime.now(UTC).isoformat())
            ),
            encoding="utf-8",
        )
        return child.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-pid", type=int, required=True)
    parser.add_argument("--status-dir", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a Python script command is required")
    raise SystemExit(run(args.wait_pid, args.status_dir.resolve(), command))
