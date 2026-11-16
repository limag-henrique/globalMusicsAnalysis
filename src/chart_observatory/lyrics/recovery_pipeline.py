"""End-to-end lyrics recovery, reconciliation, technical verification, and PG parity."""

from __future__ import annotations

import base64
import hashlib
import json
import msvcrt
import shutil
import sqlite3
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import insert, select, text
from sqlalchemy.engine import Engine

from chart_observatory.ingestion.import_quotas import recovery_targets
from chart_observatory.lyrics.corpus_quality import assess_acquired_lyric
from chart_observatory.lyrics.identity_collisions import flag_shared_text_identities
from chart_observatory.lyrics.inventory_export import PARSER_VERSION, candidate_technical_status
from chart_observatory.lyrics.quota_acquisition import (
    AcquisitionStore,
    PacedHTTP,
    identity,
    recovery_cache_sources,
)
from chart_observatory.lyrics.quota_discovery import (
    audit_saved_result,
    recover_with_fallback,
)
from chart_observatory.lyrics.quota_staging import (
    blobs,
    candidates,
    metadata,
    persist_lyric_staging,
    runs,
)
from chart_observatory.lyrics.source_chain import verify_source_chain
from chart_observatory.lyrics.text_quality import prepare_lyric_derivative
from chart_observatory.research_flow import load_selection


def _parse_utc_timestamp(raw: str | datetime) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(raw))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def replay_sqlite_staging_runs(
    sqlite_run_specs: list[tuple[Path, list[str] | None]],
    pg_engine: Engine,
) -> list[dict[str, Any]]:
    """Replay preserved SQLite staging snapshots into PostgreSQL idempotently."""
    summary: list[dict[str, Any]] = []
    for sqlite_path, target_run_ids in sqlite_run_specs:
        resolved = sqlite_path.resolve()
        with sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True) as sdb:
            if target_run_ids is None:
                run_rows = sdb.execute(
                    "SELECT id, manifest, created_at FROM quota_lyric_staging_runs "
                    "ORDER BY created_at"
                ).fetchall()
            else:
                placeholders = ",".join("?" for _ in target_run_ids)
                run_rows = sdb.execute(
                    f"SELECT id, manifest, created_at FROM quota_lyric_staging_runs "
                    f"WHERE id IN ({placeholders}) ORDER BY created_at",
                    tuple(target_run_ids),
                ).fetchall()
            for run_id, manifest_raw, created_raw in run_rows:
                with pg_engine.connect() as conn:
                    already = conn.execute(
                        select(runs.c.id).where(runs.c.id == run_id)
                    ).scalar_one_or_none()
                if already:
                    summary.append({"run_id": run_id, "inserted": False, "source": str(resolved)})
                    continue

                manifest_obj = json.loads(manifest_raw)
                cand_rows = sdb.execute(
                    "SELECT candidate_id, text_sha256, acquisition_status, payload, "
                    "source_result, audit, classification_ready, identity_validated, "
                    "completeness_validated, rights_status "
                    "FROM quota_lyric_staging_candidates WHERE run_id=? ORDER BY candidate_id",
                    (run_id,),
                ).fetchall()
                needed_hashes = sorted({r[1] for r in cand_rows if r[1]})
                blob_map: dict[str, tuple[str, int]] = {}
                for off in range(0, len(needed_hashes), 500):
                    chunk = needed_hashes[off : off + 500]
                    ph = ",".join("?" for _ in chunk)
                    for sha, body, chars in sdb.execute(
                        f"SELECT sha256, body, characters FROM quota_lyric_staging_blobs "
                        f"WHERE sha256 IN ({ph})",
                        tuple(chunk),
                    ):
                        if hashlib.sha256(body.encode("utf-8")).hexdigest() != sha:
                            raise ValueError(f"local blob hash mismatch during replay: {sha}")
                        blob_map[sha] = (body, int(chars))

                with pg_engine.begin() as conn:
                    if conn.dialect.name == "postgresql":
                        conn.execute(text("SELECT pg_advisory_xact_lock(2026103101)"))
                    metadata.create_all(conn)
                    if conn.execute(
                        select(runs.c.id).where(runs.c.id == run_id)
                    ).scalar_one_or_none():
                        summary.append({"run_id": run_id, "inserted": False})
                        continue
                    existing_shas: set[str] = set()
                    for off in range(0, len(needed_hashes), 500):
                        chunk = needed_hashes[off : off + 500]
                        for sha, existing_body in conn.execute(
                            select(blobs.c.sha256, blobs.c.body).where(blobs.c.sha256.in_(chunk))
                        ):
                            if existing_body != blob_map[sha][0]:
                                raise ValueError(f"PostgreSQL blob conflict for {sha}")
                            existing_shas.add(sha)
                    missing_blobs = [
                        {"sha256": sha, "body": body, "characters": chars}
                        for sha, (body, chars) in blob_map.items()
                        if sha not in existing_shas
                    ]
                    for off in range(0, len(missing_blobs), 500):
                        conn.execute(insert(blobs), missing_blobs[off : off + 500])
                    conn.execute(
                        insert(runs),
                        {
                            "id": run_id,
                            "manifest": manifest_obj,
                            "created_at": _parse_utc_timestamp(created_raw),
                        },
                    )
                    batch = [
                        {
                            "run_id": run_id,
                            "candidate_id": r[0],
                            "text_sha256": r[1],
                            "acquisition_status": r[2],
                            "payload": json.loads(r[3]),
                            "source_result": json.loads(r[4]),
                            "audit": json.loads(r[5]),
                            "classification_ready": False,
                            "identity_validated": False,
                            "completeness_validated": False,
                            "rights_status": "UNVERIFIED",
                        }
                        for r in cand_rows
                    ]
                    for off in range(0, len(batch), 500):
                        conn.execute(insert(candidates), batch[off : off + 500])
                summary.append(
                    {
                        "run_id": run_id,
                        "inserted": True,
                        "candidates": len(cand_rows),
                        "new_blobs": len(missing_blobs),
                        "source": str(resolved),
                    }
                )
    return summary


