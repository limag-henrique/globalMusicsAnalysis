from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_manifests(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return []
    provider = str(payload.get("provider", ""))
    origin_platform = str(payload.get("origin_platform", ""))
    files = payload.get("files", [])
    if not isinstance(files, list):
        return []
    rows: list[dict[str, str]] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "provider": provider,
                "origin_platform": origin_platform,
                "filename": str(item.get("filename", "")),
                "status": str(item.get("status", "")),
                "countries": ";".join(_as_strings(item.get("countries"))),
                "row_count": _as_display(item.get("row_count")),
                "earliest_date": _as_display(item.get("earliest_date")),
                "latest_date": _as_display(item.get("latest_date")),
            }
        )
    return rows


def load_capabilities(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _as_strings(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return []


def _as_display(value: Any) -> str:
    return "" if value is None else str(value)
