"""Verify global country/year import, frozen baseline and PostgreSQL idempotency."""

import copy
import hashlib
import json
from pathlib import Path

from sqlalchemy import create_engine, func, select

from chart_observatory.config import Settings
from chart_observatory.ingestion.archive_metadata import apply_archive_repairs
from chart_observatory.ingestion.global_annual import (
    cells_table,
    countries_table,
    memberships_table,
    persist,
)
from chart_observatory.ingestion.quota_boundary import validate_quota_memberships

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/derived/annual_revision/global-2018-2026-20261108"


def rows(path):
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def main():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    countries = json.loads((OUT / "countries.json").read_text(encoding="utf-8"))
    cells = rows(OUT / "country_years.jsonl")
    members = rows(OUT / "combined.jsonl")
    for name, digest in manifest["source_hashes"].items():
        with (ROOT / name).open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != digest:
                raise ValueError(f"input changed: {name}")
    for name, digest in manifest["output_hashes"].items():
        with (OUT / name).open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != digest:
                raise ValueError(f"output changed: {name}")
    quotas = {
        c["country_code"]: c["quota_per_year_main"]
        for c in countries
        if c["quota_per_year_main"] is not None
    }
    validate_quota_memberships(members, quotas)
    expected = {(c["country_code"], y) for c in countries for y in range(2018, 2027)}
    if {(c["country_code"], c["year"]) for c in cells} != expected or len(cells) != len(expected):
        raise ValueError("global country/year matrix is incomplete")
    baseline = rows(
        ROOT
        / "data/derived/annual_revision"
        / "reconciled-russia-2018-2026-20261031/combined.jsonl"
    )
    index = {(r["country_code"], r["year"], r["position"]): r for r in members}
    archive_path = OUT / "archive-display-metadata.json"
    archive_refs = json.loads(archive_path.read_text(encoding="utf-8")) if archive_path.exists() else {}
    baseline_display_repairs = 0
    for row in baseline:
        if index[row["country_code"], row["year"], row["position"]] != row:
            if row.get("title") and row.get("artist"):
                raise ValueError("already complete frozen baseline metadata changed")
            expected_row = copy.deepcopy(row)
            if apply_archive_repairs([expected_row], archive_refs) != 1:
                raise ValueError("missing exact-ID proof for legacy metadata repair")
            if index[row["country_code"], row["year"], row["position"]] != expected_row:
                raise ValueError("frozen baseline rank or non-display fields changed")
            baseline_display_repairs += 1
    receipt = json.loads((OUT / "postgres_import.json").read_text(encoding="utf-8"))
    run_id = receipt["run_id"]
    engine = create_engine(Settings.load(ROOT).database_url)
    try:
        with engine.connect() as conn:
            for table, source, keys in [
                (countries_table, countries, ("country_code",)),
                (cells_table, cells, ("country_code", "year")),
                (memberships_table, members, ("country_code", "year", "position")),
            ]:
                count = conn.execute(
                    select(func.count()).select_from(table).where(table.c.run_id == run_id)
                ).scalar_one()
                if count != len(source):
                    raise ValueError("PostgreSQL row count differs")
                actual = conn.execute(
                    select(table.c.payload)
                    .where(table.c.run_id == run_id)
                    .order_by(*(table.c[k] for k in keys))
                ).scalars()
                ordered = sorted(source, key=lambda r: tuple(r[k] for k in keys))
                if any(a != b for a, b in zip(actual, ordered, strict=True)):
                    raise ValueError("PostgreSQL payload differs")
        result = dict(
            countries=countries,
            cells=cells,
            memberships=members,
            new_definitive_memberships=manifest["new_definitive_memberships"],
            new_provisional_memberships=manifest["new_provisional_memberships"],
        )
        repeated = persist(engine, manifest, result)
        if repeated["inserted"] or repeated["run_id"] != run_id:
            raise ValueError("import is not idempotent")
    finally:
        engine.dispose()
    report = dict(
        status="PASS",
        countries=len(countries),
        country_year_cells=len(cells),
        verified_memberships=len(members),
        unchanged_baseline_memberships=len(baseline) - baseline_display_repairs,
        baseline_display_repairs=baseline_display_repairs,
        preserved_baseline_ranked_memberships=len(baseline),
        postgres_payloads_verified=True,
        idempotency_verified=True,
        paid_calls=0,
    )
    (OUT / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