def load_sqlite_staging_snapshot(
    sqlite_path: Path, run_id: str
) -> tuple[dict[str, Any], str, dict[str, dict[str, Any]], dict[str, str]]:
    """Load one immutable staging run and verify every blob SHA-256."""
    with sqlite3.connect(sqlite_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        run_row = db.execute(
            "SELECT manifest, created_at FROM quota_lyric_staging_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        if not run_row:
            raise ValueError(f"staging run not found: {run_id} in {sqlite_path}")
        manifest = json.loads(run_row[0])
        created_at = str(run_row[1])
        records: dict[str, dict[str, Any]] = {}
        texts: dict[str, str] = {}
        for cid, pl_raw, sr_raw, au_raw, st, tsha, body in db.execute(
            "SELECT c.candidate_id, c.payload, c.source_result, c.audit, "
            "c.acquisition_status, c.text_sha256, b.body "
            "FROM quota_lyric_staging_candidates c "
            "LEFT JOIN quota_lyric_staging_blobs b ON c.text_sha256 = b.sha256 "
            "WHERE c.run_id=? ORDER BY c.candidate_id",
            (run_id,),
        ):
            if tsha:
                if (
                    not isinstance(body, str)
                    or hashlib.sha256(body.encode("utf-8")).hexdigest() != tsha
                ):
                    raise ValueError(f"staging blob hash mismatch for {cid}: {tsha}")
                texts[tsha] = body
            records[cid] = {
                "candidate_id": cid,
                "payload": json.loads(pl_raw),
                "source_result": json.loads(sr_raw),
                "audit": json.loads(au_raw),
                "acquisition_status": st,
                "text_sha256": tsha,
            }
        return manifest, created_at, records, texts


def _evidence_rank(
    rec: dict[str, Any],
    texts: dict[str, str],
    root: Path,
) -> tuple[bool, bool, bool, int, str]:
    """Score candidate quality without relying on staging timestamp."""
    digest = rec.get("text_sha256")
    if not digest or digest not in texts:
        return (False, False, False, -999, "unavailable")
    body = texts[digest]
    payload = rec["payload"]
    sr = rec["source_result"]
    audit = audit_saved_result(payload, sr)
    assessed = assess_acquired_lyric(payload, sr, body, digest)
    chain = verify_source_chain(payload, sr, body, digest, root)
    not_quarantined = not bool(audit.get("source_quarantined"))
    chain_ok = chain.get("status") in {
        "source_chain_matched",
        "source_chain_match_metadata_pending",
    }
    clean_quality = assessed["quality_state"] == "acquired_unverified"
    return (
        not_quarantined,
        chain_ok,
        clean_quality,
        -len(assessed.get("flags", [])),
        chain.get("status") or "unknown",
    )


def reconcile_v4_staging_runs(
    f593_path: Path,
    f593_id: str,
    c15da_path: Path,
    c15da_id: str,
    b85_path: Path,
    b85_id: str,
    root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, Any], list[dict[str, Any]]]:
    """Reconcile baseline, Codex, and Antigravity staging runs with provenance checks."""
    m_f, t_f, r_f, txt_f = load_sqlite_staging_snapshot(f593_path, f593_id)
    m_c, t_c, r_c, txt_c = load_sqlite_staging_snapshot(c15da_path, c15da_id)
    m_a, t_a, r_a, txt_a = load_sqlite_staging_snapshot(b85_path, b85_id)

    all_keys = sorted(r_a)
    if set(all_keys) != set(r_f) or set(all_keys) != set(r_c):
        raise ValueError("staging runs do not share identical v4 candidate sets")

    def _pos_texts(recs: dict[str, dict[str, Any]]) -> int:
        return sum(
            len(v["payload"]["chart_bindings"]) for v in recs.values() if v.get("text_sha256")
        )

    merged: dict[str, dict[str, Any]] = {}
    merged_texts: dict[str, str] = {}
    diff_ledger: list[dict[str, Any]] = []
    conflicts_15da_vs_b85c = 0
    adopted_from_15da = 0
    adopted_from_b85c = 0

    for cid in all_keys:
        ra = r_a[cid]
        rc = r_c[cid]
        sa = ra.get("text_sha256")
        sc = rc.get("text_sha256")
        if sa == sc:
            chosen = json.loads(json.dumps(ra))
            merged[cid] = chosen
            if sa:
                merged_texts[sa] = txt_a[sa]
            continue

        if sc and not sa:
            body_c = txt_c[sc]
            assessed_c = assess_acquired_lyric(rc["payload"], rc["source_result"], body_c, sc)
            chain_c = verify_source_chain(rc["payload"], rc["source_result"], body_c, sc, root)
            chosen = json.loads(json.dumps(rc))
            chosen["source_result"] = {
                **chosen["source_result"],
                "reconciled_from_run_id": c15da_id,
                "reconciliation_reason": "present_verified_in_15da3853_absent_in_b85c4d84",
                "reconciliation_chain_status": chain_c.get("status"),
            }
            merged[cid] = chosen
            merged_texts[sc] = body_c
            adopted_from_15da += 1
            diff_ledger.append(
                {
                    "candidate_id": cid,
                    "change_kind": "cross_run_reconciliation_fill",
                    "repair_method": f"adopted_from_run:{c15da_id[:12]}",
                    "old_text_sha256": None,
                    "old_source_system": None,
                    "old_status": "missing_in_b85c4d84",
                    "new_text_sha256": sc,
                    "new_source_system": rc["source_result"].get("source"),
                    "new_status": assessed_c["quality_state"],
                    "source_chain_status": chain_c.get("status"),
                    "verified_at": datetime.now(UTC).isoformat(),
                }
            )
        elif sa and not sc:
            chosen = json.loads(json.dumps(ra))
            chosen["source_result"] = {
                **chosen["source_result"],
                "reconciled_from_run_id": b85_id,
                "reconciliation_reason": "present_verified_in_b85c4d84_absent_in_15da3853",
            }
            merged[cid] = chosen
            merged_texts[sa] = txt_a[sa]
            adopted_from_b85c += 1
        else:
            # Both non-null with differing hashes: score by evidence quality, never timestamp.
            conflicts_15da_vs_b85c += 1
            score_a = _evidence_rank(ra, txt_a, root)
            score_c = _evidence_rank(rc, txt_c, root)
            winner, w_txt, w_run = (
                (ra, txt_a, b85_id) if score_a[:4] >= score_c[:4] else (rc, txt_c, c15da_id)
            )
            chosen = json.loads(json.dumps(winner))
            chosen["source_result"] = {
                **chosen["source_result"],
                "reconciled_from_run_id": w_run,
                "reconciliation_reason": "evidence_scored_conflict_resolution",
                "alternate_run_text_sha256": sc if w_run == b85_id else sa,
            }
            merged[cid] = chosen
            merged_texts[winner["text_sha256"]] = w_txt[winner["text_sha256"]]

    report = {
        "reconciled_at": datetime.now(UTC).isoformat(),
        "runs": {
            "f59314e5": {
                "run_id": f593_id,
                "created_at": t_f,
                "selection_root": m_f.get("selection_root"),
                "phase": m_f.get("phase"),
                "candidates_with_text": sum(bool(v.get("text_sha256")) for v in r_f.values()),
                "position_linked_texts": _pos_texts(r_f),
            },
            "15da3853": {
                "run_id": c15da_id,
                "created_at": t_c,
                "selection_root": m_c.get("selection_root"),
                "phase": m_c.get("phase"),
                "candidates_with_text": sum(bool(v.get("text_sha256")) for v in r_c.values()),
                "position_linked_texts": _pos_texts(r_c),
            },
            "b85c4d84": {
                "run_id": b85_id,
                "created_at": t_a,
                "selection_root": m_a.get("selection_root"),
                "phase": m_a.get("phase"),
                "candidates_with_text": sum(bool(v.get("text_sha256")) for v in r_a.values()),
                "position_linked_texts": _pos_texts(r_a),
            },
        },
        "reconciled_v4_candidates_with_text": sum(
            bool(v.get("text_sha256")) for v in merged.values()
        ),
        "reconciled_v4_position_linked_texts": _pos_texts(merged),
        "adopted_from_15da3853": adopted_from_15da,
        "only_in_b85c4d84_vs_15da3853": adopted_from_b85c,
        "hash_conflicts_15da3853_vs_b85c4d84": conflicts_15da_vs_b85c,
        "f59314e5_to_b85c4d84_gain_candidates": sum(
            1 for k in all_keys if r_a[k].get("text_sha256") and not r_f[k].get("text_sha256")
        ),
        "f59314e5_to_b85c4d84_gain_positions": _pos_texts(r_a) - _pos_texts(r_f),
    }
    return merged, merged_texts, report, diff_ledger


def build_v5_records(
    v5_selection_dir: Path,
    v4_records: dict[str, dict[str, Any]],
    v4_texts: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], dict[str, str], set[str]]:
    """Build v5 record map preserving v4 records and adding distinct v5 Slovenia targets."""
    _, _, members, _ = load_selection(v5_selection_dir)
    targets = recovery_targets(members)
    v5_records: dict[str, dict[str, Any]] = {}
    v5_texts: dict[str, str] = {}
    v5_only_ids: set[str] = set()
    for payload in targets:
        cid = payload["recording_id"]
        if cid in v4_records:
            rec = json.loads(json.dumps(v4_records[cid]))
            # Keep v4 bindings untouched unless v5 extended payload bindings; use v5 payload
            rec["payload"] = payload
            v5_records[cid] = rec
            if rec.get("text_sha256"):
                v5_texts[rec["text_sha256"]] = v4_texts[rec["text_sha256"]]
        else:
            v5_only_ids.add(cid)
            payload_v5 = {
                **payload,
                "cohort_version": "global-rescan-2018-2026-20261115-v5-published-provisional-0003",
                "provisional_overlay": True,
            }
            v5_records[cid] = {
                "candidate_id": cid,
                "payload": payload_v5,
                "source_result": {"status": "not_enqueued"},
                "audit": audit_saved_result(payload_v5, {}),
                "acquisition_status": "pending",
                "text_sha256": None,
            }
    return v5_records, v5_texts, v5_only_ids


