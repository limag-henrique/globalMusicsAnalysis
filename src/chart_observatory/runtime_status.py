"""Best-effort atomic telemetry; file observers must not stop durable research work."""

import json
import os
import sys
import time
from contextlib import suppress
from pathlib import Path


def publish_status(path: Path, payload: dict, *, attempts: int = 20) -> bool:
    """Retry transient Windows sharing failures, preserving the last complete status."""
    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    part = path.with_name(f"{path.name}.{os.getpid()}.part")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        part.write_text(encoded, encoding="utf-8")
        for attempt in range(attempts):
            try:
                part.replace(path)
                return True
            except PermissionError:
                if attempt + 1 == attempts:
                    raise
                time.sleep(0.05)
    except OSError as exc:
        print(
            f"Status publication deferred ({type(exc).__name__}); durable work continues.",
            file=sys.stderr,
            flush=True,
        )
    finally:
        with suppress(OSError):
            part.unlink(missing_ok=True)
    return False
