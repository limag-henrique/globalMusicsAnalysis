"""Check exact repair scope against the previous immutable PostgreSQL import."""

import json
from pathlib import Path

from sqlalchemy import create_engine, select

from chart_observatory.config import Settings
from chart_observatory.ingestion.archive_metadata import archive_proof
from chart_observatory.ingestion.global_annual import memberships_table
from chart_observatory.ingestion.quota_boundary import validate_display_only_refresh

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/global-2018-2026-20261108"
AUDIT = BASE / "metadata-repair-20261108"


def main():
    before_id = json.loads((AUDIT / "before-postgres_import.json").read_text(encoding="utf-8"))[
        "run_id"
    ]
    after_id = json.loads((BASE / "postgres_import.json").read_text(encoding="utf-8"))["run_id"]
    countries = json.loads((BASE / "countries.json").read_text(encoding="utf-8"))
    new = {c["country_code"] for c in countries if not c["legacy_frozen"]}
    refs = json.loads((BASE / "archive-display-metadata.json").read_text(encoding="utf-8"))
    verified = {key: archive_proof(key, proof) for key, proof in refs.items()}
    engine = create_engine(Settings.load(ROOT).database_url)
    try:
        with engine.connect() as conn:
            before = list(
                conn.execute(
                    select(memberships_table.c.payload).where(
                        memberships_table.c.run_id == before_id
                    )
                ).scalars()
            )
            after = list(
                conn.execute(
                    select(memberships_table.c.payload).where(
                        memberships_table.c.run_id == after_id
                    )
                ).scalars()
            )
    finally:
        engine.dispose()
    if not before or len(before) != len(after):
        raise ValueError("repair lost or added a ranked membership")
    def key(row):
        return row["country_code"], row["year"], row["position"]
    before.sort(key=key)
    after.sort(key=key)
    changes = []
    for original, repaired in zip(before, after, strict=True):
        if original == repaired:
            continue
        if original.get("title") and original.get("artist"):
            raise ValueError("repair changed an already complete name")
        proof = verified[original["candidate_id"]]
        if any(repaired[field] != proof[field] for field in ("title", "artist")):
            raise ValueError("new names do not match the exact-ID archive proof")
        expected_identity = (
            "native_id_pending_recording_review"
            if original.get("identity_status") == "metadata_missing"
            else original.get("identity_status")
        )
        if repaired.get("identity_status") != expected_identity:
            raise ValueError("repair improperly changed recording adjudication")
        normalized = dict(repaired, identity_status=original.get("identity_status"))
        validate_display_only_refresh([normalized], [original])
        if repaired["metadata_resolution"]["recording_and_text_validation"]:
            raise ValueError("display metadata cannot authorize classification")
        changes.append(
            dict(
                country_code=repaired["country_code"],
                year=repaired["year"],
                position=repaired["position"],
                candidate_id=repaired["candidate_id"],
                title=repaired["title"],
                artist=repaired["artist"],
            )
        )
    additional = [r for r in after if r["country_code"] in new]
    missing = [
        r
        for r in additional
        if any(not isinstance(r.get(f), str) or not r[f].strip() for f in ("title", "artist"))
    ]
    if missing:
        raise ValueError(f"additional memberships still have missing names: {len(missing)}")
    if any(not isinstance(r.get(f), str) or not r[f].strip()
           for r in after for f in ("title", "artist")):
        raise ValueError("global import still has missing display metadata")
    report = dict(
        status="PASS",
        before_run_id=before_id,
        after_run_id=after_id,
        total_memberships=len(after),
        additional_memberships=len(additional),
        repaired_memberships=len(changes),
        repaired_native_ids=len(verified),
        additional_missing_title_or_artist=0,
        total_missing_title_or_artist=0,
        changes=changes,
        all_other_memberships_unchanged=True,
        ranks_metrics_quotas_unchanged=True,
        recording_identity_adjudicated=False,
        paid_calls=0,
    )
    (AUDIT / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "changes"}))


if __name__ == "__main__":
    main()
