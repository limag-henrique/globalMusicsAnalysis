"""Small resumable stage ledger: hashes, checkpoints, counters and bounded retries."""

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def file_hash(path):
    path = Path(path)
    if not path.is_file():
        return None
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def input_hashes(inputs):
    values = {role: file_hash(path) for role, path in sorted(inputs.items())}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest(), values


def process_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied is not proof of termination.
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259)
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False


@dataclass
class StageResult:
    status: str
    counters: dict = field(default_factory=dict)
    checkpoint: dict = field(default_factory=dict)
    files: list = field(default_factory=list)
    reason: str | None = None


class StageRunner:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "stages.sqlite"
        with sqlite3.connect(self.path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS stages(
                name TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,status TEXT NOT NULL,
                attempts INTEGER NOT NULL,owner_pid INTEGER,record_json TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS stage_history(
                id INTEGER PRIMARY KEY,name TEXT NOT NULL,record_json TEXT NOT NULL)""")

    def records(self):
        with sqlite3.connect(self.path) as conn:
            return {
                name: json.loads(record)
                for name, record in conn.execute("SELECT name,record_json FROM stages")
            }

    def run(self, name, inputs, action, *, retry_failed=False):
        inputs = {**inputs, "stage_engine": Path(__file__)}
        fingerprint, hashes = input_hashes(inputs)
        with sqlite3.connect(self.path, timeout=15) as conn:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute("SELECT * FROM stages WHERE name=?", (name,)).fetchone()
            record = json.loads(previous[5]) if previous else {}
            if previous and previous[2] == "running" and process_alive(previous[4]):
                return {**record, "busy": True, "cached": True}
            if previous and previous[1] == fingerprint:
                intact = all(
                    file_hash(path) == digest for path, digest in record.get("outputs", {}).items()
                )
                if intact and previous[2] in {"completed", "completed_with_deficits", "blocked"}:
                    return {**record, "cached": True}
                if previous[2] == "failed" and (not retry_failed or previous[3] >= 3):
                    return {**record, "cached": True, "retry_requires_action": True}
                attempt = previous[3] + 1
            else:
                attempt = 1
            pending = {
                "name": name,
                "status": "running",
                "fingerprint": fingerprint,
                "input_hashes": hashes,
                "attempt": attempt,
            }
            conn.execute(
                "INSERT OR REPLACE INTO stages VALUES (?,?,?,?,?,?)",
                (name, fingerprint, "running", attempt, os.getpid(), json.dumps(pending)),
            )
        output = self.root / "artifacts" / name / (fingerprint[:12] + "-" + str(uuid4())[:8])
        output.mkdir(parents=True)
        try:
            result = action(output, record.get("checkpoint", {}))
            if result.status not in {"completed", "completed_with_deficits", "blocked", "running"}:
                raise ValueError("unknown stage outcome")
            data = {
                **pending,
                "status": result.status,
                "counters": result.counters,
                "checkpoint": result.checkpoint,
                "reason": result.reason,
            }
            data["inputs_changed_during_stage"] = input_hashes(inputs)[0] != fingerprint
            if data["inputs_changed_during_stage"] and data["status"].startswith("completed"):
                data["status"] = "running"
                data["reason"] = "input changed; a stable checkpoint is still required"
            files = result.files
        except Exception as exc:
            # Never persist connection strings, authorization headers or arbitrary tracebacks.
            data = {
                **pending,
                "status": "failed",
                "error_type": type(exc).__name__,
                "checkpoint": record.get("checkpoint", {}),
                "counters": {},
            }
            files = []
        data["observed_at"] = datetime.now(UTC).isoformat()
        report = output / "report.json"
        report.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        data["outputs"] = {str(path): file_hash(path) for path in [*files, report]}
        with sqlite3.connect(self.path, timeout=15) as conn:
            payload = json.dumps(data, sort_keys=True, default=str)
            conn.execute(
                "UPDATE stages SET status=?,owner_pid=NULL,record_json=? WHERE name=?",
                (data["status"], payload, name),
            )
            conn.execute(
                "INSERT INTO stage_history(name,record_json) VALUES (?,?)", (name, payload)
            )
        return {**data, "cached": False}
