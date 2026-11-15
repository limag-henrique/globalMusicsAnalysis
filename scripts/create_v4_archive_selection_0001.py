"""Create a new immutable v4 archive overlay from frozen v3 plus delta v2."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import polars as pl
from build_global_v3_archive_supplement_v2 import rebuild_2021

from chart_observatory.ingestion.quota_boundary import validate_quota_memberships
from chart_observatory.ingestion.source_coverage import normalize_source_coverage

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v3-final"
V1 = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v3-source-supplement"
SUP = (
    ROOT
    / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v3-source-supplement-v2-final"
)
OUT = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002"
CELLS = (("IL", 2019), ("IL", 2020), ("IL", 2021), ("RU", 2021))


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values):
    with path.open("w", encoding="utf-8") as stream:
        for value in values:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def verify(folder: Path, manifest: dict):
    for name, digest in manifest["output_hashes"].items():
        if sha(folder / name) != digest:
            raise ValueError(f"output hash mismatch: {folder.name}/{name}")


def main():
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    v3_manifest = read_json(V3 / "manifest.json")
    v1_manifest = read_json(V1 / "manifest.json")
    sup_manifest = read_json(SUP / "manifest.json")
    verify(V3, v3_manifest)
    verify(V1, v1_manifest)
    verify(SUP, sup_manifest)
    parent = read_jsonl(V3 / "combined.jsonl")
    delta = read_jsonl(SUP / "added_memberships.jsonl")
    cells = read_jsonl(V3 / "country_years.jsonl")
    quota_by_country = {
        row["country_code"]: row["quota_per_year_main"]
        for row in read_json(V3 / "countries.json")
        if row.get("quota_per_year_main") is not None
    }
    parent_keys = {(r["country_code"], int(r["year"]), int(r["position"])) for r in parent}
    delta_keys = [(r["country_code"], int(r["year"]), int(r["position"])) for r in delta]
    if (
        len(delta) != 560
        or len(delta_keys) != len(set(delta_keys))
        or parent_keys.intersection(delta_keys)
    ):
        raise ValueError(
            "supplement delta is not exactly 560 unique missing v3 position participations"
        )
    combined = sorted(
        parent + delta, key=lambda r: (r["country_code"], int(r["year"]), int(r["position"]))
    )
    validate_quota_memberships(combined, quota_by_country)
    delta_count = Counter((r["country_code"], int(r["year"])) for r in delta)
    parent_count = Counter((r["country_code"], int(r["year"])) for r in parent)
    total_count = Counter((r["country_code"], int(r["year"])) for r in combined)
    for key, count in total_count.items():
        if count != parent_count[key] + delta_count[key]:
            raise ValueError(f"cell mismatch against v3 plus delta: {key}")
    for country, year in CELLS:
        rows = [
            r["position"]
            for r in combined
            if (r["country_code"], int(r["year"])) == (country, year)
        ]
        if rows != list(range(1, int(quota_by_country[country]) + 1)):
            raise ValueError(f"supplement cell is not a contiguous quota: {country}/{year}")

    # Reconstruct only the new annual-ranking evidence; do not read the old v4 path.
    rankings_2021, coverage_2021 = [], []
    for country in ("IL", "RU"):
        _, ranked, coverage, audit = rebuild_2021(country, int(quota_by_country[country]))
        if audit["annual_boundary_tie_pairs"] != 0:
            raise ValueError(f"annual boundary ties unresolved: {country}/2021")
        rankings_2021.extend(ranked)
        coverage_2021.append(coverage)
    v1_rankings = pl.read_parquet(V1 / "new_market_rankings.parquet")
    v3_rankings = pl.read_parquet(V3 / "new_market_rankings.parquet")
    all_rankings = pl.concat(
        [v3_rankings, v1_rankings, pl.DataFrame(rankings_2021)], how="diagonal_relaxed"
    )
    source_coverage = normalize_source_coverage(
        read_json(V3 / "source_coverage.json"),
        read_json(V1 / "added_source_coverage.json"),
        coverage_2021,
    )
    for cell in cells:
        key = cell["country_code"], int(cell["year"])
        if delta_count[key]:
            quota = int(cell["quota"])
            cell.update(
                selected_positions=quota,
                provisional_positions=0,
                complete_calendar_year_positions=quota,
                missing_positions=0,
                missing_complete_annual_positions=0,
                missing_position_numbers=[],
                platforms=["SPOTIFY"],
                selection_statuses={"CALENDAR_ELIGIBLE": quota},
                status="QUOTA_FILLED_COMPLETE_CALENDAR",
            )

    OUT.mkdir(parents=True)
    shutil.copy2(V3 / "countries.json", OUT / "countries.json")
    # Preserve every other parent artifact byte-for-byte, then replace only the
    # selection outputs whose contents change as a direct result of this delta.
    for name in v3_manifest["output_hashes"]:
        source = V3 / name
        if name not in {
            "combined.jsonl",
            "country_years.jsonl",
            "country_years.csv",
            "ranked_titles.jsonl",
            "new_market_rankings.parquet",
            "source_coverage.json",
        }:
            shutil.copy2(source, OUT / name)
    write_jsonl(OUT / "combined.jsonl", combined)
    write_jsonl(OUT / "country_years.jsonl", cells)
    write_jsonl(
        OUT / "ranked_titles.jsonl",
        [
            {
                k: row.get(k)
                for k in (
                    "country_code",
                    "year",
                    "position",
                    "title",
                    "artist",
                    "platform",
                    "provider",
                    "candidate_id",
                    "metric_value",
                    "selection_status",
                    "identity_status",
                    "not_for_paid_submission",
                )
            }
            for row in combined
        ],
    )
    write_json(OUT / "source_coverage.json", source_coverage)
    all_rankings.write_parquet(OUT / "new_market_rankings.parquet")
    with (OUT / "country_years.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cells[0]))
        writer.writeheader()
        writer.writerows(
            {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()}
            for row in cells
        )

    cell_audit = read_json(SUP / "source_validation.json")
    semantic_failures = int(cell_audit["cell_semantics_checks_failed_v4"])
    if semantic_failures:
        raise ValueError(f"v4 cell semantic audit failed: {semantic_failures}")
    manifest = dict(v3_manifest)
    current_inputs = dict(sup_manifest["input_hashes"])
    current_inputs[str(Path(__file__).relative_to(ROOT))] = sha(Path(__file__).resolve())
    current_inputs["src/chart_observatory/ingestion/source_coverage.py"] = sha(
        ROOT / "src/chart_observatory/ingestion/source_coverage.py"
    )
    manifest.update(
        {
            "selection_revision": "global-rescan-v4-archive-overlay-final-0002",
            "parent_selection": str(V3.relative_to(ROOT)),
            "parent_selection_manifest_sha256": sha(V3 / "manifest.json"),
            "supplement_selection": str(SUP.relative_to(ROOT)),
            "supplement_manifest_sha256": sha(SUP / "manifest.json"),
            "scientifically_verified": False,
            "memberships": len(combined),
            "new_definitive_memberships": int(v3_manifest["new_definitive_memberships"])
            + len(delta),
            "candidate_identities": len({r["candidate_id"] for r in combined}),
            "countries_with_memberships": len({r["country_code"] for r in combined}),
            "cells_with_memberships": len(total_count),
            "missing_positions": sum(int(c["missing_positions"] or 0) for c in cells),
            "missing_complete_annual_positions": sum(
                int(c["missing_complete_annual_positions"] or 0) for c in cells
            ),
            "archive_overlay_added_position_participations": len(delta),
            "archive_overlay_cells": [f"{country}/{year}" for country, year in CELLS],
            "raw_membership_coverage_pct": round(
                len(combined) / int(v3_manifest["requested_positions"]) * 100, 4
            ),
            "cell_semantics_checks_failed": semantic_failures,
            "cell_semantics_audit_report": str(
                (SUP / "cell_semantics_audit.csv").relative_to(ROOT)
            ),
            "database_write": False,
            "network_calls": 0,
            "paid_calls": 0,
            "g1_approved": False,
            "scientifically_verified_positions_added": 0,
            "source_coverage_schema": "array<object>",
            "source_coverage_rows": len(source_coverage),
            "source_coverage_invalid_rows": 0,
            "input_hashes": current_inputs,
        }
    )
    manifest["output_hashes"] = {name: sha(OUT / name) for name in v3_manifest["output_hashes"]}
    write_json(OUT / "manifest.json", manifest)
    verify(OUT, manifest)
    if (
        len(combined) != 90600
        or manifest["missing_positions"] != 187050
        or len(source_coverage) != 997
    ):
        raise ValueError("v4 global count mismatch")
    print(
        json.dumps(
            {
                "selection": str(OUT.relative_to(ROOT)),
                "v3_rows": len(parent),
                "added_rows": len(delta),
                "v4_rows": len(combined),
                "coverage_pct": manifest["raw_membership_coverage_pct"],
                "cell_semantics_failures": semantic_failures,
                "g1_approved": False,
                "hashes_verified": True,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
