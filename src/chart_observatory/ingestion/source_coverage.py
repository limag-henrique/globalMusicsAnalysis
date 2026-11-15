"""Normalize and validate source coverage records before serialization."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

REQUIRED_FIELDS = frozenset(
    {
        "country_code",
        "year",
        "platform",
        "provider",
        "expected_periods",
        "collected_periods",
        "coverage_status",
    }
)


def normalize_source_coverage(*sources: object) -> list[dict[str, Any]]:
    """Concatenate source coverage rows and reject malformed records."""
    normalized: list[dict[str, Any]] = []
    for source_index, source in enumerate(sources):
        if not isinstance(source, list):
            raise TypeError(f"source_coverage[{source_index}] must be a list")
        for row_index, row in enumerate(source):
            if not isinstance(row, Mapping):
                raise TypeError(f"source_coverage[{source_index}][{row_index}] must be an object")
            record = dict(row)
            missing = REQUIRED_FIELDS - record.keys()
            if missing:
                raise ValueError(
                    f"source_coverage[{source_index}][{row_index}] missing fields: "
                    + ", ".join(sorted(missing))
                )
            if (
                not isinstance(record["country_code"], str)
                or type(record["year"]) is not int
                or not isinstance(record["platform"], str)
                or not isinstance(record["provider"], str)
                or type(record["expected_periods"]) is not int
                or type(record["collected_periods"]) is not int
                or not isinstance(record["coverage_status"], str)
            ):
                raise TypeError(
                    f"source_coverage[{source_index}][{row_index}] has invalid field types"
                )
            normalized.append(record)
    return normalized
