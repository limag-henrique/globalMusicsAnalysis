"""Deterministic source-artifact freeze for the scientific corpus."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from chart_observatory.corpus.eligibility import EligibilityRules


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(path: Path, *, rows: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": str(path),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }
    if rows is not None:
        payload["rows"] = rows
    return payload


def _date_text(value: object) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def freeze_source_artifacts(
    observations: Path,
    coverage: Path,
    output: Path,
    *,
    analytical_datasets: tuple[Path, ...] = (),
    rules: EligibilityRules | None = None,
    name: str = "CANONICAL_CORPUS",
    version: str = "v1",
) -> dict[str, Any]:
    """Freeze the immutable, file-backed source layer before DB membership freeze.

    The manifest is deterministic except for ``frozen_at`` and records every hash
    needed to reproduce the comparable panel. It intentionally does not claim that
    PostgreSQL membership rows exist; that state is completed by ``corpus freeze``.
    """
    for path in (observations, coverage, *analytical_datasets):
        if not path.is_file():
            raise FileNotFoundError(path)

    coverage_frame = pl.read_parquet(coverage)
    eligible = coverage_frame.filter(pl.col("eligible"))
    if eligible.height == 0:
        raise ValueError("coverage file contains no eligible cells")
    dates = [value for value in eligible["first_date"].to_list() if value is not None]
    ends = [value for value in eligible["last_date"].to_list() if value is not None]
    rules = rules or EligibilityRules()

    datasets: list[dict[str, Any]] = []
    for dataset in analytical_datasets:
        datasets.append(_artifact(dataset, rows=pl.read_parquet(dataset).height))

    canonical_payload: dict[str, Any] = {
        "name": name,
        "version": version,
        "status": "FROZEN",
        "freeze_kind": "SOURCE_ARTIFACTS_ONLY",
        "operational_membership_status": "PENDING_POSTGRESQL_LOAD",
        "rules": {
            "minimum_coverage": rules.minimum_coverage,
            "minimum_years": rules.minimum_years,
            "minimum_chart_depth": rules.minimum_chart_depth,
            "minimum_source_quality": rules.minimum_source_quality,
        },
        "observations": _artifact(
            observations,
            rows=pl.scan_parquet(observations).select(pl.len()).collect().item(),
        ),
        "coverage": _artifact(coverage, rows=coverage_frame.height),
        "analytical_datasets": datasets,
        "total_cells": coverage_frame.height,
        "eligible_cells": eligible.height,
        "eligible_markets": sorted(eligible["country_code"].unique().to_list()),
        "date_start": _date_text(min(dates)),
        "date_end": _date_text(max(ends)),
    }
    manifest_sha256 = hashlib.sha256(
        json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest = {
        **canonical_payload,
        "manifest_sha256": manifest_sha256,
        "frozen_at": datetime.now(UTC).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