class CacheOnlyHTTP(PacedHTTP):
    """Offline cache-only HTTP reader using shared http-cache directories with zero network."""

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        request = self.client.build_request("GET", url, **kwargs)
        key = str(request.url)
        cached_path = self.cache / f"{hashlib.sha256(key.encode()).hexdigest()}.json"
        with self._reuse_guard:
            if not cached_path.exists():
                for directory in self.cache_sources:
                    previous = directory / cached_path.name
                    if previous.exists() and self._borrowable(previous, key):
                        try:
                            cached_path.hardlink_to(previous)
                        except OSError:
                            shutil.copy2(previous, cached_path)
                        break
        if cached_path.exists():
            try:
                cached = json.loads(cached_path.read_text(encoding="utf-8"))
                raw = (
                    base64.b64decode(cached["body_base64"], validate=True)
                    if "body_base64" in cached
                    else cached["body"].encode("utf-8")
                )
                if hashlib.sha256(raw).hexdigest() == cached["body_sha256"]:
                    response = httpx.Response(
                        200,
                        content=raw,
                        headers={"content-type": cached.get("content_type") or "text/plain"},
                        request=httpx.Request("GET", cached.get("final_url", key)),
                    )
                    response.encoding = cached.get("encoding") or "utf-8"
                    self.trace.append(
                        {
                            "url": key,
                            "status": 200,
                            "cache_path": str(cached_path),
                            "body_sha256": cached["body_sha256"],
                            "cached": True,
                            "raw_bytes_preserved": True,
                        }
                    )
                    return response
            except (OSError, ValueError, KeyError, TypeError):
                pass
        return httpx.Response(404, request=request)


