"""Export missing ranking positions and lyrics from one immutable PostgreSQL snapshot."""

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, select

from chart_observatory.config import Settings
from chart_observatory.ingestion.import_quotas import load_quotas
from chart_observatory.lyrics.quota_staging import candidates
from chart_observatory.lyrics.staging_coverage import summarize_coverage
from chart_observatory.lyrics.staging_review import list_snapshots


def main():
    root = Path(__file__).resolve().parents[1]
    engine = create_engine(Settings.load(root).database_url)
    try:
        snapshot = list_snapshots(engine, 1)[0]
        quotas = load_quotas(
            Path(snapshot["manifest"]["selection_root"]) / "sources/country_quotas.csv"
        )
        with engine.connect() as conn:
            records = (
                conn.execute(
                    select(
                        candidates.c.candidate_id,
                        candidates.c.payload,
                        candidates.c.text_sha256,
                        candidates.c.audit,
                    ).where(candidates.c.run_id == snapshot["run_id"])
                )
                .mappings()
                .all()
            )
        result = summarize_coverage(records, quotas)
        result.update(run_id=snapshot["run_id"], observed_at=datetime.now(UTC).isoformat())
        path = root / "data/derived/lyrics/quota-20261030/review-inventory/staging-coverage.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(".part")
        part.write_text(json.dumps(result, indent=2), encoding="utf-8")
        part.replace(path)
        print(json.dumps(result["summary"]))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
