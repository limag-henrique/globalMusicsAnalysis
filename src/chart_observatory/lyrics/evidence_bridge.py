"""Executable bridge between staging/catalog, review packets, canonical research evidence, and Vertex prep.

Never fabricates human reviews, reviewer identities, competence attestations, or
scientific approvals. Missing evidence remains pending; altered evidence invalidates
approval.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from chart_observatory import research_flow as flow
from chart_observatory.lyrics.classification_gate import ClassificationGate
from chart_observatory.lyrics.language_identification import identify_language


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def classify_review_pathway(assessment: dict[str, Any], payload: dict[str, Any], result: dict[str, Any]) -> str:
    """Separate candidates into automated, official-edition-bound, or human-review pathways."""
    ident_status = (assessment.get("identity") or {}).get("status")
    comp_status = (assessment.get("completeness") or {}).get("status")
    native_align = assessment.get("native_recording_alignment") or {}
    divergences = [
        k
        for k in (
            "native_title_disagreement",
            "native_artist_disagreement",
            "recording_duration_mismatch",
            "shared_provider_id_across_editions",
        )
        if native_align.get(k)
    ]
    ident_flags = (assessment.get("identity") or {}).get("blocking_quality_flags") or []
    comp_flags = (assessment.get("completeness") or {}).get("blocking_quality_flags") or []
    if ident_status != "passed" or comp_status != "passed" or divergences or ident_flags or comp_flags:
        return "dependent_on_real_human_review"
    if native_align.get("native_proof_present"):
        return "dependent_on_official_edition_transcription"
    return "dependent_on_real_human_review"


def build_minimal_review_packet(
    *,
    song_id: str,
    payload: dict[str, Any],
    result: dict[str, Any],
    text: str | None,
    assessment: dict[str, Any],
) -> dict[str, Any]:
    """Build a minimal review packet without fabricating reviewer identities or approvals."""
    source_meta = result.get("source_metadata") or {}
    lang_info = assessment.get("language_identification") or (
        identify_language(text, source_metadata=source_meta) if text else {
            "language_code": "und",
            "confidence": 0.0,
            "method": "none",
            "reason": "no_local_text",
        }
    )
    pathway = classify_review_pathway(assessment, payload, result)
    ident_flags = (assessment.get("identity") or {}).get("blocking_quality_flags") or []
    comp_flags = (assessment.get("completeness") or {}).get("blocking_quality_flags") or []
    native_align = assessment.get("native_recording_alignment") or {}
    divergences = {
        "identity_blocking_flags": ident_flags,
        "completeness_blocking_flags": comp_flags,
        "provider_identity_reasons": (assessment.get("identity") or {}).get("provider_identity_reasons") or [],
        "native_alignment": native_align,
    }
    text_hash = result.get("text_sha256") or (_sha256_text(text) if text is not None else None)
    return {
        "schema_version": "minimal-review-packet-v1",
        "candidate_id": song_id,
        "pathway": pathway,
        "automatically_verifiable": {
            "source_text_integrity": (assessment.get("source_text_integrity") or {}).get("status"),
            "provider_identity": (assessment.get("identity") or {}).get("status"),
            "provider_completeness": (assessment.get("completeness") or {}).get("status"),
            "language_identification": lang_info,
        },
        "recording": {
            "title": payload.get("title"),
            "artist": payload.get("artist"),
            "platform": payload.get("platform"),
            "spotify_track_id": payload.get("spotify_track_id")
            or (payload.get("metadata_resolution") or {}).get("spotify_track_id"),
            "duration_ms": payload.get("duration_ms")
            or (payload.get("metadata_resolution") or {}).get("duration_ms"),
            "metadata_resolution": payload.get("metadata_resolution"),
        },
        "source": {
            "provider": result.get("source"),
            "source_url": source_meta.get("url"),
            "source_id": source_meta.get("id") or (source_meta.get("provider_credit_evidence") or {}).get("song_id"),
            "raw_response_sha256": (assessment.get("source_text_integrity") or {}).get("raw_response_sha256"),
        },
        "edition": {
            "chart_bindings": payload.get("chart_bindings", []),
            "recording_version_binding": (assessment.get("identity") or {}).get("recording_version_binding"),
        },
        "hashes": {
            "text_sha256": text_hash,
            "replayed_text_sha256": (assessment.get("source_text_integrity") or {}).get("replayed_text_sha256"),
        },
        "text_preview": (text[:300] if text else None),
        "divergences": divergences,
        "exact_form": {
            "required_schema": "TextReview + ClassificationAdjudication + RightsEvidence",
            "allowed_methods": ["official_transcription", "human_audio_verification"],
            "template": {
                "document_id": None,
                "candidate_id": song_id,
                "text_sha256": text_hash,
                "language_code": lang_info.get("language_code"),
                "method": None,
                "actor": None,
                "at": None,
                "evidence": {"path": None, "sha256": None},
                "competence_evidence": {"path": None, "sha256": None},
                "identity_verified": None,
                "integrity_verified": None,
                "completeness_verified": None,
                "truncation_checked": None,
                "contamination_checked": None,
            },
        },
    }


def export_review_packets_from_catalog(
    catalog_db: Path,
    out_dir: Path,
    project: Path,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Generate minimal review packets from catalog.sqlite without mutating catalog."""
    from chart_observatory.final_pipeline import read_result, validate_text

    out_dir.mkdir(parents=True, exist_ok=True)
    packets_path = out_dir / "review-packets.jsonl"
    summary_path = out_dir / "review-packets-summary.json"
    counts = Counter()
    lang_counts = Counter()
    with closing(sqlite3.connect(catalog_db.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT id, payload, result FROM songs ORDER BY id").fetchall()
    if limit is not None:
        rows = rows[:limit]
    tmp_path = packets_path.with_suffix(".jsonl.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload = json.loads(row["payload"])
            result = json.loads(row["result"]) if row["result"] else {}
            try:
                resolved_result, text, _ = read_result(result, project)
            except ValueError:
                resolved_result, text = result, None
            assessment = validate_text(payload, result, project)
            packet = build_minimal_review_packet(
                song_id=row["id"],
                payload=payload,
                result=resolved_result,
                text=text,
                assessment=assessment,
            )
            counts[packet["pathway"]] += 1
            lang = packet["automatically_verifiable"]["language_identification"]["language_code"]
            lang_counts[lang] += 1
            handle.write(json.dumps(packet, ensure_ascii=False, sort_keys=True) + "\n")
    tmp_path.replace(packets_path)
    summary = {
        "schema_version": "review-packets-summary-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "total_packets": sum(counts.values()),
        "pathway_counts": dict(counts),
        "language_counts": dict(lang_counts),
        "packets_path": str(packets_path),
        "packets_sha256": hashlib.sha256(packets_path.read_bytes()).hexdigest(),
        "scientific_approvals_fabricated": 0,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def load_verified_scientific_approvals(
    research_audit_dir: Path | None,
    project: Path,
) -> dict[str, Any]:
    """Read and cryptographically verify real accepted scientific evidences.

    Returns zero approvals if research_audit_dir is None or missing; raises or
    marks invalid if any referenced evidence has been altered.
    """
    empty = {
        "audit_present": False,
        "audit_valid": False,
        "approved_candidate_ids": set(),
        "approved_document_ids": set(),
        "approved_rank_keys": set(),
        "invalidated_approvals": [],
        "error": None,
    }
    if research_audit_dir is None or not research_audit_dir.exists():
        return empty
    try:
        verified = flow.verify_audit(research_audit_dir, check_inputs=True)
        evidence_path = research_audit_dir / "evidence.json"
        if not evidence_path.is_file():
            # Fallback to checking G3 stage report if evidence.json isn't directly in audit_dir
            g3 = flow.require_research_stage(research_audit_dir, "G3", project=project)
            approved_docs = set(g3.get("canonical_state", {}).keys())
            return {
                "audit_present": True,
                "audit_valid": True,
                "approved_candidate_ids": set(),
                "approved_document_ids": approved_docs,
                "approved_rank_keys": set(),
                "invalidated_approvals": [],
                "error": None,
            }
        evidence = flow.ResearchEvidence.model_validate_json(evidence_path.read_text(encoding="utf-8-sig"))
        reader = flow.EvidenceReader(project)
        gate = ClassificationGate.load()
        doc_ids = [UUID(str(item.document_id)) for item in evidence.lyrics]
        documents = flow.read_canonical_documents(project, doc_ids) if doc_ids else {}
        approved_cids: set[str] = set()
        approved_dids: set[str] = set()
        invalidated: list[dict[str, str]] = []
        for approval in evidence.lyrics:
            try:
                ok, reason, doc = flow._lyric_valid(approval, documents, reader, gate)
            except Exception as exc:
                ok, reason, doc = False, str(exc), None
            if ok and doc is not None:
                approved_cids.add(approval.candidate_id)
                approved_dids.add(str(approval.document_id))
            else:
                invalidated.append({
                    "candidate_id": approval.candidate_id,
                    "document_id": str(approval.document_id),
                    "reason": reason,
                })
        return {
            "audit_present": True,
            "audit_valid": bool(verified) and not invalidated,
            "approved_candidate_ids": approved_cids,
            "approved_document_ids": approved_dids,
            "approved_rank_keys": {
                (r.country_code, int(r.year), int(r.position)) for r in evidence.rankings
            },
            "invalidated_approvals": invalidated,
            "error": None,
        }
    except Exception as exc:
        empty["audit_present"] = True
        empty["error"] = str(exc)
        return empty