def _cell_availability(records: dict[str, dict[str, Any]]) -> dict[tuple[str, int], Counter[str]]:
    cells: dict[tuple[str, int], Counter[str]] = {}
    for rec in records.values():
        has_text = bool(rec.get("text_sha256"))
        for b in rec["payload"].get("chart_bindings", []):
            cell = cells.setdefault((b["country_code"], int(b["year"])), Counter())
            cell["known_positions"] += 1
            cell["positions_with_text"] += has_text
    return cells


def _deficient_cells(cells: dict[tuple[str, int], Counter[str]]) -> set[tuple[str, int]]:
    return {
        key
        for key, val in cells.items()
        if val["positions_with_text"] * 5 < val["known_positions"] * 4
    }


def build_prioritized_queue(
    records: dict[str, dict[str, Any]],
    *,
    include_quarantined: bool = True,
) -> list[dict[str, Any]]:
    """Prioritize deficient cells, multi-membership hits, missing & quarantined items."""
    cells = _cell_availability(records)
    low = _deficient_cells(cells)
    queued: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for cid, rec in records.items():
        has_text = bool(rec.get("text_sha256"))
        quarantined = bool((rec.get("audit") or {}).get("source_quarantined"))
        if has_text and not (include_quarantined and quarantined):
            continue
        bindings = rec["payload"].get("chart_bindings", [])
        low_hits = sum((b["country_code"], int(b["year"])) in low for b in bindings)
        best_pos = min((int(b["position"]) for b in bindings), default=999)
        sort_key = (
            not has_text,
            low_hits > 0,
            low_hits,
            len(bindings),
            -best_pos,
        )
        # Invert descending keys cleanly
        key = (
            0 if low_hits > 0 else 1,
            0 if not has_text else 1,
            -low_hits,
            -len(bindings),
            best_pos,
            cid,
        )
        _ = sort_key
        queued.append((key, rec["payload"]))
    queued.sort(key=lambda item: item[0])
    return [item[1] for item in queued]


def _accept_candidate_replacement(
    cid: str,
    payload: dict[str, Any],
    old_rec: dict[str, Any],
    fresh_result: dict[str, Any],
    texts: dict[str, str],
    root: Path,
    *,
    method_label: str,
    ledger_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], str] | None:
    """Apply a missing-fill or quarantined-LETRAS repair only if verified superior."""
    fresh_text = fresh_result.get("text")
    if not isinstance(fresh_text, str) or not fresh_text.strip():
        return None
    fresh_sha = hashlib.sha256(fresh_text.encode("utf-8")).hexdigest()
    fresh_src = (fresh_result.get("source") or "").upper()
    if fresh_src == "LETRAS" or fresh_result.get("quarantined_source"):
        return None

    old_sha = old_rec.get("text_sha256")
    old_audit = old_rec.get("audit") or {}
    was_quarantined = bool(old_audit.get("source_quarantined"))
    if old_sha and not was_quarantined:
        return None

    clean_sr = {k: v for k, v in fresh_result.items() if k != "text"}
    clean_sr["text_sha256"] = fresh_sha
    fresh_audit = audit_saved_result(payload, clean_sr)
    if fresh_audit.get("source_quarantined"):
        return None

    assessed = assess_acquired_lyric(payload, clean_sr, fresh_text, fresh_sha)
    if assessed["quality_state"] in {
        "source_declared_partial",
        "suspected_partial",
        "identity_conflict",
    }:
        return None

    chain = verify_source_chain(payload, clean_sr, fresh_text, fresh_sha, root)
    if old_sha and chain["status"] not in {
        "source_chain_matched",
        "source_chain_match_metadata_pending",
    }:
        # Repairing an existing v1/quarantined text requires verifiable HTTP source chain
        return None

    if old_sha:
        clean_sr["replaced_unverified_result"] = old_rec.get("source_result")
        clean_sr["replaces_text_sha256"] = old_sha
        clean_sr["repair_method"] = method_label
    fresh_audit["technical_verification"] = {
        "quality_state": assessed["quality_state"],
        "source_chain_status": chain.get("status"),
        "parser_version": PARSER_VERSION,
        "verified_at": datetime.now(UTC).isoformat(),
    }
    texts[fresh_sha] = fresh_text
    updated_rec = {
        "candidate_id": cid,
        "payload": payload,
        "source_result": clean_sr,
        "audit": fresh_audit,
        "acquisition_status": "candidate_pending_validation",
        "text_sha256": fresh_sha,
    }
    ledger_rows.append(
        {
            "candidate_id": cid,
            "change_kind": "v1_quarantined_replacement"
            if old_sha
            else "missing_candidate_recovery",
            "repair_method": method_label,
            "old_text_sha256": old_sha,
            "old_source_system": (old_rec.get("source_result") or {}).get("source"),
            "old_status": candidate_technical_status(old_rec),
            "new_text_sha256": fresh_sha,
            "new_source_system": fresh_src,
            "new_status": assessed["quality_state"],
            "source_chain_status": chain.get("status"),
            "verified_at": datetime.now(UTC).isoformat(),
        }
    )
    return updated_rec, fresh_sha


