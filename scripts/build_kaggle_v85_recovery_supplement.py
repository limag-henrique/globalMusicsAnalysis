"""Build a hash-bound, noncanonical supplement for two complete Israel chart years."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from chart_observatory.ingestion.historical_backfill import annual_ranks, integer_metric
from chart_observatory.ingestion.quota_boundary import validate_quota_memberships

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v3-final"
SOURCE = ROOT / "data/raw/historical_backfill/20261030/kaggle-dhruvildave-v85"
STATE = ROOT / "data/runtime/kaggle-original-recovery-20261031/status.json"
OUT = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v3-source-supplement"
YEARS = (2019, 2020)
COUNTRY = "IL"
DEPTH = 200


def file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def output_hashes(path: Path, names: list[str]) -> dict[str, str]:
    return {name: file_hash(path / name) for name in names}


def load_parent():
    manifest = json.loads((PARENT / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["output_hashes"].items():
        if file_hash(PARENT / name) != digest:
            raise ValueError(f"parent selection output hash mismatch: {name}")
    members = [
        json.loads(line)
        for line in (PARENT / "combined.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    cells = [
        json.loads(line)
        for line in (PARENT / "country_years.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    countries = json.loads((PARENT / "countries.json").read_text(encoding="utf-8"))
    coverage = json.loads((PARENT / "source_coverage.json").read_text(encoding="utf-8"))
    rankings = pl.read_parquet(PARENT / "new_market_rankings.parquet")
    return manifest, members, cells, countries, coverage, rankings


def validate_kaggle_archive() -> dict:
    record = json.loads((SOURCE / "record.json").read_text(encoding="utf-8-sig"))
    files = json.loads((SOURCE / "files.json").read_text(encoding="utf-8-sig"))
    state = json.loads(STATE.read_text(encoding="utf-8-sig"))
    csv_path = SOURCE / "charts.csv"
    zip_path = SOURCE / "charts.csv.zip"
    for path in (csv_path, zip_path):
        sidecar = path.with_name(path.name + ".sha256")
        expected = sidecar.read_text(encoding="ascii").strip().split()[0].lower()
        if file_hash(path) != expected:
            raise ValueError(f"Kaggle v85 archive checksum mismatch: {path.name}")
    csv_hash = file_hash(csv_path)
    if state.get("original_sha256") != csv_hash:
        raise ValueError("Kaggle recovery state refers to different source bytes")
    dataset_file = next(
        (f for f in files.get("datasetFiles", []) if f.get("name") == "charts.csv"), None
    )
    if dataset_file is None or dataset_file.get("totalBytes") != csv_path.stat().st_size:
        raise ValueError("Kaggle file metadata does not match archived source")
    if (
        record.get("ref") != "dhruvildave/spotify-charts"
        or record.get("currentVersionNumber") != 85
    ):
        raise ValueError("Kaggle record is not pinned to the expected dataset version")

    original_csv = (
        pl.scan_csv(csv_path, infer_schema=False)
        .filter(
            (pl.col("chart") == "top200")
            & (pl.col("region") == "Israel")
            & pl.col("date").str.slice(0, 4).is_in([str(y) for y in YEARS])
        )
        .select(
            pl.lit(COUNTRY).alias("country_code"),
            pl.col("date").str.to_date().alias("period_end"),
            pl.col("url").str.extract(r"/track/([A-Za-z0-9]{22})(?:\?.*)?$", 1).alias("native_id"),
            pl.col("title"),
            pl.col("artist"),
            integer_metric("streams").alias("metric_value"),
            pl.col("rank").cast(pl.Int32, strict=False).alias("source_rank"),
        )
        .collect(engine="streaming")
        .sort(["country_code", "period_end", "source_rank", "native_id"])
    )
    normalized = (
        pl.scan_parquet(SOURCE / "full-top200.parquet")
        .filter(
            (pl.col("country_code") == COUNTRY) & pl.col("period_end").dt.year().is_in(list(YEARS))
        )
        .collect(engine="streaming")
        .sort(["country_code", "period_end", "source_rank", "native_id"])
    )
    if not original_csv.equals(normalized):
        raise ValueError("normalized IL source rows differ from pinned Kaggle CSV")
    return {
        "provider": "KAGGLE_DHRUVILDAVE_V85",
        "dataset_ref": record["ref"],
        "dataset_id": record["id"],
        "dataset_version": record["currentVersionNumber"],
        "record_last_updated": record["lastUpdated"],
        "local_source_retrieval_time": None,
        "recovery_normalization_completed_at": state["updated_at"],
        "canonical_url": "https://www.kaggle.com/datasets/dhruvildave/spotify-charts/versions/85",
        "archive_download_url": (
            "https://www.kaggle.com/api/v1/datasets/download/"
            "dhruvildave/spotify-charts/charts.csv?datasetVersionNumber=85"
        ),
        "license": record.get("licenseName"),
        "source_files": {
            path.name: {
                "sha256": file_hash(path),
                "size_bytes": path.stat().st_size,
            }
            for path in (csv_path, zip_path, SOURCE / "record.json", SOURCE / "files.json")
        },
        "normalizer_state_sha256": file_hash(STATE),
        "normalized_parquet_sha256": file_hash(SOURCE / "full-top200.parquet"),
        "normalized_rows_directly_compared_to_original_csv": original_csv.height,
        "normalized_source_equals_filtered_original_csv": True,
    }


def build():
    if OUT.exists():
        raise FileExistsError("refusing to overwrite a prior supplement")
    parent_manifest, parent_members, parent_cells, countries, parent_coverage, parent_rankings = (
        load_parent()
    )
    parent_manifest_hash = file_hash(PARENT / "manifest.json")
    country_policy = next(c for c in countries if c["country_code"] == COUNTRY)
    quota = country_policy["quota_per_year_main"]
    if quota != 120:
        raise ValueError("expected Israel annual quota has changed")
    existing_by_cell = Counter((r["country_code"], r["year"]) for r in parent_members)
    if any(existing_by_cell[(COUNTRY, year)] for year in YEARS):
        raise ValueError("supplement would overwrite existing country/year memberships")
    provenance = validate_kaggle_archive()

    normalized = (
        pl.scan_parquet(SOURCE / "full-top200.parquet")
        .filter(
            (pl.col("country_code") == COUNTRY) & pl.col("period_end").dt.year().is_in(list(YEARS))
        )
        .collect(engine="streaming")
    )
    new_members, new_coverage = [], []
    new_rankings = []
    for year in YEARS:
        expected_dates = {
            date(year, 1, 1) + timedelta(days=i)
            for i in range((date(year + 1, 1, 1) - date(year, 1, 1)).days)
        }
        year_frame = normalized.filter(pl.col("period_end").dt.year() == year)
        periods = year_frame.group_by("period_end").agg(
            pl.len().alias("rows"),
            pl.col("native_id").n_unique().alias("unique_tracks"),
            pl.col("source_rank").n_unique().alias("unique_source_ranks"),
            pl.col("source_rank").min().alias("minimum_source_rank"),
            pl.col("source_rank").max().alias("maximum_source_rank"),
            pl.col("metric_value").null_count().alias("null_metrics"),
            pl.col("native_id").null_count().alias("null_native_ids"),
            (pl.col("metric_value") < 0).sum().alias("negative_metrics"),
        )
        if set(periods["period_end"].to_list()) != expected_dates:
            raise ValueError(f"Kaggle v85 calendar is incomplete: {COUNTRY}/{year}")
        if periods.filter(
            (pl.col("rows") != DEPTH)
            | (pl.col("unique_tracks") != DEPTH)
            | (pl.col("unique_source_ranks") != DEPTH)
            | (pl.col("minimum_source_rank") != 1)
            | (pl.col("maximum_source_rank") != DEPTH)
            | (pl.col("null_metrics") != 0)
            | (pl.col("null_native_ids") != 0)
            | (pl.col("negative_metrics") != 0)
        ).height:
            raise ValueError(f"Kaggle v85 Top 200 validation failed: {COUNTRY}/{year}")
        frame = year_frame.select(
            "country_code",
            "period_end",
            "native_id",
            "title",
            "artist",
            "metric_value",
            "source_rank",
        )
        ranked, coverage = annual_ranks(
            frame,
            markets={COUNTRY},
            year=year,
            cutoff=date(2026, 10, 15),
            frequency="DAILY",
            platform="SPOTIFY",
            provider=provenance["provider"],
            expected_depth=DEPTH,
        )
        cell_coverage = coverage[0]
        if (
            cell_coverage["coverage_status"] != "COMPLETE"
            or cell_coverage["depth_shortfall_periods"] != 0
            or cell_coverage["rank_invalid_observations"] != 0
            or cell_coverage["rank_start_missing_periods"] != 0
        ):
            raise ValueError(f"annual rank reconstruction failed: {COUNTRY}/{year}")
        selected = [r for r in ranked if r["position"] <= quota + 1]
        tie_pairs = [
            [left["position"], right["position"]]
            for left, right in zip(selected, selected[1:], strict=False)
            if left["metric_value"] == right["metric_value"]
        ]
        if tie_pairs:
            raise ValueError(f"annual ranking ties require adjudication: {COUNTRY}/{year}")
        selected = [r for r in selected if r["position"] <= quota]
        for row in selected:
            new_members.append(
                {
                    **row,
                    "quota_main": quota,
                    "selection_status": "CALENDAR_ELIGIBLE",
                    "coverage_status": "COMPLETE",
                    "collected_periods": cell_coverage["collected_periods"],
                    "expected_periods": cell_coverage["expected_periods"],
                    "not_for_paid_submission": True,
                }
            )
        new_rankings.extend(ranked)
        new_coverage.append(
            {
                **cell_coverage,
                "source_url": provenance["canonical_url"],
                "source_sha256": provenance["source_files"]["charts.csv"]["sha256"],
                "provenance_status": "hash_verified_kaggle_archive",
                "scientifically_verified": False,
            }
        )

    combined = sorted(
        parent_members + new_members,
        key=lambda row: (row["country_code"], row["year"], row["position"]),
    )
    validate_quota_memberships(
        combined,
        {
            c["country_code"]: c["quota_per_year_main"]
            for c in countries
            if c["quota_per_year_main"] is not None
        },
    )
    for year in YEARS:
        positions = [
            row["position"]
            for row in combined
            if row["country_code"] == COUNTRY and row["year"] == year
        ]
        if positions != list(range(1, quota + 1)):
            raise ValueError(f"supplement position keys are not contiguous: {COUNTRY}/{year}")

    cells = []
    for cell in parent_cells:
        updated = dict(cell)
        if cell["country_code"] == COUNTRY and cell["year"] in YEARS:
            updated.update(
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
        cells.append(updated)

    coverage = parent_coverage + new_coverage
    all_rankings = pl.concat([parent_rankings, pl.DataFrame(new_rankings)], how="diagonal_relaxed")
    candidate_ids = {row["candidate_id"] for row in combined}
    memberships_by_cell = Counter((row["country_code"], row["year"]) for row in combined)
    output_cells = sorted(cells, key=lambda row: (row["country_code"], row["year"]))
    output_dir = OUT
    output_dir.mkdir(parents=True, exist_ok=False)
    write_jsonl(output_dir / "combined.jsonl", combined)
    write_jsonl(output_dir / "country_years.jsonl", output_cells)
    write_jsonl(
        output_dir / "ranked_titles.jsonl",
        [
            {
                key: row.get(key)
                for key in (
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
    write_jsonl(output_dir / "added_memberships.jsonl", new_members)
    write_json(output_dir / "added_source_coverage.json", new_coverage)
    write_json(output_dir / "source_coverage.json", coverage)
    write_json(output_dir / "countries.json", countries)
    all_rankings.write_parquet(output_dir / "new_market_rankings.parquet")
    with (output_dir / "country_years.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_cells[0]))
        writer.writeheader()
        writer.writerows(
            {
                key: json.dumps(value) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
            for row in output_cells
        )
    write_json(output_dir / "source_definition.json", provenance)
    write_json(
        output_dir / "source_reconstruction_verification.json",
        {
            "source_csv_equals_normalized_subset": True,
            "directly_compared_source_rows": provenance[
                "normalized_rows_directly_compared_to_original_csv"
            ],
            "cells": [
                {
                    "country_code": COUNTRY,
                    "year": year,
                    "quota": quota,
                    "expected_periods": (date(year + 1, 1, 1) - date(year, 1, 1)).days,
                    "minimum_unique_tracks_per_period": DEPTH,
                    "all_periods_have_200_unique_tracks_and_positions_1_to_200": True,
                    "annual_boundary_tie_pairs": 0,
                    "added_positions": quota,
                    "scientifically_verified": False,
                }
                for year in YEARS
            ],
        },
    )

    additional = 2 * quota
    manifest = {
        "protocol": parent_manifest["protocol"],
        "selection_revision": "global-archive-source-supplement-v1",
        "parent_selection": str(PARENT.relative_to(ROOT)),
        "parent_selection_manifest_sha256": parent_manifest_hash,
        "scientifically_verified": False,
        "source_candidate_cells": [f"{COUNTRY}/{year}" for year in YEARS],
        "source_provider": provenance["provider"],
        "source_file_hashes": {
            name: details["sha256"]
            for name, details in provenance["source_files"].items()
            if "sha256" in details
        },
        "years": parent_manifest["years"],
        "cutoff": parent_manifest["cutoff"],
        "countries": len(countries),
        "country_year_cells": len(output_cells),
        "requested_positions": parent_manifest["requested_positions"],
        "parent_memberships": len(parent_members),
        "supplemental_memberships": additional,
        "memberships": len(combined),
        "new_definitive_memberships": parent_manifest["new_definitive_memberships"] + additional,
        "new_provisional_memberships": parent_manifest["new_provisional_memberships"],
        "candidate_identities": len(candidate_ids),
        "countries_with_memberships": len({row["country_code"] for row in combined}),
        "cells_with_memberships": sum(bool(value) for value in memberships_by_cell.values()),
        "missing_positions": sum(cell["missing_positions"] or 0 for cell in output_cells),
        "missing_complete_annual_positions": sum(
            cell["missing_complete_annual_positions"] or 0 for cell in output_cells
        ),
        "position_tie_pairs_pending": parent_manifest["position_tie_pairs_pending"],
        "unresolved_source_conflicts": parent_manifest["unresolved_source_conflicts"],
        "database_write": False,
        "paid_calls": 0,
        "network_calls": 0,
        "classification_ready": False,
        "lyrics_acquisition_ready": False,
        "scientifically_verified_positions_added": 0,
    }
    tracked_inputs = [
        PARENT / "manifest.json",
        SOURCE / "charts.csv",
        SOURCE / "charts.csv.sha256",
        SOURCE / "charts.csv.zip",
        SOURCE / "charts.csv.zip.sha256",
        SOURCE / "record.json",
        SOURCE / "files.json",
        SOURCE / "full-top200.parquet",
        SOURCE / "normalization-summary.json",
        STATE,
        ROOT / "scripts/recover_original_kaggle_charts.py",
        ROOT / "src/chart_observatory/ingestion/historical_backfill.py",
        ROOT / "src/chart_observatory/sources/catalog.py",
        Path(__file__).resolve(),
    ]
    manifest["input_hashes"] = {
        str(path.relative_to(ROOT)): file_hash(path) for path in tracked_inputs
    }
    artifact_names = [
        "combined.jsonl",
        "country_years.jsonl",
        "country_years.csv",
        "ranked_titles.jsonl",
        "added_memberships.jsonl",
        "added_source_coverage.json",
        "source_coverage.json",
        "countries.json",
        "new_market_rankings.parquet",
        "source_definition.json",
        "source_reconstruction_verification.json",
    ]
    manifest["output_hashes"] = output_hashes(output_dir, artifact_names)
    write_json(output_dir / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "output": str(output_dir.relative_to(ROOT)),
                "parent_memberships": len(parent_members),
                "supplemental_memberships": additional,
                "memberships": len(combined),
                "net_cell_additions": [f"{COUNTRY}/{year}" for year in YEARS],
                "scientifically_verified": False,
                "database_write": False,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    build()
