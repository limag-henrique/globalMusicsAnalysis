"""Read-only browsing of pending imports, scoped to an immutable snapshot."""

import hashlib
import json
import re
from pathlib import Path

from sqlalchemy import JSON, Integer, cast, exists, func, inspect, or_, select

from chart_observatory.lyrics.quota_discovery import usable_cached_repair, usable_cached_replay
from chart_observatory.lyrics.quota_staging import blobs, candidates, runs
from chart_observatory.lyrics.staging_coverage import summarize_coverage


def list_snapshots(engine, limit=20):
    if not inspect(engine).has_table(runs.name):
        return []
    with engine.connect() as conn:
        return [
            dict(run_id=r.id, created_at=r.created_at.isoformat(), manifest=r.manifest)
            for r in conn.execute(
                select(runs).order_by(runs.c.created_at.desc(), runs.c.id).limit(limit)
            )
        ]


def _run(conn, run_id):
    query = select(runs)
    query = (
        query.where(runs.c.id == run_id)
        if run_id
        else query.order_by(runs.c.created_at.desc(), runs.c.id)
    )
    return conn.execute(query.limit(1)).first()


def coverage_for_run(engine, quotas, *, run_id):
    """Read all membership coverage, including quota cells with no selected candidate."""
    with engine.connect() as conn:
        if not _run(conn, run_id):
            return None
        records = (
            conn.execute(
                select(
                    candidates.c.candidate_id,
                    candidates.c.payload,
                    candidates.c.text_sha256,
                    candidates.c.audit,
                ).where(candidates.c.run_id == run_id)
            )
            .mappings()
            .all()
        )
    return summarize_coverage(records, quotas)


def _binding_filter(dialect, country, year):
    if dialect == "sqlite":
        binding = (
            func.json_each(candidates.c.payload, "$.chart_bindings")
            .table_valued("value")
            .alias("binding")
        )

        def get(name):
            return func.json_extract(binding.c.value, f"$.{name}")
    else:
        binding = (
            func.json_array_elements(candidates.c.payload["chart_bindings"])
            .table_valued("value")
            .alias("binding")
        )

        def get(name):
            return cast(binding.c.value, JSON)[name].as_string()

    conditions = []
    if country:
        conditions.append(get("country_code") == country.upper())
    if year is not None:
        conditions.append(cast(get("year"), Integer) == year)
    predicate = exists(select(1).select_from(binding).where(*conditions).correlate(candidates))
    position = (
        select(func.min(cast(get("position"), Integer)))
        .select_from(binding)
        .where(*conditions)
        .correlate(candidates)
        .scalar_subquery()
    )
    return predicate, position


