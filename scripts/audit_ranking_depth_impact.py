"""Independently audit Top-K depth for a frozen selection and its legacy predecessor."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

import polars as pl
from sqlalchemy import create_engine, func, select

from chart_observatory.ingestion.global_annual import (
    cells_table,
    countries_table,
    memberships_table,
    persist,
)
from chart_observatory.ingestion.quota_boundary import validate_quota_memberships

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v3-final"
LEGACY = ROOT / "data/derived/annual_revision/global-2018-2026-20261108"
KAGGLE = (
    ROOT / "data/derived/annual_revision/backfill-2018-2026-20261030/sources/kaggle_daily.parquet"
)
MGD_MANIFEST = ROOT / "research/mgd_source_manifest.json"
CUTOFF = date(2026, 10, 15)


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_csv(path: Path, rows: list[dict], columns: list[str]):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def source_short_days() -> tuple[dict[str, Counter], dict[str, str]]:
    kaggle_short = (
        pl.scan_parquet(KAGGLE)
        .filter(pl.col("period_end") <= CUTOFF)
        .group_by("country_code", "period_end")
        .agg(pl.col("native_id").n_unique().alias("unique_tracks"))
        .filter(pl.col("unique_tracks") < 200)
        .collect(engine="streaming")
    )
    short: dict[str, Counter] = {"KAGGLE_GONZALOPEZGIL_V151": Counter()}
    for row in kaggle_short.iter_rows(named=True):
        short["KAGGLE_GONZALOPEZGIL_V151"][(row["country_code"], row["period_end"].year)] += 1

    mgd_inventory = read_json(MGD_MANIFEST)
    files = []
    mgd_file_hashes = {}
    for entry in mgd_inventory["files"]:
        path = (ROOT / entry["path"]).resolve()
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise ValueError(f"MGD native file hash mismatch: {entry['path']}")
        files.append(path)
        mgd_file_hashes[entry["path"]] = entry["sha256"]
    native = pl.concat(
        [
            pl.scan_csv(str(path), separator=chr(9), infer_schema_length=100)
            .select("ID", "Date", "Chart", "market")
            .filter(pl.col("Chart") == "Top 200")
            for path in files
        ]
    )
    mgd_short = (
        native.with_columns(pl.col("Date").str.to_date(strict=False).alias("period"))
        .filter(pl.col("period").is_not_null() & (pl.col("period") <= CUTOFF))
        .group_by(pl.col("market").str.to_uppercase().alias("country_code"), "period")
        .agg(pl.col("ID").n_unique().alias("unique_tracks"))
        .filter(pl.col("unique_tracks") < 200)
        .collect(engine="streaming")
    )
    short["MGD"] = Counter()
    for row in mgd_short.iter_rows(named=True):
        short["MGD"][(row["country_code"], row["period"].year)] += 1
    return short, mgd_file_hashes


def main():
    v3_manifest = read_json(V3 / "manifest.json")
    for name, digest in v3_manifest["source_hashes"].items():
        if sha256(ROOT / name) != digest:
            raise ValueError(f"v3 source hash mismatch: {name}")
    for name, digest in v3_manifest["implementation_hashes"].items():
        if sha256(ROOT / name) != digest:
            raise ValueError(f"v3 implementation hash mismatch: {name}")
    for name, digest in v3_manifest["output_hashes"].items():
        if sha256(V3 / name) != digest:
            raise ValueError(f"v3 output hash mismatch: {name}")

    countries = read_json(V3 / "countries.json")
    cells = read_rows(V3 / "country_years.jsonl")
    members = read_rows(V3 / "combined.jsonl")
    quotas = {
        country["country_code"]: country["quota_per_year_main"]
        for country in countries
        if country["quota_per_year_main"] is not None
    }
    validate_quota_memberships(members, quotas)
    expected_cells = {
        (country["country_code"], year) for country in countries for year in range(2018, 2027)
    }
    if (
        len(cells) != len(expected_cells)
        or {(cell["country_code"], cell["year"]) for cell in cells} != expected_cells
    ):
        raise ValueError("v3 country/year matrix is incomplete or duplicated")

    receipt = read_json(V3 / "local_import.json")
    run_id = receipt["run_id"]
    local_engine = create_engine(f"sqlite:///{(V3 / 'global_annual.sqlite3').as_posix()}")
    try:
        for table, source, keys in [
            (countries_table, countries, ("country_code",)),
            (cells_table, cells, ("country_code", "year")),
            (memberships_table, members, ("country_code", "year", "position")),
        ]:
            with local_engine.connect() as connection:
                count = connection.execute(
                    select(func.count()).select_from(table).where(table.c.run_id == run_id)
                ).scalar_one()
                actual = (
                    connection.execute(
                        select(table.c.payload)
                        .where(table.c.run_id == run_id)
                        .order_by(*(table.c[key] for key in keys))
                    )
                    .scalars()
                    .all()
                )
            expected = sorted(source, key=lambda row: tuple(row[key] for key in keys))
            if count != len(source) or actual != expected:
                raise ValueError(f"v3 local SQLite payload mismatch: {table.name}")
        repeated = persist(
            local_engine,
            v3_manifest,
            {
                "countries": countries,
                "cells": cells,
                "memberships": members,
                "new_definitive_memberships": v3_manifest["new_definitive_memberships"],
                "new_provisional_memberships": v3_manifest["new_provisional_memberships"],
            },
        )
        if repeated["inserted"] or repeated["run_id"] != run_id:
            raise ValueError("v3 local SQLite persistence is not idempotent")
    finally:
        local_engine.dispose()

    member_counts = Counter(
        (row["country_code"], row["year"], row["platform"], row["provider"]) for row in members
    )
    coverage = read_json(V3 / "source_coverage.json")
    depth_rows = []
    for row in coverage:
        if row.get("expected_depth") is None:
            continue
        depth_rows.append(
            {
                "country_code": row["country_code"],
                "year": row["year"],
                "platform": row["platform"],
                "provider": row["provider"],
                "coverage_status": row["coverage_status"],
                "expected_periods": row["expected_periods"],
                "collected_periods": row["collected_periods"],
                "expected_depth": row["expected_depth"],
                "minimum_source_rows_per_period": row.get("minimum_source_rows_per_period"),
                "minimum_unique_tracks_per_period": row.get("minimum_unique_tracks_per_period"),
                "depth_shortfall_periods": row.get("depth_shortfall_periods", 0),
                "rank_invalid_observations": row.get("rank_invalid_observations", 0),
                "rank_start_missing_periods": row.get("rank_start_missing_periods", 0),
                "selected_memberships": member_counts[
                    (row["country_code"], row["year"], row["platform"], row["provider"])
                ],
            }
        )
    depth_columns = list(depth_rows[0])
    write_csv(V3 / "ranking_depth_impact_by_cell.csv", depth_rows, depth_columns)
    incomplete_depth = [row for row in depth_rows if row["depth_shortfall_periods"] > 0]

    old_members = read_rows(LEGACY / "combined.jsonl")
    old_group_counts = Counter(
        (row["provider"], row["country_code"], row["year"], row["selection_status"])
        for row in old_members
        if row["provider"] in {"KAGGLE_GONZALOPEZGIL_V151", "MGD"}
    )
    source_short, mgd_file_hashes = source_short_days()
    legacy_impacts = []
    for (provider, country, year, status), count in sorted(old_group_counts.items()):
        short_days = source_short.get(provider, Counter()).get((country, year), 0)
        legacy_impacts.append(
            {
                "country_code": country,
                "year": year,
                "provider": provider,
                "selection_status": status,
                "selected_memberships": count,
                "observed_days_below_expected_top_k": short_days,
                "depth_impacted": short_days > 0,
            }
        )
    write_csv(
        V3 / "legacy_92k_depth_impact_by_cell.csv",
        legacy_impacts,
        [
            "country_code",
            "year",
            "provider",
            "selection_status",
            "selected_memberships",
            "observed_days_below_expected_top_k",
            "depth_impacted",
        ],
    )
    legacy_affected = [row for row in legacy_impacts if row["depth_impacted"]]
    v2_manifest = read_json(LEGACY / "manifest.json")
    v2_verification = read_json(LEGACY / "verification.json")
    frozen_baseline_path = (
        ROOT / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031/combined.jsonl"
    )
    frozen_baseline = read_rows(frozen_baseline_path)
    frozen_groups = Counter(
        (row["provider"], row["country_code"], row["year"], row["selection_status"])
        for row in frozen_baseline
        if row["provider"] in {"KAGGLE_GONZALOPEZGIL_V151", "MGD"}
    )
    frozen_affected = []
    for (provider, country, year, status), count in sorted(frozen_groups.items()):
        if source_short.get(provider, Counter()).get((country, year), 0) > 0:
            frozen_affected.append(
                {
                    "provider": provider,
                    "country_code": country,
                    "year": year,
                    "selection_status": status,
                    "selected_memberships": count,
                }
            )
    write_csv(
        V3 / "legacy_86090_depth_impact_by_cell.csv",
        frozen_affected,
        ["provider", "country_code", "year", "selection_status", "selected_memberships"],
    )

    def impact_breakdown(rows):
        result = {}
        for provider in ("KAGGLE_GONZALOPEZGIL_V151", "MGD"):
            for status in ("CALENDAR_ELIGIBLE", "PROVISIONAL_OBSERVED_PERIODS"):
                subset = [
                    row
                    for row in rows
                    if row["provider"] == provider and row["selection_status"] == status
                ]
                result[f"{provider}|{status}"] = {
                    "cells": len({(row["country_code"], row["year"]) for row in subset}),
                    "memberships": sum(row["selected_memberships"] for row in subset),
                }
        return result

    eligible_quota = sum(cell["quota"] or 0 for cell in cells)
    inventory_ratio = len(members) / eligible_quota if eligible_quota else 0.0
    coverage80 = sum(
        1 for cell in cells if cell["quota"] and cell["selected_positions"] / cell["quota"] >= 0.8
    )

    report = {
        "version": "ranking-depth-independent-audit-v1",
        "selection": str(V3.relative_to(ROOT)),
        "v3_integrity": "PASS",
        "v3_local_sqlite": {
            "payloads_verified": True,
            "idempotency_verified": True,
            "run_id": run_id,
        },
        "v3_country_year_matrix": {
            "expected": len(expected_cells),
            "observed": len(cells),
            "complete": True,
        },
        "v3_rankings": {
            "quota_positions": eligible_quota,
            "memberships_observed": len(members),
            "raw_inventory_coverage": inventory_ratio,
            "inventory_cells_at_least_80pct": coverage80,
            "depth_shortfall_cells": len(incomplete_depth),
            "depth_shortfall_periods": sum(
                row["depth_shortfall_periods"] for row in incomplete_depth
            ),
            "source_coverage_rows": len(depth_rows),
            "pending_tie_pairs": v3_manifest["position_tie_pairs_pending"],
            "unresolved_source_conflicts": v3_manifest["unresolved_source_conflicts"],
            "scientifically_verified": False,
            "G1_approved_coverage": 0.0,
            "G1_state": "REPROVADO_SEM_EVIDENCIA_CIENTIFICA_INDEPENDENTE",
        },
        "legacy_92k": {
            "memberships": v2_manifest["memberships"],
            "verification_status": v2_verification["status"],
            "verification_scope": ["preservacao", "payload_postgresql", "idempotencia"],
            "original_verification_has_independent_top_k_depth_check": False,
            "posthoc_raw_source_reconstruction_available": True,
            "kaggle_mgd_selected_cells": len(legacy_impacts),
            "kaggle_mgd_depth_impacted_cells": len(legacy_affected),
            "kaggle_mgd_depth_impacted_memberships": sum(
                row["selected_memberships"] for row in legacy_affected
            ),
            "depth_impact_by_provider_and_status": impact_breakdown(legacy_affected),
            "source_depth_note": (
                "Legacy source_coverage lacks expected_depth and per-period shortfall counts; "
                "source-level raw reconstruction is independently recorded in the impact CSV."
            ),
        },
        "legacy_frozen_baseline_86090": {
            "memberships": len(frozen_baseline),
            "depth_impacted_cell_groups": len(frozen_affected),
            "depth_impacted_memberships": sum(
                row["selected_memberships"] for row in frozen_affected
            ),
            "depth_impact_by_provider_and_status": impact_breakdown(frozen_affected),
            "explanation": (
                "81/9690 counts Kaggle CALENDAR_ELIGIBLE rows in the frozen 86090 baseline; "
                "83/10090 is that same Kaggle status across the full 92000 selection. "
                "122/15270 additionally includes MGD and provisional rows."
            ),
        },
        "input_hashes": {
            "v3_manifest": sha256(V3 / "manifest.json"),
            "v3_source_coverage": sha256(V3 / "source_coverage.json"),
            "v3_combined": sha256(V3 / "combined.jsonl"),
            "v2_manifest": sha256(LEGACY / "manifest.json"),
            "v2_combined": sha256(LEGACY / "combined.jsonl"),
            "frozen_baseline_combined": sha256(frozen_baseline_path),
            "kaggle_daily": sha256(KAGGLE),
            "mgd_source_manifest": sha256(MGD_MANIFEST),
            "audit_script": sha256(Path(__file__).resolve()),
        },
    }
    (V3 / "ranking_depth_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    artifact_names = [
        "ranking_depth_impact_by_cell.csv",
        "legacy_92k_depth_impact_by_cell.csv",
        "legacy_86090_depth_impact_by_cell.csv",
        "ranking_depth_audit.json",
    ]
    audit_manifest = {
        "version": report["version"],
        "artifacts": {name: sha256(V3 / name) for name in artifact_names},
        "inputs": report["input_hashes"],
        "source_scan": {
            "kaggle_market_days_below_200": sum(source_short["KAGGLE_GONZALOPEZGIL_V151"].values()),
            "mgd_market_days_below_200": sum(source_short["MGD"].values()),
            "mgd_native_file_hashes": mgd_file_hashes,
        },
    }
    (V3 / "ranking_depth_audit_manifest.json").write_text(
        json.dumps(audit_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
