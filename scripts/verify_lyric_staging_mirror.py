"""Independently verify a complete immutable local lyric snapshot against PostgreSQL."""

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, select, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.quota_staging import blobs, candidates, runs
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]


def snapshot_signature(manifest, records):
    raw = json.dumps(
        dict(manifest=manifest, records=sorted(records, key=lambda r: r["candidate_id"])),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-staging", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if not all(p.resolve().is_relative_to(ROOT) for p in (args.local_staging, args.out)):
        raise ValueError("verification paths must remain inside project")
    with sqlite3.connect(args.local_staging.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        local_manifest = db.execute(
            "SELECT manifest FROM quota_lyric_staging_runs WHERE id=?", (args.run_id,)
        ).fetchone()
        if not local_manifest:
            raise ValueError("local run was not found")
        local_manifest = json.loads(local_manifest[0])
        local_records, local_texts = [], {}
        rows = db.execute(
            "SELECT c.candidate_id,c.payload,c.source_result,c.audit,c.acquisition_status,"
            "c.text_sha256,c.classification_ready,c.identity_validated,"
            "c.completeness_validated,c.rights_status,b.body "
            "FROM quota_lyric_staging_candidates c LEFT JOIN quota_lyric_staging_blobs b "
            "ON c.text_sha256=b.sha256 WHERE c.run_id=? ORDER BY c.candidate_id",
            (args.run_id,),
        )
        for (
            key,
            payload,
            result,
            audit,
            status,
            digest,
            ready,
            identity_ok,
            complete,
            rights,
            body,
        ) in rows:
            if ready or identity_ok or complete or rights != "UNVERIFIED":
                raise ValueError("local staging contains an impermissible approval")
            record = dict(
                candidate_id=key,
                payload=json.loads(payload),
                source_result=json.loads(result),
                audit=json.loads(audit),
                acquisition_status=status,
                text_sha256=digest,
            )
            local_records.append(record)
            if digest:
                if not isinstance(body, str) or hashlib.sha256(body.encode()).hexdigest() != digest:
                    raise ValueError("local text hash mismatch")
                local_texts[digest] = body
    if snapshot_signature(local_manifest, local_records) != args.run_id:
        raise ValueError("local run signature differs from its frozen data")
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            pg_manifest = conn.execute(
                select(runs.c.manifest).where(runs.c.id == args.run_id)
            ).scalar_one()
            pg_records = []
            for r in conn.execute(
                select(candidates)
                .where(candidates.c.run_id == args.run_id)
                .order_by(candidates.c.candidate_id)
            ).mappings():
                if (
                    r["classification_ready"]
                    or r["identity_validated"]
                    or r["completeness_validated"]
                    or r["rights_status"] != "UNVERIFIED"
                ):
                    raise ValueError("PostgreSQL staging contains an impermissible approval")
                pg_records.append(
                    {
                        key: r[key]
                        for key in (
                            "candidate_id",
                            "payload",
                            "source_result",
                            "audit",
                            "acquisition_status",
                            "text_sha256",
                        )
                    }
                )
            if pg_manifest != local_manifest or pg_records != local_records:
                raise ValueError("PostgreSQL candidate/manifest snapshot differs from local")
            keys = sorted(local_texts)
            checked = set()
            for offset in range(0, len(keys), 500):
                for digest, body in conn.execute(
                    select(blobs.c.sha256, blobs.c.body).where(
                        blobs.c.sha256.in_(keys[offset : offset + 500])
                    )
                ):
                    if (
                        hashlib.sha256(body.encode()).hexdigest() != digest
                        or local_texts[digest] != body
                    ):
                        raise ValueError("PostgreSQL text body differs from its local hash")
                    checked.add(digest)
            if checked != set(local_texts):
                raise ValueError("PostgreSQL text inventory is incomplete")
    finally:
        engine.dispose()
    publish_status(
        args.out,
        dict(
            verified_at=datetime.now(UTC).isoformat(),
            run_id=args.run_id,
            local_staging=str(args.local_staging.resolve()),
            candidate_count=len(local_records),
            text_candidates=sum(bool(r["text_sha256"]) for r in local_records),
            verified_text_blobs=len(local_texts),
            run_signature_matches=True,
            local_postgresql_candidates_equal=True,
            local_postgresql_bodies_equal=True,
            scientific_approvals=0,
            paid_calls=0,
            producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        ),
    )


if __name__ == "__main__":
    main()
