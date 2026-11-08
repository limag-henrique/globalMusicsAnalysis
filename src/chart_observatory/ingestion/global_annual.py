"""Worldwide annual incorporation without fabricating missing chart positions."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    insert,
    select,
    text,
)
from sqlalchemy.engine import Engine

from chart_observatory.ingestion.import_quotas import (
    provisional_selection,
    select_quota_candidates,
)
from chart_observatory.ingestion.quota_boundary import validate_quota_memberships

metadata = MetaData()
runs = Table(
    "global_annual_import_runs",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("manifest", JSON, nullable=False),
)
countries_table = Table(
    "global_annual_import_countries",
    metadata,
    Column("run_id", ForeignKey(runs.c.id), primary_key=True),
    Column("country_code", String(2), primary_key=True),
    Column("payload", JSON, nullable=False),
)
cells_table = Table(
    "global_annual_import_cells",
    metadata,
    Column("run_id", ForeignKey(runs.c.id), primary_key=True),
    Column("country_code", String(2), primary_key=True),
    Column("year", Integer, primary_key=True),
    Column("payload", JSON, nullable=False),
    CheckConstraint("year BETWEEN 2018 AND 2026"),
)
memberships_table = Table(
    "global_annual_import_memberships",
    metadata,
    Column("run_id", ForeignKey(runs.c.id), primary_key=True),
    Column("country_code", String(2), primary_key=True),
    Column("year", Integer, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("candidate_id", String, nullable=False),
    Column("payload", JSON, nullable=False),
    CheckConstraint("year BETWEEN 2018 AND 2026"),
    CheckConstraint("position BETWEEN 1 AND 500"),
)


def assemble(
    countries: list[dict[str, Any]],
    baseline: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
) -> dict[str, Any]:
    """Keep frozen memberships byte-equivalent as objects; append only new markets."""
    by_country = {c["country_code"]: c for c in countries}
    if len(by_country) != len(countries):
        raise ValueError("duplicate country")
    quotas = {
        c["country_code"]: c["quota_per_year_main"]
        for c in countries
        if c["quota_per_year_main"] is not None
    }
    legacy = {c["country_code"] for c in countries if c["legacy_frozen"]}
    if any(r["country_code"] not in legacy for r in baseline):
        raise ValueError("baseline contains a non-frozen country")
    if any(r["country_code"] in legacy for r in rankings + coverage):
        raise ValueError("new evidence cannot replace a frozen market")
    new_quotas = {code: q for code, q in quotas.items() if code not in legacy}
    chosen = select_quota_candidates(rankings, coverage, new_quotas)  # type: ignore[no-untyped-call]
    status = {(c["country_code"], c["year"]): c["status"] for c in chosen["coverage"]}
    definitive = [
        dict(r, selection_status=status[r["country_code"], r["year"]], coverage_status="COMPLETE")
        for r in chosen["selections"]
    ]
    provisional = provisional_selection(  # type: ignore[no-untyped-call]
        rankings, coverage, new_quotas, definitive
    )
    combined = sorted(
        baseline + definitive + provisional,
        key=lambda r: (r["country_code"], r["year"], r["position"]),
    )
    validate_quota_memberships(combined, quotas)  # type: ignore[no-untyped-call]
    groups = defaultdict(list)
    for row in combined:
        if row.get("period_scope", "").startswith("CURRENT"):
            raise ValueError("current snapshot cannot be an annual membership")
        groups[row["country_code"], row["year"]].append(row)
    cells = []
    for code, country in sorted(by_country.items()):
        quota = country["quota_per_year_main"]
        for year in range(2018, 2027):
            rows = groups[code, year]
            if [r["position"] for r in rows] != list(range(1, len(rows) + 1)):
                raise ValueError("membership positions must start at one without gaps")
            provisional_count = sum(
                r.get("selection_status") == "PROVISIONAL_OBSERVED_PERIODS" for r in rows
            )
            full_year = len(rows) - provisional_count if year < 2026 else 0
            cells.append(
                dict(
                    country_code=code,
                    year=year,
                    quota=quota,
                    selected_positions=len(rows),
                    provisional_positions=provisional_count,
                    complete_calendar_year_positions=full_year,
                    missing_positions=quota - len(rows) if quota is not None else None,
                    missing_complete_annual_positions=quota - full_year
                    if quota is not None
                    else None,
                    missing_position_numbers=list(range(len(rows) + 1, quota + 1))
                    if quota is not None
                    else [],
                    platforms=sorted({r["platform"] for r in rows}),
                    selection_statuses=dict(Counter(r.get("selection_status") for r in rows)),
                    status=(
                        "POPULATION_QUOTA_UNRESOLVED"
                        if quota is None
                        else "NO_VERIFIED_ANNUAL_SOURCE"
                        if not rows
                        else "PARTIAL_YEAR"
                        if year == 2026
                        else "PROVISIONAL_OBSERVED_PERIODS"
                        if provisional_count
                        else "INSUFFICIENT_RANKING"
                        if len(rows) < quota
                        else "QUOTA_FILLED_COMPLETE_CALENDAR"
                    ),
                    ranking_period_end=f"{year}-12-31" if year < 2026 else "2026-10-15",
                    classification_ready=False,
                )
            )
    return dict(
        countries=countries,
        cells=cells,
        memberships=combined,
        new_definitive_memberships=len(definitive),
        new_provisional_memberships=len(provisional),
    )


def persist(engine: Engine, manifest: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Add a content-addressed global run; never update legacy/canonical tables."""
    payload = json.dumps(
        dict(manifest=manifest, result=result),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    run_id = hashlib.sha256(payload.encode()).hexdigest()
    metadata.create_all(engine)
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), dict(key=int(run_id[:15], 16)))
        if conn.execute(select(runs.c.id).where(runs.c.id == run_id)).scalar_one_or_none():
            return dict(run_id=run_id, inserted=False)
        conn.execute(insert(runs), dict(id=run_id, manifest=manifest))
        for table, source, keys in [
            (countries_table, result["countries"], ("country_code",)),
            (cells_table, result["cells"], ("country_code", "year")),
            (
                memberships_table,
                result["memberships"],
                ("country_code", "year", "position", "candidate_id"),
            ),
        ]:
            for offset in range(0, len(source), 1000):
                conn.execute(
                    insert(table),
                    [
                        dict(run_id=run_id, payload=r, **{k: r[k] for k in keys})
                        for r in source[offset : offset + 1000]
                    ],
                )
    return dict(run_id=run_id, inserted=True)
