"""Evidence-only lyric intake for newly incorporated global annual memberships."""

import hashlib
import json
import sqlite3
from pathlib import Path

from sqlalchemy import select, text

from chart_observatory.ingestion.import_quotas import recovery_targets
from chart_observatory.ingestion.quota_boundary import validate_quota_memberships
from chart_observatory.lyrics.identity_collisions import flag_shared_text_identities
from chart_observatory.lyrics.quota_discovery import (
    audit_saved_result,
    usable_cached_repair,
    usable_cached_replay,
)
from chart_observatory.lyrics.quota_staging import blobs, candidates, persist_lyric_staging, runs
from chart_observatory.lyrics.source_chain import verify_source_chain
from chart_observatory.lyrics.text_quality import prepare_lyric_derivative


def read_rows(path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def plan_global(base, legacy):
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    if manifest["protocol"] != "worldwide-annual-quotas-v1":
        raise ValueError("unsupported global annual protocol")
    for name, expected in manifest["output_hashes"].items():
        path = (base / name).resolve()
        if not path.is_relative_to(base.resolve()):
            raise ValueError("global artifact outside selection directory")
        with path.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                raise ValueError("global selection artifact changed: " + name)
    members = read_rows(base / "combined.jsonl")
    countries = json.loads((base / "countries.json").read_text(encoding="utf-8"))
    quotas = {
        c["country_code"]: c["quota_per_year_main"]
        for c in countries
        if c["quota_per_year_main"] is not None
    }
    validate_quota_memberships(members, quotas)
    indexed = {(r["country_code"], r["year"], r["position"]): r for r in members}
    old_ids = set()
    preserved = 0
    with (legacy / "combined.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if indexed.get((row["country_code"], row["year"], row["position"])) != row:
                raise ValueError("global intake changed a preserved legacy membership")
            old_ids.add(row["candidate_id"])
            preserved += 1
    targets = recovery_targets(members)
    for task in targets:
        task["cohort_version"] = manifest["protocol"]
    delta = {p["recording_id"] for p in targets} - old_ids
    return (
        targets,
        delta,
        dict(
            unique_candidates=len(targets),
            new_candidates=len(delta),
            memberships=len(members),
            preserved_legacy_memberships=preserved,
            country_year_cells=manifest["country_year_cells"],
            countries=manifest["countries"],
            public_delta_only=True,
            classification_ready=False,
            paid_calls_authorized=0,
            legacy_paid_scope_cap_exceeded=len(targets) > 30000,
        ),
    )


def seed_exact_native_results(store, targets, legacy_store):
    """Reuse only the same native candidate, checking its immutable original bytes."""
    wanted = {t["recording_id"] for t in targets}
    reused = 0
    for payload in targets:
        store.enqueue(payload["recording_id"], payload)
    with sqlite3.connect(
        (legacy_store / "acquisition.sqlite").as_uri() + "?mode=ro", uri=True
    ) as old:
        for key, raw in old.execute("SELECT identity,result FROM tasks"):
            if key not in wanted or not raw:
                continue
            current = store.conn.execute(
                "SELECT result FROM tasks WHERE identity=?", (key,)
            ).fetchone()[0]
            if current and json.loads(current).get("text_sha256"):
                continue
            result = json.loads(raw)
            if not result.get("text_path") or not result.get("text_sha256"):
                continue
            body = Path(result["text_path"]).read_bytes()
            if hashlib.sha256(body).hexdigest() != result["text_sha256"]:
                raise ValueError("legacy lyric blob hash mismatch")
            store.finish(
                key,
                {
                    **result,
                    "text": body.decode("utf-8"),
                    "status": "reused_pending_validation",
                    "copied_from_exact_native_id": key,
                    "previous_result_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                },
            )
            reused += 1
    return reused


def recovery_replacement_hash(db, key, result):
    """Bind a fresh result to the old blob recorded before its actual request."""
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "recovery_attempts" not in tables:
        return None
    hashes = set()
    for previous, returned in db.execute(
        "SELECT previous_result,result FROM recovery_attempts "
        "WHERE identity=? AND state='finished'",
        (key,),
    ):
        old = json.loads(previous) if previous else {}
        fresh = json.loads(returned) if returned else {}
        if old.get("text_sha256") and all(
            result.get(field) == fresh.get(field)
            for field in (
                "source",
                "source_metadata",
                "http_evidence",
                "identity_check",
            )
        ):
            hashes.add(old["text_sha256"])
    return next(iter(hashes)) if len(hashes) == 1 else None


def fresh_global_overlay(
    payload, current_result, body, digest, entry, *, replacement_hash=None, evidence_root
):
    """Fill a legacy gap or repair an explicitly hash-bound flagged result only.

    Download success is insufficient: the exact ID/name binding, text bytes,
    saved source response and existing replacement validators all must agree.
    """
    status, acquired_payload, fresh = entry
    if digest and (body is None or hashlib.sha256(body.encode()).hexdigest() != digest):
        raise ValueError("inherited global lyric blob hash mismatch")
    if not fresh.get("text_sha256") or not fresh.get("text_path"):
        return None, "no_fresh_text"
    path = Path(fresh["text_path"]).resolve()
    if not path.is_relative_to(Path(evidence_root).resolve()):
        raise ValueError("global acquisition text outside evidence root")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != fresh["text_sha256"]:
        raise ValueError("fresh global acquisition blob hash mismatch")
    if digest == fresh["text_sha256"]:
        return None, "same_text_preserved"
    proposal = dict(payload=acquired_payload, result={**fresh, "text": raw.decode("utf-8")})
    if digest is None:
        accepted = usable_cached_replay(payload, current_result, proposal)
    else:
        if replacement_hash != digest:
            return None, "missing_or_stale_replacement_binding"
        proposal.update(replay_kind="flagged_repair", replaces_text_sha256=replacement_hash)
        baseline = {**current_result, "text_sha256": digest}
        quality = prepare_lyric_derivative(body, baseline.get("source", "UNKNOWN"))
        baseline["text_quality_flags"] = sorted(
            set(baseline.get("text_quality_flags", [])) | set(quality.flags)
        )
        accepted = usable_cached_repair(payload, baseline, proposal)
    if not accepted:
        return None, "fresh_identity_or_quality_not_eligible"
    chain = verify_source_chain(
        payload, fresh, accepted["text"], fresh["text_sha256"], evidence_root
    )
    if chain["status"] != "source_chain_matched":
        return None, chain["status"]
    updated = {k: v for k, v in accepted.items() if k != "text"}
    updated.update(
        text_sha256=fresh["text_sha256"],
        global_acquisition_overlay=True,
        source_acquisition_candidate_id=payload["recording_id"],
        source_chain_check=chain,
    )
    if digest:
        updated["replaced_unverified_result"] = current_result
        updated["replaces_text_sha256"] = digest
    return (accepted["text"], fresh["text_sha256"], status, updated), "accepted"


def stage_global(engine, base, legacy, store_root, progress=None, *, evidence_root=None):
    evidence_root = Path(evidence_root or Path(__file__).resolve().parents[3]).resolve()
    targets, delta, summary = plan_global(base, legacy)
    with engine.connect() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        old_run = conn.execute(
            select(runs.c.id)
            .where(runs.c.manifest["selection_root"].as_string() == str(legacy))
            .order_by(runs.c.created_at.desc())
            .limit(1)
        ).scalar_one()
        inherited = {
            r["candidate_id"]: dict(r)
            for r in conn.execute(
                select(candidates, blobs.c.body)
                .outerjoin(blobs, candidates.c.text_sha256 == blobs.c.sha256)
                .where(candidates.c.run_id == old_run)
            ).mappings()
        }
    with sqlite3.connect((store_root / "acquisition.sqlite").as_uri() + "?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        acquired = {
            key: (status, json.loads(payload), json.loads(raw) if raw else {})
            for key, status, payload, raw in db.execute(
                "SELECT identity,status,payload,result FROM tasks"
            )
        }
        replacement_hashes = {
            key: recovery_replacement_hash(db, key, result)
            for key, (_status, _payload, result) in acquired.items()
            if key not in delta
        }
    offline = {}
    for path in (store_root / "offline-replay").glob("*.json"):
        if path.name.endswith(".outcome.json"):
            continue
        raw = path.read_bytes()
        proposal = json.loads(raw)
        offline.setdefault(proposal["payload"]["recording_id"], []).append((path, raw, proposal))
    records, texts = [], {}
    gap_fills = repairs = rejected_overlays = 0
    for i, payload in enumerate(targets, 1):
        key = payload["recording_id"]
        overlay_check = None
        if key not in delta:
            previous = inherited.get(key)
            if previous is None:
                raise ValueError("legacy lyric staging candidate is missing")
            result = dict(previous["source_result"])
            body, digest, status = (
                previous["body"],
                previous["text_sha256"],
                previous["acquisition_status"],
            )
            if key in acquired:
                overlay, overlay_check = fresh_global_overlay(
                    payload,
                    result,
                    body,
                    digest,
                    acquired[key],
                    replacement_hash=replacement_hashes.get(key),
                    evidence_root=evidence_root,
                )
                if overlay:
                    gap_fills += digest is None
                    repairs += digest is not None
                    body, digest, status, result = overlay
                elif overlay_check not in {"no_fresh_text", "same_text_preserved"}:
                    rejected_overlays += 1
        else:
            status, _acquired_payload, result = acquired.get(key, ("pending", {}, {}))
            result = dict(result)
            digest = result.get("text_sha256")
            body = Path(result["text_path"]).read_bytes().decode("utf-8") if digest else None
        options = {}
        for path, raw, proposal in offline.get(key, []):
            accepted = usable_cached_replay(payload, result, proposal) or usable_cached_repair(
                payload, result, proposal
            )
            if accepted:
                options[hashlib.sha256(accepted["text"].encode()).hexdigest()] = (
                    accepted,
                    path,
                    raw,
                )
        if len(options) == 1:
            new_hash, (accepted, path, raw) = next(iter(options.items()))
            previous_result = result if digest else None
            body, digest, status = accepted["text"], new_hash, "candidate_pending_validation"
            result = {k: v for k, v in accepted.items() if k != "text"}
            result.update(
                text_sha256=digest,
                offline_replay_evidence_file=str(path),
                offline_replay_evidence_sha256=hashlib.sha256(raw).hexdigest(),
            )
            if previous_result:
                result["replaced_unverified_result"] = previous_result
        audit = audit_saved_result(payload, result)
        if overlay_check not in {None, "no_fresh_text", "same_text_preserved"}:
            audit["fresh_global_acquisition_check"] = overlay_check
        if len(options) > 1:
            audit["text_quality_flags"].append("conflicting_offline_replays")
        if body is not None:
            if hashlib.sha256(body.encode()).hexdigest() != digest:
                raise ValueError("global lyric blob hash mismatch")
            quality = prepare_lyric_derivative(body, result.get("source", "UNKNOWN"))
            audit["text_quality_flags"] = sorted(
                set(audit["text_quality_flags"]) | set(quality.flags)
            )
            texts[digest] = body
        records.append(
            dict(
                candidate_id=key,
                text_sha256=digest,
                acquisition_status=status,
                payload=payload,
                source_result=result,
                audit=audit,
            )
        )
        if progress and i % 500 == 0:
            progress(i, len(targets))
    flag_shared_text_identities(records)
    manifest = dict(
        summary,
        selection_root=str(base),
        legacy_lyric_run_id=old_run,
        global_manifest_sha256=hashlib.sha256((base / "manifest.json").read_bytes()).hexdigest(),
        text_candidates=sum(bool(r["text_sha256"]) for r in records),
        global_acquisition_gap_fills=gap_fills,
        global_acquisition_repairs=repairs,
        global_acquisition_overlay_rejections=rejected_overlays,
        state="pending_identity_integrity_and_rights_review",
    )
    return {**persist_lyric_staging(engine, manifest, records, texts), **manifest}