def run_offline_store_and_cache_pass(
    records: dict[str, dict[str, Any]],
    texts: dict[str, str],
    root: Path,
    temp_cache_dir: Path,
    legacy_store_dirs: list[Path],
    ledger_rows: list[dict[str, Any]],
    *,
    label: str = "v4",
) -> dict[str, int]:
    """Resolve missing & quarantined candidates purely from local stores and http-cache."""
    stats: Counter[str] = Counter()
    targets = build_prioritized_queue(records, include_quarantined=True)
    target_ids = {p["recording_id"] for p in targets}

    # 1. Exact candidate_id matches in legacy SQLite acquisition stores
    for st_dir in legacy_store_dirs:
        ap = st_dir / "acquisition.sqlite"
        if not ap.exists():
            continue
        with sqlite3.connect(ap.resolve().as_uri() + "?mode=ro", uri=True) as sdb:
            for cid, rraw in sdb.execute(
                "SELECT identity, result FROM tasks WHERE result IS NOT NULL"
            ):
                if cid not in target_ids:
                    continue
                rec = records[cid]
                if rec.get("text_sha256") and not (rec.get("audit") or {}).get(
                    "source_quarantined"
                ):
                    continue
                res = json.loads(rraw)
                tpath = res.get("text_path")
                tsha = res.get("text_sha256")
                if not tpath or not tsha:
                    continue
                p_txt = Path(tpath)
                if not p_txt.exists():
                    p_txt = st_dir / "texts" / f"{tsha}.txt"
                if not p_txt.exists():
                    continue
                body = p_txt.read_bytes().decode("utf-8", errors="replace")
                if hashlib.sha256(body.encode("utf-8")).hexdigest() != tsha:
                    continue
                res_with_text = {**res, "text": body}
                accepted = _accept_candidate_replacement(
                    cid,
                    rec["payload"],
                    rec,
                    res_with_text,
                    texts,
                    root,
                    method_label=f"store_exact:{st_dir.name}:{label}",
                    ledger_rows=ledger_rows,
                )
                if accepted:
                    records[cid] = accepted[0]
                    stats["store_exact_recovered"] += 1

    # 2. Zero-network HTTP cache replay via CacheOnlyHTTP + updated recover_with_fallback
    remaining = build_prioritized_queue(records, include_quarantined=True)
    sources = recovery_cache_sources(root, temp_cache_dir)
    temp_cache_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=5) as client:
        http = CacheOnlyHTTP(
            temp_cache_dir,
            client,
            cache_sources=sources,
            interval=0.01,
        )
        for payload in remaining:
            cid = payload["recording_id"]
            rec = records[cid]
            try:
                res = recover_with_fallback(
                    payload["title"],
                    payload["artist"],
                    http,
                    first_time=True,
                    metadata_resolution=payload.get("metadata_resolution"),
                )
            except (httpx.HTTPError, ValueError):
                continue
            accepted = _accept_candidate_replacement(
                cid,
                payload,
                rec,
                res,
                texts,
                root,
                method_label=f"http_cache_replay:{label}",
                ledger_rows=ledger_rows,
            )
            if accepted:
                records[cid] = accepted[0]
                stats["http_cache_recovered"] += 1
    return dict(stats)


def _load_exhausted_ids(stores: tuple[Path, ...]) -> set[str]:
    exhausted: set[str] = set()
    for store_root in stores:
        db_path = Path(store_root) / "acquisition.sqlite"
        if not db_path.exists():
            continue
        with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True) as sdb:
            for (cid,) in sdb.execute(
                "SELECT identity FROM tasks WHERE status='not_found_or_unverified'"
            ):
                exhausted.add(cid)
    return exhausted


