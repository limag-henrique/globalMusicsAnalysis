"""Immutable quota snapshots, separate from historical article Top 80 tables."""

import hashlib
import json

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
)

metadata = MetaData()
runs = Table(
    "quota_import_runs", metadata,
    Column("id", String(64), primary_key=True),
    Column("manifest", JSON, nullable=False),
)
memberships = Table(
    "quota_import_memberships", metadata,
    Column("run_id", ForeignKey("quota_import_runs.id"), primary_key=True),
    Column("country_code", String(2), primary_key=True),
    Column("year", Integer, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("candidate_id", String, nullable=False),
    Column("payload", JSON, nullable=False),
    CheckConstraint("year BETWEEN 2017 AND 2026"),
    CheckConstraint("position BETWEEN 1 AND 500"),
)


def persist_snapshot(engine, manifest, selections):
    """Atomic insert once per content signature; never replace an older selection."""
    payload = json.dumps(dict(manifest=manifest, selections=selections),
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    run_id = hashlib.sha256(payload.encode()).hexdigest()
    metadata.create_all(engine)
    with engine.begin() as conn:
        # PostgreSQL serializes concurrent attempts for this immutable signature.
        if conn.dialect.name == "postgresql":
            from sqlalchemy import text

            conn.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                         {"key": int(run_id[:15], 16)})
        if conn.execute(select(runs.c.id).where(runs.c.id == run_id)).scalar_one_or_none():
            return {"run_id": run_id, "inserted": False, "memberships": len(selections)}
        conn.execute(insert(runs), {"id": run_id, "manifest": manifest})
        for offset in range(0, len(selections), 1000):
            conn.execute(insert(memberships), [dict(
                run_id=run_id, country_code=row["country_code"], year=row["year"],
                position=row["position"], candidate_id=row["candidate_id"], payload=row,
            ) for row in selections[offset:offset+1000]])
    return {"run_id": run_id, "inserted": True, "memberships": len(selections)}
