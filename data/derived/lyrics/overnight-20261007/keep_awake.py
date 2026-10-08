"""Hold system sleep for this authorized run, for at most twelve hours."""

import ctypes
import json
import time
from pathlib import Path

status_path = Path(__file__).with_name("status.json")
end = time.monotonic() + 12 * 3600
kernel = ctypes.windll.kernel32
if not kernel.SetThreadExecutionState(0x80000001):
    raise RuntimeError("Cannot hold system sleep")
try:
    while time.monotonic() < end:
        state = json.loads(status_path.read_text(encoding="utf-8")).get("status", "")
        if state in {"completed", "budget_exhausted", "failed", "stopped"}:
            break
        time.sleep(30)
finally:
    kernel.SetThreadExecutionState(0x80000000)
