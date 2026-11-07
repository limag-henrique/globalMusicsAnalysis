"""Verify capped annual memberships separately from repeated weekly reference observations."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from sqlalchemy import create_engine, select, text

from chart_observatory.config import Settings
from chart_observatory.ingestion.import_quotas import load_quotas
from chart_observatory.ingestion.quota_boundary import (
    validate_quota_memberships,
    validate_ranking_positions,
)
from chart_observatory.lyrics.quota_staging import candidates, runs
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031"


def main():
    quota_path = BASE / "sources/country_quotas.csv"
    quotas = load_quotas(quota_path)
    raw = (BASE / "combined.jsonl").read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    cells = validate_quota_memberships(rows, quotas)
    rankings = pl.read_parquet(BASE / "sources/rankings.parquet").to_dicts()
    validate_ranking_positions(rows, rankings)
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.begin() as conn:
            run_id = conn.execute(
                select(runs.c.id).order_by(runs.c.created_at.desc(), runs.c.id).limit(1)
            ).scalar_one()
            stored = (
                conn.execute(
                    select(
                        candidates.c.candidate_id,
                        candidates.c.payload,
                        candidates.c.classification_ready,
                    ).where(candidates.c.run_id == run_id)
                )
                .mappings()
                .all()
            )
            db_rows = [
                dict(binding, candidate_id=r["candidate_id"])
                for r in stored
                for binding in r["payload"].get("chart_bindings", [])
            ]
            db_cells = validate_quota_memberships(db_rows, quotas)
            validate_ranking_positions(db_rows, rankings)
            reference = (
                conn.execute(
                    text("""SELECT country_code,
                extract(year from period_end)::int AS year, count(*) AS reference_weeks,
                sum(jsonb_array_length(payload->'rows'))::int AS weekly_reference_occurrences
                FROM quota_chart_discovery_snapshots GROUP BY 1,2 ORDER BY 1,2""")
                )
                .mappings()
                .all()
            )
            conn.execute(
                text("""COMMENT ON TABLE quota_chart_discovery_snapshots IS
                'Reference evidence only: repeated weekly occurrences. Not annual memberships,
                not analysis input, not a count of unique selected songs. Apply country quotas
                only to reconciled annual positions 1..N.'""")
            )
        report = dict(
            observed_at=datetime.now(UTC).isoformat(),
            run_id=run_id,
            quota_table_sha256=hashlib.sha256(quota_path.read_bytes()).hexdigest(),
            selection_sha256=hashlib.sha256(raw).hexdigest(),
            annual_memberships=len(rows),
            staged_annual_memberships=len(db_rows),
            excess_positions=0,
            weekly_reference_occurrences_used_for_analysis=0,
            classification_ready_candidates=sum(r["classification_ready"] for r in stored),
            cells=cells,
            staged_cells=db_cells,
            reference_only=[dict(r) for r in reference],
        )
        publish_status(ROOT / "data/runtime/quota-analysis-boundary-20261101.json", report)
        print(
            json.dumps(
                {
                    k: v
                    for k, v in report.items()
                    if k not in {"cells", "staged_cells", "reference_only"}
                }
            )
        )
        print(json.dumps(dict(israel=[r for r in db_cells if r["country_code"] == "IL"])))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
