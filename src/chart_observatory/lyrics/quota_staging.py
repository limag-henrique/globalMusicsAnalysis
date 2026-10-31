"""Immutable, deduplicated lyric staging; never writes canonical or classified documents."""

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    insert,
    select,
    text,
)

metadata = MetaData()
runs = Table(
    "quota_lyric_staging_runs",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("manifest", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
blobs = Table(
    "quota_lyric_staging_blobs",
    metadata,
    Column("sha256", String(64), primary_key=True),
    Column("body", Text, nullable=False),
    Column("characters", Integer, nullable=False),
    CheckConstraint("length(sha256)=64"),
)
candidates = Table(
    "quota_lyric_staging_candidates",
    metadata,
    Column("run_id", ForeignKey(runs.c.id), primary_key=True),
    Column("candidate_id", String, primary_key=True),
    Column("text_sha256", ForeignKey(blobs.c.sha256)),
    Column("acquisition_status", String, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("source_result", JSON, nullable=False),
    Column("audit", JSON, nullable=False),
    Column("classification_ready", Boolean, nullable=False, default=False),
    Column("identity_validated", Boolean, nullable=False, default=False),
    Column("completeness_validated", Boolean, nullable=False, default=False),
    Column("rights_status", String, nullable=False, default="UNVERIFIED"),
    CheckConstraint("NOT classification_ready"),
    CheckConstraint("NOT identity_validated"),
    CheckConstraint("NOT completeness_validated"),
    CheckConstraint("rights_status='UNVERIFIED'"),
)


def persist_lyric_staging(engine, manifest, records, texts):
    """Atomically preserve a whole acquisition snapshot; store each text hash once."""
    records = sorted(records, key=lambda row: row["candidate_id"])
    if len({r["candidate_id"] for r in records}) != len(records):
        raise ValueError("duplicate retrieval candidate in staging snapshot")
    required = {r["text_sha256"] for r in records if r.get("text_sha256")}
    if required != set(texts):
        raise ValueError("staging text inventory does not match candidate references")
    for digest, body in texts.items():
        if not isinstance(body, str) or hashlib.sha256(body.encode()).hexdigest() != digest:
            raise ValueError("staging lyric body hash mismatch")
    signature = json.dumps(
        dict(manifest=manifest, records=records),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    run_id = hashlib.sha256(signature.encode()).hexdigest()
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(2026103101)"))
        metadata.create_all(conn)
        if conn.execute(select(runs.c.id).where(runs.c.id == run_id)).scalar_one_or_none():
            return dict(
                run_id=run_id,
                inserted=False,
                candidates=len(records),
                unique_texts=len(texts),
                classification_ready=False,
            )
        existing = set()
        keys = sorted(required)
        for offset in range(0, len(keys), 500):
            for digest, body in conn.execute(
                select(blobs.c.sha256, blobs.c.body).where(
                    blobs.c.sha256.in_(keys[offset : offset + 500])
                )
            ):
                if body != texts[digest]:
                    raise ValueError("existing staged body contradicts its content hash")
                existing.add(digest)
        conn.execute(insert(runs), dict(id=run_id, manifest=manifest, created_at=datetime.now(UTC)))
        missing = [
            dict(sha256=digest, body=body, characters=len(body))
            for digest, body in texts.items()
            if digest not in existing
        ]
        for offset in range(0, len(missing), 500):
            conn.execute(insert(blobs), missing[offset : offset + 500])
        for offset in range(0, len(records), 500):
            batch = [
                dict(
                    run_id=run_id,
                    candidate_id=r["candidate_id"],
                    text_sha256=r.get("text_sha256"),
                    acquisition_status=r["acquisition_status"],
                    payload=r["payload"],
                    source_result=r["source_result"],
                    audit=r["audit"],
                    classification_ready=False,
                    identity_validated=False,
                    completeness_validated=False,
                    rights_status="UNVERIFIED",
                )
                for r in records[offset : offset + 500]
            ]
            conn.execute(insert(candidates), batch)
    return dict(
        run_id=run_id,
        inserted=True,
        candidates=len(records),
        unique_texts=len(texts),
        new_text_blobs=len(missing),
        classification_ready=False,
    )