def browse_pending(
    engine, *, run_id=None, country=None, year=None, has_text=None, query=None, limit=50, offset=0
):
    if not 1 <= limit <= 200 or offset < 0:
        raise ValueError("invalid page limits")
    if not inspect(engine).has_table(runs.name):
        return dict(run_id=None, total=0, rows=[], limit=limit, offset=offset)
    with engine.connect() as conn:
        run = _run(conn, run_id)
        if not run:
            return dict(run_id=None, total=0, rows=[], limit=limit, offset=offset)
        conditions = [candidates.c.run_id == run.id]
        order = [candidates.c.payload["title"].as_string(), candidates.c.candidate_id]
        if country or year is not None:
            binding_filter, position = _binding_filter(conn.dialect.name, country, year)
            conditions.append(binding_filter)
            if country and year is not None:
                order.insert(0, position)
        if has_text is not None:
            conditions.append(
                candidates.c.text_sha256.is_not(None)
                if has_text
                else candidates.c.text_sha256.is_(None)
            )
        if query and query.strip():
            conditions.append(
                or_(
                    candidates.c.payload["title"]
                    .as_string()
                    .icontains(query.strip(), autoescape=True),
                    candidates.c.payload["artist"]
                    .as_string()
                    .icontains(query.strip(), autoescape=True),
                    candidates.c.candidate_id.icontains(query.strip(), autoescape=True),
                )
            )
        total = conn.execute(
            select(func.count()).select_from(candidates).where(*conditions)
        ).scalar_one()
        values = (
            conn.execute(
                select(
                    candidates.c.candidate_id,
                    candidates.c.acquisition_status,
                    candidates.c.text_sha256,
                    candidates.c.payload,
                    candidates.c.audit,
                )
                .where(*conditions)
                .order_by(*order)
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        rows = []
        for value in values:
            payload = value["payload"]
            bindings = [
                b
                for b in payload.get("chart_bindings", [])
                if (not country or b["country_code"] == country.upper())
                and (year is None or int(b["year"]) == year)
            ]
            rows.append(
                dict(
                    candidate_id=value["candidate_id"],
                    title=payload.get("title"),
                    artist=payload.get("artist"),
                    acquisition_status=value["acquisition_status"],
                    has_text=bool(value["text_sha256"]),
                    text_sha256=value["text_sha256"],
                    bindings=bindings,
                    review_flags=value["audit"].get("text_quality_flags", []),
                    source_quarantined=value["audit"].get("source_quarantined", False),
                    classification_ready=False,
                )
            )
        return dict(
            run_id=run.id,
            created_at=run.created_at.isoformat(),
            manifest=run.manifest,
            total=total,
            rows=rows,
            limit=limit,
            offset=offset,
            classification_ready=False,
        )


def load_conflicting_alternatives(payload, source_result, replay_root):
    """Read only hash-bound files from the configured local replay directory."""
    root = Path(replay_root).resolve()
    alternatives = []
    for reference in source_result.get("conflicting_offline_alternatives", []):
        row = dict(
            source=reference.get("source"),
            text_sha256=reference.get("text_sha256"),
            text=None,
            evidence_integrity_verified=False,
            classification_ready=False,
            identity_validated=False,
            completeness_validated=False,
        )
        try:
            filename = re.split(r"[/\\]", reference["replay_evidence_file"])[-1]
            if not re.fullmatch(r"[0-9a-f]{64}\.json", filename):
                raise ValueError("invalid replay filename")
            path = (root / filename).resolve()
            if not path.is_relative_to(root):
                raise ValueError("replay outside the local evidence directory")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != reference["replay_evidence_sha256"]:
                raise ValueError("replay evidence hash mismatch")
            replay = json.loads(raw)
            if reference["candidate_id"] != payload["recording_id"]:
                raise ValueError("another candidate's evidence")
            accepted = usable_cached_replay(payload, source_result, replay) or usable_cached_repair(
                payload, source_result, replay
            )
            if (
                not accepted
                or hashlib.sha256(accepted["text"].encode()).hexdigest() != row["text_sha256"]
                or accepted["source"] != row["source"]
            ):
                raise ValueError("alternative no longer meets the recorded identity")
            row.update(
                text=accepted["text"],
                source_metadata=accepted["source_metadata"],
                evidence_integrity_verified=True,
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError):
            row["error"] = "alternative_evidence_unavailable_or_invalid"
        alternatives.append(row)
    return alternatives


def pending_detail(engine, candidate_id, *, run_id=None, replay_root=None):
    if not inspect(engine).has_table(runs.name):
        return None
    with engine.connect() as conn:
        run = _run(conn, run_id)
        if not run:
            return None
        row = (
            conn.execute(
                select(candidates, blobs.c.body)
                .select_from(
                    candidates.outerjoin(blobs, candidates.c.text_sha256 == blobs.c.sha256)
                )
                .where(candidates.c.run_id == run.id, candidates.c.candidate_id == candidate_id)
            )
            .mappings()
            .first()
        )
        if not row:
            return None
        body = row["body"]
        if body is not None and hashlib.sha256(body.encode()).hexdigest() != row["text_sha256"]:
            raise ValueError("staged lyric body hash mismatch")
        return dict(
            run_id=run.id,
            candidate_id=row["candidate_id"],
            payload=row["payload"],
            acquisition_status=row["acquisition_status"],
            text=body,
            text_sha256=row["text_sha256"],
            blob_integrity_verified=body is not None,
            source_result=row["source_result"],
            audit=row["audit"],
            alternatives=load_conflicting_alternatives(
                row["payload"],
                row["source_result"],
                replay_root or Path.cwd() / "data/derived/lyrics/quota-20261030/offline-replay",
            ),
            classification_ready=False,
            identity_validated=False,
            completeness_validated=False,
            rights_status="UNVERIFIED",
        )
