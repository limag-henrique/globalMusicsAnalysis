"""Refresh article exports during one existing Windows collector run, then exit."""

import argparse
import ctypes
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from scrape_youtube_chart_titles import OUTPUT, write_json_atomic

ROOT = Path(__file__).resolve().parents[1]


def refresh():
    for script in ("report_web_chart_coverage.py", "export_web_chart_titles.py"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode:
            # Do not persist connection strings or exception text containing credentials.
            raise RuntimeError(f"{script} returned {result.returncode}")
        print(result.stdout.strip(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", required=True, type=int)
    args = parser.parse_args()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.WaitForSingleObject.restype = ctypes.c_ulong
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x00100000, False, args.pid)  # SYNCHRONIZE only
    if not handle:
        raise OSError(ctypes.get_last_error(), "Cannot monitor collector process")
    status_path = OUTPUT / "export_manifest.json"
    last_refresh = 0
    try:
        while True:
            ended = kernel.WaitForSingleObject(handle, 0) == 0
            if ended or time.monotonic() - last_refresh >= 300:
                status = {
                    "collector_pid": args.pid,
                    "collector_running": not ended,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
                try:
                    refresh()
                    status["export_status"] = "UPDATED"
                except (RuntimeError, subprocess.TimeoutExpired) as error:
                    status["export_status"] = "FAILED"
                    status["error"] = type(error).__name__
                    print(json.dumps(status), flush=True)
                write_json_atomic(status_path, status)
                last_refresh = time.monotonic()
                if ended:
                    break
            wait = kernel.WaitForSingleObject(handle, 60_000)
            if wait not in (0, 258):
                raise OSError(ctypes.get_last_error(), "Collector wait failed")
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()
