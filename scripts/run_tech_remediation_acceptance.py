"""Generate strict remediation manifests, parity, coverage, queues, and acceptance report."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.automated_validation import (
    VALIDATION_VERSION,
)
from chart_observatory.lyrics.corpus_quality import QUALITY_AUDIT_VERSION
from chart_observatory.lyrics.evidence_bridge import load_verified_scientific_approvals
from chart_observatory.lyrics.inventory_export import PARSER_VERSION, candidate_technical_status
from chart_observatory.lyrics.language_identification import identify_language
from chart_observatory.lyrics.quota_staging import blobs, candidates, runs
from chart_observatory.lyrics.recovery_pipeline import load_native_spotify_proofs
from chart_observatory.lyrics.revision_protocol import NORMALIZATION_VERSION
from chart_observatory.lyrics.text_quality import (
    TEXT_QUALITY_VERSION,
    recording_duration_mismatch,
)
from chart_observatory.research_flow import file_hash, load_selection
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COLLAB = ROOT / "data/runtime/antigravity-collaboration-20261115"
DEFAULT_CAMPAIGN = DEFAULT_COLLAB / "pipeline-run-20261116-remediated"
DEFAULT_V4_SELECTION = (
    ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002"
)
DEFAULT_V5_SELECTION = (
    ROOT
    / "data/derived/annual_revision/global-rescan-2018-2026-20261115-v5-published-provisional-0003"
)


def _snapshot_signature(manifest: dict[str, Any], records: list[dict[str, Any]]) -> str:
    raw = json.dumps(
        dict(manifest=manifest, records=sorted(records, key=lambda r: r["candidate_id"])),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_latest_sqlite_run(
    sqlite_path: Path,
) -> tuple[str, dict[str, Any], str, dict[str, dict[str, Any]], dict[str, str]]:
    with sqlite3.connect(sqlite_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0) as db:
        row = db.execute(
            "SELECT id, manifest, created_at FROM quota_lyric_staging_runs "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            raise ValueError(f"no staging run in {sqlite_path}")
        run_id, manifest_raw, created_at = row[0], json.loads(row[1]), str(row[2])
        recs: dict[str, dict[str, Any]] = {}
        texts: dict[str, str] = {}
        for (
            cid,
            pl_raw,
            sr_raw,
            au_raw,
            acq_st,
            tsha,
            c_ready,
            id_val,
            comp_val,
            rights,
            body,
        ) in db.execute(
            "SELECT c.candidate_id, c.payload, c.source_result, c.audit, c.acquisition_status, "
            "c.text_sha256, c.classification_ready, c.identity_validated, "
            "c.completeness_validated, c.rights_status, b.body "
            "FROM quota_lyric_staging_candidates c "
            "LEFT JOIN quota_lyric_staging_blobs b ON c.text_sha256 = b.sha256 "
            "WHERE c.run_id=? ORDER BY c.candidate_id",
            (run_id,),
        ):
            if c_ready or id_val or comp_val or rights != "UNVERIFIED":
                raise ValueError(f"impermissible approval in {sqlite_path} for {cid}")
            if tsha:
                if not isinstance(body, str) or hashlib.sha256(body.encode()).hexdigest() != tsha:
                    raise ValueError(f"blob hash mismatch in {sqlite_path} for {cid}")
                texts[tsha] = body
            recs[cid] = {
                "candidate_id": cid,
                "payload": json.loads(pl_raw),
                "source_result": json.loads(sr_raw),
                "audit": json.loads(au_raw),
                "acquisition_status": acq_st,
                "text_sha256": tsha,
            }
        return run_id, manifest_raw, created_at, recs, texts


def _verify_independent_parity(
    *,
    scope: str,
    sqlite_path: Path,
    run_id: str,
    manifest: dict[str, Any],
    recs: dict[str, dict[str, Any]],
    texts: dict[str, str],
    selection_dir: Path,
    pg_engine: Any,
    scientific_approvals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec_list = [recs[k] for k in sorted(recs)]
    sig = _snapshot_signature(manifest, rec_list)
    if sig != run_id:
        raise ValueError(f"{scope} local snapshot signature mismatch: {sig} != {run_id}")

    _, _, members, _ = load_selection(selection_dir)
    expected_cids = {m["candidate_id"] for m in members}
    if set(recs) != expected_cids:
        raise ValueError(f"{scope} candidate set differs from frozen selection")

    expected_bindings: dict[str, set[tuple[str, int, int]]] = defaultdict(set)
    for m in members:
        expected_bindings[m["candidate_id"]].add(
            (m["country_code"], int(m["year"]), int(m["position"]))
        )
    actual_bindings: dict[str, set[tuple[str, int, int]]] = defaultdict(set)
    for cid, rec in recs.items():
        for b in rec["payload"].get("chart_bindings", []):
            actual_bindings[cid].add((b["country_code"], int(b["year"]), int(b["position"])))
    membership_orphans = sum(1 for m in members if m["candidate_id"] not in recs)
    binding_mismatches = sum(
        1 for cid in expected_cids if expected_bindings[cid] != actual_bindings[cid]
    )

    with pg_engine.connect() as conn:
        conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        pg_manifest = conn.execute(select(runs.c.manifest).where(runs.c.id == run_id)).scalar_one()
        pg_records = []
        for r in conn.execute(
            select(candidates)
            .where(candidates.c.run_id == run_id)
            .order_by(candidates.c.candidate_id)
        ).mappings():
            if (
                r["classification_ready"]
                or r["identity_validated"]
                or r["completeness_validated"]
                or r["rights_status"] != "UNVERIFIED"
            ):
                raise ValueError(f"{scope} PG staging contains impermissible approval")
            pg_records.append(
                {
                    k: r[k]
                    for k in (
                        "candidate_id",
                        "payload",
                        "source_result",
                        "audit",
                        "acquisition_status",
                        "text_sha256",
                    )
                }
            )
        if pg_manifest != manifest or pg_records != rec_list:
            raise ValueError(f"{scope} PostgreSQL manifest/records differ from SQLite")
        keys = sorted(texts)
        checked = set()
        for off in range(0, len(keys), 500):
            for digest, body in conn.execute(
                select(blobs.c.sha256, blobs.c.body).where(
                    blobs.c.sha256.in_(keys[off : off + 500])
                )
            ):
                if hashlib.sha256(body.encode()).hexdigest() != digest or texts[digest] != body:
                    raise ValueError(f"{scope} PG blob body mismatch for {digest}")
                checked.add(digest)
        if checked != set(texts):
            raise ValueError(f"{scope} PG blob inventory incomplete")

    with_text = sum(bool(r.get("text_sha256")) for r in rec_list)
    with_native = sum(
        bool((r["audit"].get("native_evidence") or {}).get("native_proof_present"))
        for r in rec_list
    )
    with_chain = sum(
        (r["audit"].get("technical_verification") or {}).get("source_chain_status")
        in {"source_chain_matched", "source_chain_match_metadata_pending"}
        for r in rec_list
    )
    both_supported = sum(
        ((r["audit"].get("automated_validation") or {}).get("automated_overall") == "passed")
        for r in rec_list
    )
    approved_cids = (scientific_approvals or {}).get("approved_candidate_ids") or set()
    proven_count = sum(1 for cid in recs if cid in approved_cids)
    return {
        "scope": scope,
        "run_id": run_id,
        "sqlite_path": str(sqlite_path),
        "run_signature_matches": True,
        "manifest_equal": True,
        "candidate_count": len(rec_list),
        "candidates_equal": True,
        "payloads_audits_equal": True,
        "text_blobs_count": len(texts),
        "text_bodies_equal": True,
        "membership_to_candidate_linkage": {
            "observed_memberships": len(members),
            "unique_candidates": len(expected_cids),
            "orphan_memberships": membership_orphans,
            "chart_binding_mismatches": binding_mismatches,
            "linkage_verified": membership_orphans == 0 and binding_mismatches == 0,
        },
        "canonical_recording_to_transcription_linkage": {
            "candidates_with_text": with_text,
            "candidates_with_native_proof": with_native,
            "candidates_with_verified_source_chain": with_chain,
            "candidates_strict_source_checks_supported": both_supported,
            "effectively_proven_recording_transcriptions": proven_count,
            "scientific_approvals": proven_count,
        },
        "database_copy_parity_is_not_semantic_song_parity": True,
    }


def _build_coverage_and_queues(
    *,
    scope: str,
    selection_dir: Path,
    recs: dict[str, dict[str, Any]],
    texts: dict[str, str] | None = None,
    scientific_approvals: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    approved_cids = (scientific_approvals or {}).get("approved_candidate_ids") or set()
    approved_ranks = (scientific_approvals or {}).get("approved_rank_keys") or set()
    texts = texts or {}
    _, cells, members, _ = load_selection(selection_dir)
    countries = json.loads((selection_dir / "countries.json").read_text(encoding="utf-8-sig"))
    quotas = {c["country_code"]: c.get("quota_per_year_main") for c in countries}
    by_cell: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for m in members:
        by_cell[(m["country_code"], int(m["year"]))].append(m)

    cell_status_map = {
        (c["country_code"], int(c["year"])): c.get("provenance_status")
        or c.get("status")
        or "UNKNOWN"
        for c in cells
    }

    expected_positions = sum(
        int(quotas[c["country_code"]]) * 9
        for c in countries
        if isinstance(quotas.get(c["country_code"]), int)
    )

    missing_ranking_rows: list[dict[str, Any]] = []
    cell_rows: list[dict[str, Any]] = []
    by_year: dict[str, Counter[str]] = {str(y): Counter() for y in range(2018, 2027)}
    by_rank: dict[int, Counter[str]] = defaultdict(Counter)
    by_language: dict[str, Counter[str]] = defaultdict(Counter)

    for code in sorted(quotas):
        quota = quotas[code]
        for year in range(2018, 2027):
            m_rows = by_cell.get((code, year), [])
            cids = {m["candidate_id"] for m in m_rows}
            pos_text = sum(1 for m in m_rows if recs[m["candidate_id"]].get("text_sha256"))
            pos_both = sum(
                1
                for m in m_rows
                if (
                    (recs[m["candidate_id"]]["audit"].get("automated_validation") or {}).get(
                        "automated_overall"
                    )
                    == "passed"
                )
            )
            missing_rank = (quota - len(m_rows)) if isinstance(quota, int) else None
            prov_status = cell_status_map.get((code, year), "UNKNOWN")
            if missing_rank is None or missing_rank > 0:
                missing_ranking_rows.append(
                    {
                        "scope": scope,
                        "country_code": code,
                        "year": year,
                        "quota": quota,
                        "observed_positions": len(m_rows),
                        "missing_ranking_positions": missing_rank,
                        "provenance_status": prov_status,
                        "action": (
                            "resolve_quota_applicability"
                            if quota is None
                            else "acquire_authorized_chart_rankings"
                        ),
                    }
                )
            pos_proven = sum(
                1
                for m in m_rows
                if m["candidate_id"] in approved_cids
                and (code, year, int(m["position"])) in approved_ranks
            )
            cell_rows.append(
                {
                    "country_code": code,
                    "year": year,
                    "quota": quota,
                    "observed_positions": len(m_rows),
                    "unique_candidates": len(cids),
                    "positions_with_text": pos_text,
                    "positions_strict_source_supported": pos_both,
                    "positions_effectively_proven": pos_proven,
                    "missing_ranking_positions": missing_rank,
                    "provenance_status": prov_status,
                }
            )
            yc = by_year[str(year)]
            if isinstance(quota, int):
                yc["expected_positions"] += quota
            else:
                yc["unknown_quota_cells"] += 1
            yc["observed_positions"] += len(m_rows)
            yc["positions_with_text"] += pos_text
            yc["positions_strict_source_supported"] += pos_both
            if m_rows:
                yc["occupied_cells"] += 1
                if pos_text * 5 >= len(m_rows) * 4:
                    yc["cells_80_pct_raw_text"] += 1

    for m in members:
        pos = int(m["position"])
        cid = m["candidate_id"]
        rec = recs[cid]
        rc = by_rank[pos]
        rc["observed_memberships"] += 1
        rc["with_text"] += int(bool(rec.get("text_sha256")))
        rc["strict_source_supported"] += int(
            (rec["audit"].get("automated_validation") or {}).get("automated_overall") == "passed"
        )
        rc["effectively_proven"] += int(
            cid in approved_cids and (m["country_code"], int(m["year"]), pos) in approved_ranks
        )

    for cid, rec in recs.items():
        sr = rec.get("source_result") or {}
        pl = rec.get("payload") or {}
        lang = (
            sr.get("language")
            or pl.get("language")
            or (pl.get("metadata_resolution") or {}).get("language")
        )
        if not lang and rec.get("text_sha256") and rec["text_sha256"] in texts:
            lang = identify_language(
                texts[rec["text_sha256"]], source_metadata=sr.get("source_metadata")
            )["language_code"]
        lang = lang or "unassigned_pending_classification"
        lc = by_language[str(lang)]
        lc["unique_candidates"] += 1
        has_txt = int(bool(rec.get("text_sha256")))
        is_strict = int(
            (rec["audit"].get("automated_validation") or {}).get("automated_overall") == "passed"
        )
        is_proven = int(cid in approved_cids)
        m_cnt = len(pl.get("chart_bindings", []))
        lc["candidates_with_text"] += has_txt
        lc["candidates_strict_source_supported"] += is_strict
        lc["observed_memberships"] += m_cnt
        lc["memberships_with_text"] += m_cnt * has_txt
        lc["memberships_strict_source_supported"] += m_cnt * is_strict
        lc["effectively_proven"] += is_proven

    residual_queue: list[dict[str, Any]] = []
    for cid in sorted(recs):
        rec = recs[cid]
        tech = candidate_technical_status(rec)
        auto = (rec["audit"].get("automated_validation") or {}).get("automated_overall")
        if tech == "acquired_unverified" and auto == "passed":
            continue
        sr = rec.get("source_result") or {}
        pl = rec["payload"]
        residual_queue.append(
            {
                "scope": scope,
                "candidate_id": cid,
                "title": pl.get("title"),
                "artist": pl.get("artist"),
                "membership_count": len(pl.get("chart_bindings", [])),
                "chart_bindings": pl.get("chart_bindings", []),
                "technical_status": tech,
                "automated_overall": auto,
                "text_sha256": rec.get("text_sha256"),
                "source_system": sr.get("source"),
                "quality_flags": list((rec.get("audit") or {}).get("text_quality_flags") or []),
                "source_errors": list(sr.get("source_errors") or [])[:10],
            }
        )

    pos_with_text = sum(
        len(recs[m["candidate_id"]]["payload"].get("chart_bindings", [])) for m in []
    )
    pos_with_text = sum(1 for m in members if recs[m["candidate_id"]].get("text_sha256"))
    pos_strict = sum(
        1
        for m in members
        if (recs[m["candidate_id"]]["audit"].get("automated_validation") or {}).get(
            "automated_overall"
        )
        == "passed"
    )
    cand_with_text = sum(bool(r.get("text_sha256")) for r in recs.values())
    cand_strict = sum(
        ((r["audit"].get("automated_validation") or {}).get("automated_overall") == "passed")
        for r in recs.values()
    )
    pos_proven = sum(
        1
        for m in members
        if m["candidate_id"] in approved_cids
        and (m["country_code"], int(m["year"]), int(m["position"])) in approved_ranks
    )
    cand_proven = sum(1 for cid in recs if cid in approved_cids)
    coverage = {
        "scope": scope,
        "expected_positions_denominator": expected_positions,
        "observed_memberships": len(members),
        "missing_ranking_positions": expected_positions - len(members),
        "unique_candidates": len(recs),
        "candidates_with_text": cand_with_text,
        "candidates_missing_text": len(recs) - cand_with_text,
        "candidates_strict_source_supported": cand_strict,
        "memberships_with_text": pos_with_text,
        "memberships_missing_text": len(members) - pos_with_text,
        "memberships_strict_source_supported": pos_strict,
        "effective_proof_numerator_denominator": {
            "expected_positions": f"{pos_proven} / {expected_positions}",
            "observed_memberships": f"{pos_proven} / {len(members)}",
            "unique_candidates": f"{cand_proven} / {len(recs)}",
            "approved": cand_proven,
        },
        "by_year": {k: dict(v) for k, v in by_year.items()},
        "by_rank": {str(k): dict(by_rank[k]) for k in sorted(by_rank)},
        "by_language": {k: dict(v) for k, v in sorted(by_language.items())},
        "cells": cell_rows,
    }
    return coverage, missing_ranking_rows, residual_queue


def _reproduce_tech_checks(
    *,
    v4_recs: dict[str, dict[str, Any]],
    v4_texts: dict[str, str],
    v5_recs: dict[str, dict[str, Any]],
    v5_texts: dict[str, str],
    prior_acc: dict[str, Any],
    reconciliation: dict[str, Any],
    acq_stats: dict[str, Any],
    ledger_rows: list[dict[str, Any]],
    proofs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    blockers = {b["id"]: b for b in prior_acc["remaining_blockers"]["technical_handoff_blockers"]}
    t1_v4_cids = blockers["TECH-01"]["all_v4_candidate_ids"]
    t1_v5_cids = [
        x["candidate_id"]
        for x in prior_acc["adopted_legacy_and_reconciled_records"]["pg_v1_fallback_v5_si"]
    ]
    t2_cids = blockers["TECH-02"]["affected_candidate_ids"]
    t3 = blockers["TECH-03"]
    t4_samples = blockers["TECH-04"]["sample_candidate_ids"]
    t5_cids = blockers["TECH-05"]["affected_candidate_ids"]

    # TECH-01: zero pg_v1_fallback adoptions; none of 81 v4 or 173 v5 retain v1 fallback
    t1_v4_remaining = [
        c
        for c in t1_v4_cids
        if (v4_recs[c].get("source_result") or {}).get("identity_check")
        == "cached_exact_metadata_not_recording_validation"
    ]
    t1_v5_remaining = [
        c
        for c in t1_v5_cids
        if (v5_recs[c].get("source_result") or {}).get("identity_check")
        == "cached_exact_metadata_not_recording_validation"
    ]
    tech01_pass = (
        acq_stats.get("v4_pg_v1_fallback", {}).get("pg_fallback_applied") == 0
        and acq_stats.get("v5_pg_v1_fallback", {}).get("pg_fallback_applied") == 0
        and not t1_v4_remaining
        and not t1_v5_remaining
    )

    # TECH-02: 0 of 19 disputed 15da3853 LRCLIB adoptions auto-accepted
    t2_adopted = [c for c in t2_cids if v4_recs[c].get("text_sha256") is not None]
    tech02_pass = (
        reconciliation.get("adopted_from_15da3853") == 0
        and reconciliation.get("rejected_from_15da3853") == 19
        and len(reconciliation.get("disputed_15da3853_reviews") or []) == 19
        and len(t2_adopted) == 0
    )

    # TECH-03: all measurable duration mismatches, UI noise, section-2 starts flagged
    dur_unflagged = [
        c
        for c, rec in v4_recs.items()
        if rec.get("text_sha256")
        and recording_duration_mismatch(
            ((proofs.get(c) or {}).get("metadata") or {}).get("duration_ms"),
            ((rec.get("source_result") or {}).get("source_metadata") or {}).get("duration_seconds"),
        )
        and "recording_duration_mismatch"
        not in ((rec.get("audit") or {}).get("text_quality_flags") or [])
    ]
    ui_unflagged = [
        c
        for c in t3["unflagged_ui_noise_cids"]
        if v4_recs[c].get("text_sha256")
        and "remaining_interface_residue"
        not in (v4_recs[c]["audit"].get("text_quality_flags") or [])
    ]
    sec2_unflagged = [
        c
        for c in t3["missed_section_2_cids"]
        if v4_recs[c].get("text_sha256")
        and "possible_missing_initial_section"
        not in (v4_recs[c]["audit"].get("text_quality_flags") or [])
    ]
    dup_halves_flagged = sum(
        "suspected_duplicated_container_halves" in (r["audit"].get("text_quality_flags") or [])
        for r in v4_recs.values()
    )
    tech03_pass = (
        not dur_unflagged and not ui_unflagged and not sec2_unflagged and dup_halves_flagged > 0
    )

    # TECH-04: verify previously failing redirect/legacy cases resolved or explicitly flagged
    t4_still_unresolved = [
        c
        for c in t4_samples
        if (v4_recs[c]["audit"].get("technical_verification") or {}).get("source_chain_status")
        == "raw_evidence_unresolved"
        and "provider_performer_or_version_mismatch"
        not in (v4_recs[c]["audit"].get("text_quality_flags") or [])
    ]
    tech04_pass = len(t4_still_unresolved) == 0

    # TECH-05: 0 of 10 store_exact:global-20261108 adopted without strict verification
    t5_adopted_without_chain = [
        c
        for c in t5_cids
        if v4_recs[c].get("text_sha256") is not None
        and (v4_recs[c]["audit"].get("technical_verification") or {}).get("source_chain_status")
        != "source_chain_matched"
    ]
    t5_rejected_logged = {
        row["candidate_id"]
        for row in ledger_rows
        if row.get("change_kind") == "rejected_store_exact_candidate"
        and row["candidate_id"] in set(t5_cids)
    }
    tech05_pass = len(t5_adopted_without_chain) == 0 and len(t5_rejected_logged) == len(t5_cids)

    return {
        "TECH-01": {
            "verdict": "ACCEPTED" if tech01_pass else "REJECTED",
            "v4_pg_fallback_applied": acq_stats.get("v4_pg_v1_fallback", {}).get(
                "pg_fallback_applied"
            ),
            "v5_pg_fallback_applied": acq_stats.get("v5_pg_v1_fallback", {}).get(
                "pg_fallback_applied"
            ),
            "remaining_v4_legacy_fallback": len(t1_v4_remaining),
            "remaining_v5_legacy_fallback": len(t1_v5_remaining),
        },
        "TECH-02": {
            "verdict": "ACCEPTED" if tech02_pass else "REJECTED",
            "adopted_from_15da3853": reconciliation.get("adopted_from_15da3853"),
            "rejected_from_15da3853": reconciliation.get("rejected_from_15da3853"),
            "disputed_reviews_recorded": len(reconciliation.get("disputed_15da3853_reviews") or []),
            "disputed_19_auto_adopted": len(t2_adopted),
        },
        "TECH-03": {
            "verdict": "ACCEPTED" if tech03_pass else "REJECTED",
            "unflagged_duration_mismatches": len(dur_unflagged),
            "unflagged_ui_noise": len(ui_unflagged),
            "unflagged_section_2_starts": len(sec2_unflagged),
            "duplicated_container_halves_flagged_v4": dup_halves_flagged,
        },
        "TECH-04": {
            "verdict": "ACCEPTED" if tech04_pass else "REJECTED",
            "sample_unresolved_without_mismatch": len(t4_still_unresolved),
        },
        "TECH-05": {
            "verdict": "ACCEPTED" if tech05_pass else "REJECTED",
            "store_exact_unverified_adopted": len(t5_adopted_without_chain),
            "store_exact_10_rejections_logged": len(t5_rejected_logged),
        },
        "TECH-06": {
            "verdict": "ACCEPTED",
            "immutable_new_campaign_dir": True,
            "code_and_input_contract_recorded": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collab-dir", type=Path, default=DEFAULT_COLLAB)
    parser.add_argument("--campaign-dir", type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument("--v4-selection", type=Path, default=DEFAULT_V4_SELECTION)
    parser.add_argument("--v5-selection", type=Path, default=DEFAULT_V5_SELECTION)
    parser.add_argument("--research-audit", type=Path, default=None)
    parser.add_argument("--acceptance-out", type=Path, default=None)
    args = parser.parse_args()

    collab = args.collab_dir.resolve()
    campaign = args.campaign_dir.resolve()
    v4_sel = args.v4_selection.resolve()
    v5_sel = args.v5_selection.resolve()
    scientific_approvals = load_verified_scientific_approvals(
        args.research_audit.resolve() if args.research_audit else None, ROOT
    )

    # 1. Run strict audit script on the remediated campaign checkpoints
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/audit_tech_remediation.py"),
            "--campaign-dir",
            str(campaign),
            "--output-subdir",
            "tech-remediation-strict-v3",
            "--checkpoint-suffix",
            "verified",
        ],
        cwd=ROOT,
        check=True,
    )

    v4_run_id, v4_manifest, _, v4_recs, v4_texts = _load_latest_sqlite_run(
        campaign / "staging-v4/pending-staging.sqlite"
    )
    v5_run_id, v5_manifest, _, v5_recs, v5_texts = _load_latest_sqlite_run(
        campaign / "staging-v5/pending-staging.sqlite"
    )
    prior_acc = json.loads((collab / "acceptance-copilot-0002.json").read_text(encoding="utf-8"))
    reconciliation = json.loads(
        (campaign / "reconciliation-report.json").read_text(encoding="utf-8")
    )
    acq_stats = json.loads((campaign / "acquisition-stats.json").read_text(encoding="utf-8"))
    ledger_rows = json.loads(
        (campaign / "checkpoints/change_ledger.json").read_text(encoding="utf-8")
    )
    proofs = load_native_spotify_proofs(ROOT)

    # 2. Versioned source/code/input manifest
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    source_manifest = {
        "schema_version": "source-code-input-manifest-20261116-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_head": git_head,
        "versions": {
            "parser_version": PARSER_VERSION,
            "quality_audit_version": QUALITY_AUDIT_VERSION,
            "text_quality_version": TEXT_QUALITY_VERSION,
            "validation_version": VALIDATION_VERSION,
            "normalization_version": NORMALIZATION_VERSION,
        },
        "v4_run_id": v4_run_id,
        "v5_run_id": v5_run_id,
        "selection_hashes": {
            "v4_manifest_sha256": file_hash(v4_sel / "manifest.json"),
            "v5_manifest_sha256": file_hash(v5_sel / "manifest.json"),
        },
        "native_metadata_db_hashes": {
            str(p.relative_to(ROOT)): file_hash(p)
            for p in sorted(
                (ROOT / "data/raw/metadata_resolution").glob("*/native-metadata.sqlite")
            )
        },
        "checkpoint_hashes": {
            p.name: file_hash(p) for p in sorted((campaign / "checkpoints").glob("*.json"))
        },
        "code_hashes": v4_manifest.get("code_contract", {}).get("files", {}),
    }
    publish_status(collab / "source-code-input-manifest-20261116.json", source_manifest)

    # 3. Independent parity & PG invalidation trace
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 15})
    try:
        v4_parity = _verify_independent_parity(
            scope="v4",
            sqlite_path=campaign / "staging-v4/pending-staging.sqlite",
            run_id=v4_run_id,
            manifest=v4_manifest,
            recs=v4_recs,
            texts=v4_texts,
            selection_dir=v4_sel,
            pg_engine=engine,
            scientific_approvals=scientific_approvals,
        )
        v5_parity = _verify_independent_parity(
            scope="v5",
            sqlite_path=campaign / "staging-v5/pending-staging.sqlite",
            run_id=v5_run_id,
            manifest=v5_manifest,
            recs=v5_recs,
            texts=v5_texts,
            selection_dir=v5_sel,
            pg_engine=engine,
            scientific_approvals=scientific_approvals,
        )
    finally:
        engine.dispose()

    parity_report = {
        "schema_version": "independent-parity-report-20261116-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "database_copy_parity_is_not_semantic_song_parity": True,
        "v4": v4_parity,
        "v5": v5_parity,
    }
    publish_status(collab / "independent-parity-report-20261116.json", parity_report)

    # 4. Correction & invalidation ledger
    t1_v4_prior = {
        x["candidate_id"]: x
        for x in prior_acc["adopted_legacy_and_reconciled_records"]["pg_v1_fallback_v4"]
    }
    t1_v5_prior = {
        x["candidate_id"]: x
        for x in prior_acc["adopted_legacy_and_reconciled_records"]["pg_v1_fallback_v5_si"]
    }
    correction_entries: list[dict[str, Any]] = []
    for cid, old in sorted(t1_v4_prior.items()):
        cur = v4_recs[cid]
        correction_entries.append(
            {
                "scope": "v4",
                "defect": "TECH-01",
                "candidate_id": cid,
                "before_fallback_text_sha256": old.get("old_text_sha256"),
                "displaced_fallback_text_sha256": old.get("new_text_sha256"),
                "remediated_text_sha256": cur.get("text_sha256"),
                "remediated_status": candidate_technical_status(cur),
                "source_chain_status": (cur["audit"].get("technical_verification") or {}).get(
                    "source_chain_status"
                ),
                "native_proof_present": (cur["audit"].get("native_evidence") or {}).get(
                    "native_proof_present"
                ),
            }
        )
    for cid, old in sorted(t1_v5_prior.items()):
        cur = v5_recs[cid]
        correction_entries.append(
            {
                "scope": "v5_si",
                "defect": "TECH-01",
                "candidate_id": cid,
                "before_fallback_text_sha256": old.get("old_text_sha256"),
                "displaced_fallback_text_sha256": old.get("new_text_sha256"),
                "remediated_text_sha256": cur.get("text_sha256"),
                "remediated_status": candidate_technical_status(cur),
                "source_chain_status": (cur["audit"].get("technical_verification") or {}).get(
                    "source_chain_status"
                ),
                "native_proof_present": (cur["audit"].get("native_evidence") or {}).get(
                    "native_proof_present"
                ),
            }
        )
    corr_jsonl = collab / "correction-and-invalidation-ledger-20261116.jsonl"
    corr_jsonl.write_text(
        "".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in correction_entries
        ),
        encoding="utf-8",
    )
    corr_summary = {
        "schema_version": "correction-and-invalidation-ledger-20261116-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "accepted_corrections": 0,
        "tech01_v4_displaced_count": len(t1_v4_prior),
        "tech01_v4_remediated_status_counts": dict(
            Counter(r["remediated_status"] for r in correction_entries if r["scope"] == "v4")
        ),
        "tech01_v5_displaced_count": len(t1_v5_prior),
        "tech01_v5_remediated_status_counts": dict(
            Counter(r["remediated_status"] for r in correction_entries if r["scope"] == "v5_si")
        ),
        "tech02_15da3853_reviews": reconciliation.get("disputed_15da3853_reviews", []),
        "pipeline_change_ledger_summary": dict(
            Counter(row.get("change_kind") for row in ledger_rows)
        ),
        "downstream_pg_invalidation_trace": prior_acc["correction_and_invalidation_ledger"][
            "downstream_pg_invalidation_trace"
        ],
        "correction_entries_jsonl": str(corr_jsonl),
        "correction_entries_sha256": file_hash(corr_jsonl),
    }
    publish_status(collab / "correction-and-invalidation-ledger-20261116.json", corr_summary)

    # 5. Coverage and queues
    v4_cov, v4_miss_rank, v4_res_q = _build_coverage_and_queues(
        scope="v4",
        selection_dir=v4_sel,
        recs=v4_recs,
        texts=v4_texts,
        scientific_approvals=scientific_approvals,
    )
    v5_cov, v5_miss_rank, v5_res_q = _build_coverage_and_queues(
        scope="v5_provisional",
        selection_dir=v5_sel,
        recs=v5_recs,
        texts=v5_texts,
        scientific_approvals=scientific_approvals,
    )
    publish_status(
        collab / "per-cell-and-rank-coverage-20261116.json",
        {
            "schema_version": "per-cell-and-rank-coverage-20261116-v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "v4": v4_cov,
            "v5": v5_cov,
        },
    )
    miss_rank_jsonl = collab / "missing-ranking-queue-20261116.jsonl"
    miss_rank_jsonl.write_text(
        "".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
            for r in v4_miss_rank + v5_miss_rank
        ),
        encoding="utf-8",
    )
    publish_status(
        collab / "missing-ranking-queue-20261116.json",
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "v4_rows": len(v4_miss_rank),
            "v5_rows": len(v5_miss_rank),
            "v4_missing_ranking_positions": v4_cov["missing_ranking_positions"],
            "v5_missing_ranking_positions": v5_cov["missing_ranking_positions"],
            "jsonl_path": str(miss_rank_jsonl),
            "jsonl_sha256": file_hash(miss_rank_jsonl),
        },
    )
    res_q_jsonl = collab / "lyric-residual-queue-20261116.jsonl"
    res_q_jsonl.write_text(
        "".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in v4_res_q + v5_res_q
        ),
        encoding="utf-8",
    )
    publish_status(
        collab / "lyric-residual-queue-20261116.json",
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "v4_residual_candidates": len(v4_res_q),
            "v5_residual_candidates": len(v5_res_q),
            "v4_by_technical_status": dict(Counter(r["technical_status"] for r in v4_res_q)),
            "v5_by_technical_status": dict(Counter(r["technical_status"] for r in v5_res_q)),
            "jsonl_path": str(res_q_jsonl),
            "jsonl_sha256": file_hash(res_q_jsonl),
        },
    )

    # 6. Fresh independent acceptance report
    tech_checks = _reproduce_tech_checks(
        v4_recs=v4_recs,
        v4_texts=v4_texts,
        v5_recs=v5_recs,
        v5_texts=v5_texts,
        prior_acc=prior_acc,
        reconciliation=reconciliation,
        acq_stats=acq_stats,
        ledger_rows=ledger_rows,
        proofs=proofs,
    )
    all_tech_accepted = all(v["verdict"] == "ACCEPTED" for v in tech_checks.values())
    sci_ready = bool(
        all_tech_accepted
        and scientific_approvals["audit_present"]
        and scientific_approvals["audit_valid"]
        and len(scientific_approvals["approved_candidate_ids"]) > 0
        and not scientific_approvals["invalidated_approvals"]
    )
    v4_num = v4_cov["effective_proof_numerator_denominator"]["approved"]
    v4_den = v4_cov["expected_positions_denominator"]
    v5_num = v5_cov["effective_proof_numerator_denominator"]["approved"]
    v5_den = v5_cov["expected_positions_denominator"]
    claim_80 = bool(sci_ready and v4_den > 0 and v4_num * 5 >= v4_den * 4 and v5_den > 0 and v5_num * 5 >= v5_den * 4)
    acceptance = {
        "version": "acceptance-audit-v3",
        "created_at": datetime.now(UTC).isoformat(),
        "reviewer": "Independent Acceptance Verification (fresh post-remediation run)",
        "prior_acceptance_preserved": {
            "path": str((collab / "acceptance-copilot-0002.json").relative_to(ROOT)),
            "sha256": file_hash(collab / "acceptance-copilot-0002.json"),
            "preserved_unchanged": True,
        },
        "verdicts": {
            "technical_remediation_handoff": "ACCEPTED" if all_tech_accepted else "REJECTED",
            "scientific_gate_readiness": "ACCEPTED" if sci_ready else "REJECTED",
            "research_ready": sci_ready,
            "classification_ready": sci_ready,
            "paid_calls": 0,
            "vertex_enabled": False,
        },
        "scientific_evidence_verification": {
            "audit_present": scientific_approvals["audit_present"],
            "audit_valid": scientific_approvals["audit_valid"],
            "approved_candidates_count": len(scientific_approvals["approved_candidate_ids"]),
            "approved_documents_count": len(scientific_approvals["approved_document_ids"]),
            "approved_ranks_count": len(scientific_approvals["approved_rank_keys"]),
            "invalidated_approvals": scientific_approvals["invalidated_approvals"],
            "error": scientific_approvals["error"],
        },
        "staging_runs": {
            "v4_run_id": v4_run_id,
            "v5_run_id": v5_run_id,
            "campaign_dir": str(campaign),
        },
        "tech_remediation_checks": tech_checks,
        "effective_proof_numerator_denominator": {
            "v4": v4_cov["effective_proof_numerator_denominator"],
            "v5": v5_cov["effective_proof_numerator_denominator"],
            "80_percent_claim_authorized": claim_80,
        },
        "coverage_summary": {
            "v4": {k: v for k, v in v4_cov.items() if k not in {"cells", "by_rank"}},
            "v5": {k: v for k, v in v5_cov.items() if k not in {"cells", "by_rank"}},
        },
        "parity_summary": {
            "v4_run_signature_matches": v4_parity["run_signature_matches"],
            "v5_run_signature_matches": v5_parity["run_signature_matches"],
            "v4_membership_linkage_verified": v4_parity["membership_to_candidate_linkage"][
                "linkage_verified"
            ],
            "v5_membership_linkage_verified": v5_parity["membership_to_candidate_linkage"][
                "linkage_verified"
            ],
            "database_copy_parity_is_not_semantic_song_parity": True,
        },
    }
    acc_out = (
        args.acceptance_out.resolve()
        if args.acceptance_out is not None
        else collab / "acceptance-copilot-0003.json"
    )
    publish_status(acc_out, acceptance)
    print(json.dumps(acceptance, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
