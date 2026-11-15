"""Persist and compare a frozen rebuilt selection without editing its snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, select, text

from chart_observatory.config import Settings
from chart_observatory.ingestion.global_annual import (
    cells_table,
    countries_table,
    memberships_table,
    persist,
)
from chart_observatory.research_flow import file_hash, load_selection, write_json

ROOT = Path(__file__).resolve().parents[1]


def persist_selection(project, selection, output, *, engine=None):
    project, selection, output = (Path(p).resolve() for p in (project, selection, output))
    if not selection.is_relative_to(project) or not output.is_relative_to(project):
        raise ValueError("selection and receipt must remain inside project")
    if output == selection or output.is_relative_to(selection):
        raise ValueError("receipt must stay outside the immutable selection")
    if output.exists():
        raise ValueError("use a new immutable receipt directory")
    manifest, cells, memberships, hashes = load_selection(selection)
    country_path = selection / "countries.json"
    if str(country_path) not in hashes:
        raise ValueError("hashed country inventory required")
    countries = json.loads(country_path.read_text(encoding="utf-8-sig"))
    result = dict(
        countries=countries,
        cells=cells,
        memberships=memberships,
        new_definitive_memberships=manifest["new_definitive_memberships"],
        new_provisional_memberships=manifest["new_provisional_memberships"],
    )
    import_manifest = dict(
        manifest,
        selection_root=str(selection),
        global_manifest_sha256=hashes[str(selection / "manifest.json")],
    )
    own_engine = engine is None
    if own_engine:
        engine = create_engine(
            Settings.load(project).database_url, connect_args={"connect_timeout": 5}
        )
    try:
        receipt = persist(engine, import_manifest, result)
        comparisons = []
        with engine.connect() as conn:
            if conn.dialect.name == "postgresql":
                conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            for table, expected, keys in (
                (countries_table, countries, ("country_code",)),
                (cells_table, cells, ("country_code", "year")),
                (memberships_table, memberships, ("country_code", "year", "position")),
            ):
                actual = list(conn.scalars(
                    select(table.c.payload).where(table.c.run_id == receipt["run_id"])
                ))

                def order(row, fields=keys):
                    return tuple(row[k] for k in fields)

                if sorted(actual, key=order) != sorted(expected, key=order):
                    raise ValueError("persisted payload differs from selection: " + table.name)
                comparisons.append(dict(
                    table=table.name, rows=len(actual), all_payloads_equal=True
                ))
        repeated = persist(engine, import_manifest, result)
        if repeated["inserted"] or repeated["run_id"] != receipt["run_id"]:
            raise ValueError("frozen selection import is not idempotent")
        if any(file_hash(path) != digest for path, digest in hashes.items()):
            raise ValueError("selection changed during import")
        report = dict(
            protocol="frozen-research-selection-persistence-v1",
            observed_at=datetime.now(UTC).isoformat(),
            selection_root=str(selection),
            selection_sha256=hashes[str(selection / "manifest.json")],
            **receipt,
            comparisons=comparisons,
            idempotency_verified=True,
            scientific_approval=False,
            paid_calls=0,
        )
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "report.json", report)
        write_json(output / "manifest.json", dict(
            input_hashes=hashes,
            artifacts={"report.json": file_hash(output / "report.json")},
        ))
        return report
    finally:
        if own_engine:
            engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(persist_selection(ROOT, args.selection, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
