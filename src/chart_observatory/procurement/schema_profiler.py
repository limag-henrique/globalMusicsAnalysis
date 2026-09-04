from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import polars as pl


@dataclass(frozen=True)
class FieldProfile:
    path: str
    types: tuple[str, ...]
    observed_count: int
    null_count: int


@dataclass(frozen=True)
class SampleProfile:
    file_name: str
    sha256: str
    byte_length: int
    format: str
    row_count: int | None
    fields: tuple[FieldProfile, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _ObservedField:
    types: set[str]
    observed_count: int = 0
    null_count: int = 0


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _json_fields(payload: Any) -> tuple[FieldProfile, ...]:
    observed: defaultdict[str, _ObservedField] = defaultdict(
        lambda: _ObservedField(set())
    )

    def visit(value: Any, path: str) -> None:
        kind = _json_type(value)
        field = observed[path]
        field.types.add(kind)
        field.observed_count += 1
        field.null_count += int(value is None)

        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path != "$" else f"$.{key}"
                visit(child, child_path)
        elif isinstance(value, list):
            for child in value:
                visit(child, f"{path}[]")

    visit(payload, "$")
    return tuple(
        FieldProfile(
            path=path,
            types=tuple(sorted(field.types)),
            observed_count=field.observed_count,
            null_count=field.null_count,
        )
        for path, field in sorted(observed.items())
    )


def _table_fields(frame: pl.DataFrame) -> tuple[FieldProfile, ...]:
    return tuple(
        FieldProfile(
            path=column,
            types=(str(frame.schema[column]),),
            observed_count=frame.height,
            null_count=frame[column].null_count(),
        )
        for column in frame.columns
    )


def profile_sample(path: Path) -> SampleProfile:
    """Describe a local provider sample without retaining its record values."""
    raw = path.read_bytes()
    suffix = path.suffix.casefold()

    if suffix == ".csv":
        frame = pl.read_csv(path, try_parse_dates=True)
        format_name = "CSV"
        row_count: int | None = frame.height
        fields = _table_fields(frame)
    elif suffix == ".parquet":
        frame = pl.read_parquet(path)
        format_name = "PARQUET"
        row_count = frame.height
        fields = _table_fields(frame)
    elif suffix == ".json":
        payload = json.loads(raw)
        format_name = "JSON"
        row_count = len(payload) if isinstance(payload, list) else None
        fields = _json_fields(payload)
    else:
        raise ValueError(f"Unsupported sample format: {path.suffix or '<none>'}")

    return SampleProfile(
        file_name=path.name,
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_length=len(raw),
        format=format_name,
        row_count=row_count,
        fields=fields,
    )
