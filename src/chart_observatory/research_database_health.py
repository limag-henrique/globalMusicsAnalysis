"""Current read-only PostgreSQL inventory, scoped to one frozen research selection."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, func, select, text

from chart_observatory.config import Settings
from chart_observatory.ingestion.global_annual import cells_table, memberships_table
from chart_observatory.ingestion.global_annual import runs as ranking_runs
from chart_observatory.lyrics.quota_staging import candidates, runs
from chart_observatory.pipeline_state import file_hash


def current_inventory(project, selection, *, engine=None):
    project, selection = Path(project).resolve(), Path(selection).resolve()
    selection_hash = file_hash(selection / "manifest.json")
    if selection_hash is None:
        raise ValueError("frozen selection manifest required")
    selection_manifest = json.loads((selection / "manifest.json").read_text(encoding="utf-8"))
    created_engine = engine is None
    if created_engine:
        engine = create_engine(
            Settings.load(project).database_url, connect_args={"connect_timeout": 5}
        )
    try:
        with engine.connect() as connection:
            if connection.dialect.name == "postgresql":
                connection.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                )
                connection.execute(text("SET LOCAL statement_timeout = '30000'"))
                readonly = connection.scalar(text("SHOW transaction_read_only")) == "on"
                version = connection.scalar(text("SHOW server_version"))
                in_recovery = connection.scalar(text("SELECT pg_is_in_recovery()"))
            else:
                raise ValueError("current research inventory requires PostgreSQL")
            # Scan run metadata only; never fetch lyric bodies or include credentials.
            chosen = next(
                (
                    dict(row)
                    for row in connection.execute(
                        select(runs.c.id, runs.c.manifest, runs.c.created_at).order_by(
                            runs.c.created_at.desc(), runs.c.id.desc()
                        )
                    ).mappings()
                    if row["manifest"].get("global_manifest_sha256") == selection_hash
                ),
                None,
            )
            report = {
                "observed_at": datetime.now(UTC).isoformat(),
                "database_available": True,
                "server_version": version,
                "transaction_read_only": readonly,
                "in_recovery": in_recovery,
                "selection_sha256": selection_hash,
                "current_database_certified": readonly and not in_recovery,
                "staging": None,
                "production_writes": 0,
                "paid_calls": 0,
            }
            if chosen is not None:
                run_id = chosen["id"]
                count, with_text, ready = connection.execute(
                    select(
                        func.count(),
                        func.count(candidates.c.text_sha256),
                        func.count().filter(candidates.c.classification_ready.is_(True)),
                    ).where(candidates.c.run_id == run_id)
                ).one()
                expected = chosen["manifest"].get("unique_candidates")
                if type(expected) is not int or count != expected or ready > with_text:
                    raise ValueError("current staging contradicts frozen candidate inventory")
                report["staging"] = {
                    "run_id": run_id,
                    "created_at": chosen["created_at"].isoformat(),
                    "candidates": count,
                    "text_candidates": with_text,
                    "without_text": count - with_text,
                    "classification_ready": ready,
                    "availability_percent": 100 * with_text / count if count else None,
                    "identity_or_integrity_approval_implied": False,
                }
            import_ref = selection / "postgres_import.json"
            rank_run = None
            if import_ref.is_file():
                rank_run = json.loads(import_ref.read_text(encoding="utf-8"))["run_id"]
                imported = connection.execute(
                    select(ranking_runs.c.manifest).where(ranking_runs.c.id == rank_run)
                ).scalar_one_or_none()
                if imported is None:
                    raise ValueError("selection import receipt points to a missing database run")
                explicit_hash = imported.get("global_manifest_sha256")
                if explicit_hash is not None:
                    matches = explicit_hash == selection_hash
                else:
                    matches = json.dumps(
                        imported, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                    ) == json.dumps(
                        selection_manifest,
                        sort_keys=True,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                if not matches:
                    raise ValueError("selection import receipt points to a different selection")
            else:
                # Rebuilt selections remain immutable. Their receipt is stored
                # outside the selection, and the DB manifest binds its hash.
                rank_run = next(
                    (
                        row["id"]
                        for row in connection.execute(
                            select(ranking_runs.c.id, ranking_runs.c.manifest)
                            .order_by(ranking_runs.c.id)
                        ).mappings()
                        if row["manifest"].get("global_manifest_sha256") == selection_hash
                    ),
                    None,
                )
            if rank_run is not None:
                report["rankings"] = {
                    "run_id": rank_run,
                    "memberships": connection.scalar(
                        select(func.count())
                        .select_from(memberships_table)
                        .where(memberships_table.c.run_id == rank_run)
                    ),
                    "country_year_cells": connection.scalar(
                        select(func.count())
                        .select_from(cells_table)
                        .where(cells_table.c.run_id == rank_run)
                    ),
                    "scientific_approval_implied": False,
                }
                if (
                    report["rankings"]["memberships"] != selection_manifest["memberships"]
                    or report["rankings"]["country_year_cells"]
                    != selection_manifest["country_year_cells"]
                ):
                    raise ValueError("current imported ranking counts contradict frozen selection")
            if file_hash(selection / "manifest.json") != selection_hash:
                raise ValueError("selection changed during read-only inventory")
            return report
    finally:
        if created_engine:
            engine.dispose()