def run_bounded_live_recovery(
    records: dict[str, dict[str, Any]],
    texts: dict[str, str],
    root: Path,
    store_dir: Path,
    ledger_rows: list[dict[str, Any]],
    *,
    max_candidates: int = 120,
    max_seconds: int = 150,
    workers: int = 6,
    label: str = "v4",
    exclude_exhausted_stores: tuple[Path, ...] = (),
) -> dict[str, Any]:
    """Run bounded live HTTP acquisition over the prioritized remaining queue."""
    if max_candidates <= 0 or max_seconds <= 0:
        return {"attempted": 0, "recovered": 0, "skipped_live": True}

    prior_exhausted = _load_exhausted_ids(exclude_exhausted_stores)
    store_dir.mkdir(parents=True, exist_ok=True)
    owner = (store_dir / "owner.lock").open("a+b")
    owner.seek(0)
    if not owner.read(1):
        owner.write(b"0")
        owner.flush()
    owner.seek(0)
    msvcrt.locking(owner.fileno(), msvcrt.LK_NBLCK, 1)

    store = AcquisitionStore(store_dir)
    recovered = 0
    attempted = 0
    error_counts: Counter[str] = Counter()
    try:
        queue_payloads = build_prioritized_queue(records, include_quarantined=True)
        for payload in queue_payloads:
            store.enqueue(payload["recording_id"], payload)
        with store.conn:
            store.conn.execute("UPDATE tasks SET status='pending' WHERE status='running'")

        to_run: list[dict[str, Any]] = []
        skipped_prior_exhausted = 0
        for payload in queue_payloads:
            cid = payload["recording_id"]
            if cid in prior_exhausted:
                skipped_prior_exhausted += 1
                continue
            row = store.conn.execute(
                "SELECT status, result FROM tasks WHERE identity=?", (cid,)
            ).fetchone()
            # Retry items not yet attempted in this store (or previously only pending)
            if row and row[0] == "pending":
                to_run.append(payload)
            if len(to_run) >= max_candidates:
                break

        deadline = datetime.now(UTC) + timedelta(seconds=max_seconds)
        cooldown_path = (
            root / "data/derived/lyrics/quota-20261030/http-cache/provider-cooldowns.sqlite"
        )
        with httpx.Client(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "ChartObservatory/0.1 public lyric recovery"},
        ) as client:
            http = PacedHTTP(
                store_dir / "http-cache",
                client,
                interval=0.8,
                cache_sources=recovery_cache_sources(root, store_dir),
                cooldown_path=cooldown_path,
            )

            def acquire(payload: dict[str, Any]) -> dict[str, Any]:
                http.start_trace()
                try:
                    return recover_with_fallback(
                        payload["title"],
                        payload["artist"],
                        http,
                        first_time=True,
                        metadata_resolution=payload.get("metadata_resolution"),
                    )
                except (httpx.RequestError, ValueError) as exc:
                    return {"status": "retrieval_error", "error_type": type(exc).__name__}

            iterator = iter(to_run)
            with ThreadPoolExecutor(max_workers=workers) as executor:
                inflight: dict[Any, str] = {}
                exhausted = False
                while inflight or not exhausted:
                    while len(inflight) < workers and not exhausted:
                        if datetime.now(UTC) >= deadline:
                            exhausted = True
                            break
                        nxt = next(iterator, None)
                        if nxt is None:
                            exhausted = True
                            break
                        if store.claim(nxt["recording_id"]):
                            inflight[executor.submit(acquire, nxt)] = nxt["recording_id"]
                    if not inflight:
                        break
                    done, _ = wait(inflight, timeout=20, return_when=FIRST_COMPLETED)
                    for future in done:
                        cid = inflight.pop(future)
                        res = future.result()
                        store.finish(cid, res)
                        attempted += 1
                        rec = records[cid]
                        accepted = _accept_candidate_replacement(
                            cid,
                            rec["payload"],
                            rec,
                            res,
                            texts,
                            root,
                            method_label=f"live_http:{label}",
                            ledger_rows=ledger_rows,
                        )
                        if accepted:
                            records[cid] = accepted[0]
                            recovered += 1
                        else:
                            for err in res.get("source_errors") or []:
                                error_counts[err] += 1
                            if not rec.get("text_sha256"):
                                updated_sr = {k: v for k, v in res.items() if k != "text"}
                                records[cid] = {
                                    **rec,
                                    "source_result": updated_sr,
                                    "acquisition_status": res.get("status")
                                    or "not_found_or_unverified",
                                    "audit": audit_saved_result(rec["payload"], updated_sr),
                                }
        return {
            "attempted": attempted,
            "recovered": recovered,
            "queued_total": len(queue_payloads),
            "skipped_prior_exhausted": skipped_prior_exhausted,
            "sample_errors": dict(error_counts.most_common(12)),
        }
    finally:
        store.conn.close()
        with suppress(OSError):
            msvcrt.locking(owner.fileno(), msvcrt.LK_UNLCK, 1)
        owner.close()


