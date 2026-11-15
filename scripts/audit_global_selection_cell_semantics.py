"""Audit cell counters using the membership semantics defined by global_annual.py."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import polars as pl

from chart_observatory.ingestion.historical_backfill import integer_metric

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v3-final"
SUP = (
    ROOT
    / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v3-source-supplement-v2-final"
)
V4 = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0001"
SEMANTICS_SOURCE = ROOT / "src/chart_observatory/ingestion/global_annual.py"
KAGGLE = ROOT / "data/raw/historical_backfill/20261030/kaggle-dhruvildave-v85"


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_outputs(folder: Path, manifest: dict):
    for name, digest in manifest["output_hashes"].items():
        if sha(folder / name) != digest:
            raise ValueError(f"output hash mismatch: {folder.name}/{name}")


def audit_selection(folder: Path, revision: str):
    manifest = read_json(folder / "manifest.json")
    verify_outputs(folder, manifest)
    members = read_jsonl(folder / "combined.jsonl")
    cells = read_jsonl(folder / "country_years.jsonl")
    actual = Counter((r["country_code"], int(r["year"])) for r in members)
    provisional = Counter(
        (r["country_code"], int(r["year"]))
        for r in members
        if r.get("selection_status") == "PROVISIONAL_OBSERVED_PERIODS"
    )
    rows = []
    failures = 0
    for cell in cells:
        key = cell["country_code"], int(cell["year"])
        selected_expected = actual[key]
        provisional_expected = provisional[key]
        complete_expected = selected_expected - provisional_expected if key[1] < 2026 else 0
        quota = cell.get("quota")
        expected = {
            "selected_positions": selected_expected,
            "provisional_positions": provisional_expected,
            "complete_calendar_year_positions": complete_expected,
            "missing_positions": quota - selected_expected if quota is not None else None,
            "missing_complete_annual_positions": quota - complete_expected
            if quota is not None
            else None,
        }
        errors = {
            field: {"stored": cell.get(field), "expected": value}
            for field, value in expected.items()
            if cell.get(field) != value
        }
        failures += bool(errors)
        rows.append(
            {
                "selection_revision": revision,
                "country_code": key[0],
                "year": key[1],
                "quota": quota,
                "combined_memberships": actual[key],
                "stored_selected_positions": cell.get("selected_positions"),
                "stored_provisional_positions_subset": cell.get("provisional_positions"),
                "expected_provisional_subset": provisional_expected,
                "stored_complete_calendar_year_positions": cell.get(
                    "complete_calendar_year_positions"
                ),
                "expected_complete_calendar_year_positions": complete_expected,
                "stored_missing_positions": cell.get("missing_positions"),
                "expected_missing_positions": expected["missing_positions"],
                "semantic_checks_pass": not errors,
                "error_fields": json.dumps(errors, ensure_ascii=False, sort_keys=True),
            }
        )
    return rows, failures


def compare_kaggle_raw_2021():
    raw = (
        pl.scan_csv(KAGGLE / "charts.csv", infer_schema=False)
        .filter(
            pl.col("chart").eq("top200")
            & pl.col("region").is_in(["Israel", "Russia"])
            & pl.col("date").str.starts_with("2021-")
        )
        .select(
            pl.when(pl.col("region") == "Israel")
            .then(pl.lit("IL"))
            .otherwise(pl.lit("RU"))
            .alias("country_code"),
            pl.col("date").str.to_date("%Y-%m-%d").alias("period_end"),
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
        pl.scan_parquet(KAGGLE / "full-top200.parquet")
        .filter(
            pl.col("country_code").is_in(["IL", "RU"]) & (pl.col("period_end").dt.year() == 2021)
        )
        .select(
            "country_code",
            "period_end",
            "native_id",
            "title",
            "artist",
            "metric_value",
            pl.col("source_rank"),
        )
        .collect(engine="streaming")
        .sort(["country_code", "period_end", "source_rank", "native_id"])
    )
    if not raw.equals(normalized):
        raise ValueError("Kaggle normalized IL/RU 2021 rows differ from pinned original CSV")
    return {
        country: {
            "rows_directly_compared": raw.filter(pl.col("country_code") == country).height,
            "source_dates": raw.filter(pl.col("country_code") == country)["period_end"].n_unique(),
            "normalized_rows_equal_original_csv": True,
        }
        for country in ("IL", "RU")
    }


def main():
    v3_rows, v3_failures = audit_selection(V3, "global-rescan-v3")
    v4_rows, v4_failures = audit_selection(V4, "global-rescan-v4-final-0001")
    kaggle_comparison = compare_kaggle_raw_2021()
    if v3_failures or v4_failures:
        raise ValueError(f"cell semantics audit failed: v3={v3_failures}, v4={v4_failures}")
    audit_path = SUP / "cell_semantics_audit.csv"
    audit_rows = v3_rows + v4_rows
    with audit_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)
    old_report = SUP / "inherited_v3_cell_metadata_mismatches.csv"
    old_count = max(0, sum(1 for _ in old_report.open(encoding="utf-8-sig")) - 1)
    notice_path = SUP / "SUPERSEDED_cell_metadata_audit.md"
    notice_path.write_text(
        "# Auditoria anterior superada\n\n"
        f"O relatório `inherited_v3_cell_metadata_mismatches.csv` listou {old_count} células "
        "porque somou `selected_positions + provisional_positions`. A soma não é um invariante: "
        "`selected_positions` já é o total de memberships, enquanto `provisional_positions` é "
        "um subconjunto desse total. Na implementação congelada, `selected_positions = len(rows)`, "
        "`provisional_positions` conta apenas linhas `PROVISIONAL_OBSERVED_PERIODS`, e para anos "
        "completos `complete_calendar_year_positions = len(rows) - provisional_count`; em 2026 "
        f"o total de ano-calendário completo é zero. Portanto as {old_count} linhas do relatório "
        "anterior são falsos positivos do critério de soma e não apontam erro nas memberships.\n\n"
        "A verificação correta está em `cell_semantics_audit.csv` e compara cada campo com as "
        "linhas reais de `combined.jsonl`. Ela cobre 2.250 células em v3 e 2.250 em v4. "
        "As células fora dos quatro alvos do suplemento foram preservadas sem edição.\n",
        encoding="utf-8",
    )

    validation_path = SUP / "source_validation.json"
    validation = read_json(validation_path)
    validation.pop("inherited_v3_cell_metadata_mismatches", None)
    validation.pop("cell_metadata_caveat", None)
    validation.pop("inherited_v3_cell_metadata_mismatches_report", None)
    validation.update(
        {
            "superseded_sum_based_cell_audit_false_positives": old_count,
            "superseded_report_status": "SUPERSEDED_FALSE_POSITIVE_CRITERION",
            "cell_semantics_audit_report": audit_path.name,
            "cell_semantics_checks_failed_v3": v3_failures,
            "cell_semantics_checks_failed_v4": v4_failures,
            "cell_semantics_definition_source": str(SEMANTICS_SOURCE.relative_to(ROOT)),
            "cell_semantics_source_sha256": sha(SEMANTICS_SOURCE),
            "kaggle_v85_2021_direct_raw_csv_comparison": kaggle_comparison,
            "cell_semantics": (
                "selected_positions is the total membership count; provisional_positions is a "
                "subset; complete_calendar_year_positions is selected minus provisional for "
                "2018-2025 and zero for 2026."
            ),
        }
    )
    write_json(validation_path, validation)

    sup_manifest = read_json(SUP / "manifest.json")
    sup_manifest["output_hashes"][audit_path.name] = sha(audit_path)
    sup_manifest["output_hashes"][notice_path.name] = sha(notice_path)
    sup_manifest["output_hashes"][validation_path.name] = sha(validation_path)
    for relative in (
        "scripts/audit_global_selection_cell_semantics.py",
        "scripts/audit_v3_cell_metadata_reconciliation.py",
        "scripts/build_global_v3_archive_supplement_v2.py",
        "scripts/create_v4_archive_selection_0001.py",
        "src/chart_observatory/ingestion/global_annual.py",
    ):
        sup_manifest["input_hashes"][relative] = sha(ROOT / relative)
    sup_manifest.pop("inherited_v3_cell_metadata_mismatches", None)
    sup_manifest["superseded_report_status"] = "SUPERSEDED_FALSE_POSITIVE_CRITERION"
    write_json(SUP / "manifest.json", sup_manifest)

    v4_manifest = read_json(V4 / "manifest.json")
    v4_manifest["supplement_manifest_sha256"] = sha(SUP / "manifest.json")
    v4_manifest["cell_semantics_audit_report"] = str(audit_path.relative_to(ROOT))
    v4_manifest["cell_semantics_checks_failed"] = v4_failures
    v4_manifest.pop("inherited_v3_cell_metadata_mismatches", None)
    v4_manifest.pop("inherited_v3_cell_metadata_mismatches_report", None)
    v4_manifest["input_hashes"] = sup_manifest["input_hashes"]
    write_json(V4 / "manifest.json", v4_manifest)

    verify_outputs(SUP, sup_manifest)
    verify_outputs(V4, v4_manifest)
    print(
        json.dumps(
            {
                "superseded_false_positive_rows": old_count,
                "audited_cells": len(audit_rows),
                "v3_semantic_failures": v3_failures,
                "v4_semantic_failures": v4_failures,
                "supplement_manifest_sha256": sha(SUP / "manifest.json"),
                "v4_manifest_sha256": sha(V4 / "manifest.json"),
                "hashes_verified": True,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
