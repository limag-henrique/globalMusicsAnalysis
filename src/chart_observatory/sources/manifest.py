from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from chart_observatory.sources.models import SourceManifest


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_default(value: Any) -> str:
    if isinstance(value, (Path, date)):
        return value.isoformat()
    raise TypeError(f"unsupported manifest value: {type(value)!r}")


def write_manifest(manifest: SourceManifest, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(manifest), default=_json_default, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