def apply_pg_v1_clean_fallback(
    records: dict[str, dict[str, Any]],
    texts: dict[str, str],
    pg_engine: Engine,
    ledger_rows: list[dict[str, Any]],
    *,
    label: str = "v4",
) -> dict[str, int]:
    """Reuse non-LETRAS PostgreSQL docs for unresolved items, flagged as existing_document_id."""
    targets = build_prioritized_queue(records, include_quarantined=True)
    if not targets:
        return {"pg_fallback_applied": 0}

    wanted_pairs = {(identity(p["title"]), identity(p["artist"])) for p in targets}
    if not wanted_pairs:
        return {"pg_fallback_applied": 0}

    with pg_engine.connect() as conn:
        conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        rows = conn.execute(
            text("""
            SELECT ct.id AS ct_id, ct.title,
                   COALESCE(string_agg(DISTINCT a.name, ' | '), '') AS artists,
                   ld.id AS doc_id, ld.source, ld.content_sha256, ld.text
            FROM canonical_tracks ct
            JOIN track_artists ta ON ta.track_id = ct.id
            JOIN artists a ON a.id = ta.artist_id
            JOIN lyric_documents ld ON ld.canonical_track_id = ct.id
            WHERE ld.text IS NOT NULL AND length(trim(ld.text)) > 0
              AND upper(ld.source) != 'LETRAS'
            GROUP BY ct.id, ct.title, ld.id, ld.source, ld.content_sha256, ld.text
            """)
        ).mappings()
        by_pair: dict[tuple[str, str], dict[str, Any]] = {}
        priority_rank = {"GENIUS": 0, "LRCLIB": 1, "AZLYRICS": 2, "MUSIXMATCH": 3, "LYRICS_OVH": 4}
        for row in rows:
            pair = (identity(row["title"]), identity(row["artists"]))
            if pair not in wanted_pairs:
                continue
            body = row["text"]
            sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if sha != row["content_sha256"]:
                continue
            deriv = prepare_lyric_derivative(body, row["source"])
            if any(
                "partial" in f or "residue" in f or "encoded" in f or "very_short" in f
                for f in deriv.flags
            ):
                continue
            src = row["source"].upper()
            rank = priority_rank.get(src, 9)
            existing = by_pair.get(pair)
            if existing is None or rank < existing["_rank"]:
                by_pair[pair] = {
                    "_rank": rank,
                    "doc_id": str(row["doc_id"]),
                    "ct_id": str(row["ct_id"]),
                    "source": src,
                    "text": body,
                    "text_sha256": sha,
                    "flags": list(deriv.flags),
                }

    applied = 0
    quarantined_replaced = 0
    for payload in targets:
        cid = payload["recording_id"]
        rec = records[cid]
        pair = (identity(payload["title"]), identity(payload["artist"]))
        doc = by_pair.get(pair)
        if not doc:
            continue
        old_sha = rec.get("text_sha256")
        was_q = bool((rec.get("audit") or {}).get("source_quarantined"))
        if old_sha and not was_q:
            continue
        sha = doc["text_sha256"]
        texts[sha] = doc["text"]
        sr = {
            "status": "reused_v1_pending_identity_review",
            "source": doc["source"],
            "text_sha256": sha,
            "identity_check": "cached_exact_metadata_not_recording_validation",
            "generated_by_ai": False,
            "text_quality_flags": doc["flags"],
            "source_metadata": {
                "existing_document_id": doc["doc_id"],
                "existing_canonical_track_id": doc["ct_id"],
                "observed_title": payload["title"],
                "observed_artist": payload["artist"],
                "requested_artist": payload["artist"],
                "match_basis": "normalized_exact_title_artist_v1_cohort",
            },
        }
        if old_sha:
            sr["replaced_unverified_result"] = rec.get("source_result")
            sr["replaces_text_sha256"] = old_sha
        audit = audit_saved_result(payload, sr)
        records[cid] = {
            "candidate_id": cid,
            "payload": payload,
            "source_result": sr,
            "audit": audit,
            "acquisition_status": "inherited_v1_exact_title_artist_pending_review",
            "text_sha256": sha,
        }
        applied += 1
        if was_q:
            quarantined_replaced += 1
        ledger_rows.append(
            {
                "candidate_id": cid,
                "change_kind": "v1_quarantined_replacement" if old_sha else "v1_cohort_reuse",
                "repair_method": f"postgres_lyric_documents_exact_pair:{label}",
                "old_text_sha256": old_sha,
                "old_source_system": (rec.get("source_result") or {}).get("source"),
                "old_status": candidate_technical_status(rec),
                "new_text_sha256": sha,
                "new_source_system": doc["source"],
                "new_status": "pending_adjudication",
                "existing_document_id": doc["doc_id"],
                "verified_at": datetime.now(UTC).isoformat(),
            }
        )
    return {"pg_fallback_applied": applied, "quarantined_replaced": quarantined_replaced}


def verify_all_candidates(
    records_map: dict[str, dict[str, Any]],
    texts: dict[str, str],
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run corpus quality, source-chain, and shared-text collision verification."""
    records = [records_map[k] for k in sorted(records_map)]
    status_counts: Counter[str] = Counter()
    chain_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    now_iso = datetime.now(UTC).isoformat()

    for rec in records:
        digest = rec.get("text_sha256")
        body = texts.get(digest) if digest else None
        rec["audit"] = audit_saved_result(rec["payload"], rec.get("source_result") or {})
        assessed = assess_acquired_lyric(
            rec["payload"], rec.get("source_result") or {}, body, digest
        )
        rec["audit"]["text_quality_flags"] = list(assessed.get("flags") or [])
        rec["audit"]["source_quarantined"] = bool(
            assessed.get("source_quarantined", rec["audit"].get("source_quarantined"))
        )

    # Flag cross-identity text collisions before finalizing technical status
    collisions = flag_shared_text_identities(records)

    for rec in records:
        digest = rec.get("text_sha256")
        body = texts.get(digest) if digest else None
        sr = rec.get("source_result") or {}
        assessed = assess_acquired_lyric(rec["payload"], sr, body, digest)
        # Merge shared-text collision flags added by flag_shared_text_identities
        merged_flags = sorted(
            set(assessed.get("flags") or []) | set(rec["audit"].get("text_quality_flags") or [])
        )
        rec["audit"]["text_quality_flags"] = merged_flags
        flag_counts.update(merged_flags)

        if digest and body is not None and (sr.get("http_evidence") or []):
            chain = verify_source_chain(rec["payload"], sr, body, digest, root)
        elif digest:
            chain = {"status": "no_http_evidence_recorded"}
        else:
            chain = {"status": "unavailable"}
        chain_counts[chain.get("status") or "unknown"] += 1

        raw_hashes = [
            ev.get("body_sha256")
            for ev in sr.get("http_evidence", [])
            if ev.get("status") == 200 and ev.get("body_sha256")
        ]
        # Recompute state cleanly incorporating shared-text flags
        qstate = assessed["quality_state"]
        if (
            digest
            and (
                "same_text_different_titles" in merged_flags
                or "same_text_different_performers" in merged_flags
            )
            and qstate == "acquired_unverified"
        ):
            qstate = "identity_conflict"
        if rec["audit"].get("source_quarantined"):
            tech_status = "quarantined_corrupt_source"
        else:
            tech_status = qstate

        rec["audit"]["technical_verification"] = {
            "quality_state": tech_status,
            "source_chain_status": chain.get("status"),
            "raw_response_sha256": chain.get("evidence_sha256")
            or (raw_hashes[-1] if raw_hashes else None),
            "extracted_text_sha256": digest,
            "parser_version": PARSER_VERSION,
            "scientific_approval_status": "not_approved",
            "classification_eligibility": "blocked_pending_gates",
            "verified_at": now_iso,
        }
        status_counts[tech_status] += 1

    summary = {
        "total_candidates": len(records),
        "candidates_with_text": sum(bool(r.get("text_sha256")) for r in records),
        "shared_text_collisions": len(collisions),
        "technical_status_counts": dict(status_counts),
        "source_chain_counts": dict(chain_counts),
        "top_quality_flags": dict(flag_counts.most_common(20)),
    }
    return records, summary


def fetch_postgres_cohort_metrics(pg_engine: Engine) -> dict[str, Any]:
    """Return read-only imported-song cohort counts separate from research scope."""
    with pg_engine.connect() as conn:
        conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        row = (
            conn.execute(
                text("""
            SELECT
                (SELECT count(*) FROM canonical_tracks) AS canonical_tracks,
                (SELECT count(*) FROM lyric_documents) AS lyric_documents,
                (SELECT count(DISTINCT canonical_track_id) FROM lyric_documents
                 WHERE text IS NOT NULL AND length(trim(text)) > 0) AS tracks_with_text,
                (SELECT count(*) FROM lyric_documents
                 WHERE rights_status = 'AUTHORIZED') AS docs_rights_authorized,
                (SELECT count(*) FROM lyric_classification_snapshots)
                 AS classification_snapshots
            """)
            )
            .mappings()
            .one()
        )
        sources = conn.execute(
            text("SELECT source, count(*) FROM lyric_documents GROUP BY source ORDER BY 2 DESC")
        ).fetchall()
    return {
        "canonical_tracks": int(row["canonical_tracks"]),
        "lyric_documents": int(row["lyric_documents"]),
        "tracks_with_text": int(row["tracks_with_text"]),
        "docs_with_scientific_g2_approval": 0,
        "docs_rights_authorized": int(row["docs_rights_authorized"]),
        "classification_snapshots": int(row["classification_snapshots"]),
        "documents_by_source": {str(s): int(c) for s, c in sources},
        "note": (
            "Historical imported cohort metrics kept strictly separate "
            "from frozen v4/v5 research scopes."
        ),
    }


def persist_verified_staging(
    records: list[dict[str, Any]],
    texts: dict[str, str],
    *,
    selection_dir: Path,
    local_sqlite_path: Path,
    pg_engine: Engine,
    phase: str,
    memberships_count: int,
    extra_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist reconciled snapshot to both local SQLite and PostgreSQL with v2 contract."""
    local_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    selection_hash = hashlib.sha256((selection_dir / "manifest.json").read_bytes()).hexdigest()
    manifest = {
        "status_contract": "research-staging-status-v2",
        "selection_root": str(selection_dir.resolve()),
        "global_manifest_sha256": selection_hash,
        "phase": phase,
        "memberships": memberships_count,
        "candidate_count": len(records),
        "unique_candidates": len(records),
        "text_candidates": sum(bool(r.get("text_sha256")) for r in records),
        "paid_ready_candidates": 0,
        "approvals": 0,
        "paid_calls": 0,
        **(extra_manifest or {}),
    }
    required = {r["text_sha256"] for r in records if r.get("text_sha256")}
    missing_blobs = sorted(sha for sha in required if sha not in texts)
    if missing_blobs:
        raise ValueError(
            f"missing {len(missing_blobs)} staged text blobs (e.g. {missing_blobs[0]})"
        )
    referenced_texts = {sha: texts[sha] for sha in required}

    local_engine = None
    from sqlalchemy import create_engine

    try:
        local_engine = create_engine("sqlite:///" + str(local_sqlite_path.resolve()))
        local_res = persist_lyric_staging(local_engine, manifest, records, referenced_texts)
    finally:
        if local_engine is not None:
            local_engine.dispose()

    pg_res = persist_lyric_staging(pg_engine, manifest, records, referenced_texts)
    if local_res["run_id"] != pg_res["run_id"]:
        raise ValueError("local and PostgreSQL run signatures diverged")
    return {
        "run_id": pg_res["run_id"],
        "manifest": manifest,
        "local": local_res,
        "postgres": pg_res,
        "local_sqlite": str(local_sqlite_path.resolve()),
    }
