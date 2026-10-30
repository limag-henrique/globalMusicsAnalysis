"""Hash-bound human reports; scores remain evidence, never automatic ground truth."""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_REVIEW_EVIDENCE = Path(__file__).resolve().parents[3] / "config/lyrics_review_evidence.json"


def _decision(review: dict[str, Any]) -> str:
    if review["identityVerdict"] == "mismatch":
        return "reported_identity_mismatch"
    complaint = re.search(
        r"incomplet|ausent|cortad|sintetiz|omite|omiti|não foi abordada|importação.*incorret",
        review.get("justification", ""), re.IGNORECASE,
    )
    if complaint:
        return "reported_text_defect"
    if review["identityVerdict"] == "uncertain":
        return "reported_identity_uncertain"
    return "review_recorded"


def import_comparison_export(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if payload.get("exportVersion") != "research-comparison-export-v1":
        raise ValueError("unsupported comparison export")
    evidence = []
    seen = set()
    for item in payload["evaluations"]:
        recording, review = item["recording"], item["review"]
        for key in ("documentId", "lyricsHash"):
            if not recording.get(key) or recording[key] != review.get(key):
                raise ValueError(f"review binding mismatch: {key}")
        if recording["id"] != review.get("recordingId"):
            raise ValueError("review binding mismatch: recordingId")
        if review["id"] in seen:
            raise ValueError("duplicate review id")
        seen.add(review["id"])
        evidence.append({
            "review_id": review["id"],
            "campaign_fingerprint": payload["campaignFingerprint"],
            "document_id": recording["documentId"],
            "lyrics_hash": recording["lyricsHash"],
            "recording_id": recording["id"],
            "title": recording.get("title"),
            "artist": recording.get("artist"),
            "market": recording.get("market"),
            "ai_exposed": review.get("aiExposed"),
            "identity_verdict": review["identityVerdict"],
            "justification": review.get("justification", ""),
            "recorded_language": review.get("recordedLanguage"),
            "reviewed_at": review.get("at"),
            "decision": _decision(review),
            "status": "pending_adjudication",
            "provenance": item["comparison"].get("provenance", {}),
            "export_sha256": hashlib.sha256(raw).hexdigest(),
        })
    return evidence


def load_review_evidence(path: Path = DEFAULT_REVIEW_EVIDENCE) -> list[dict[str, Any]]:
    return _load_review_evidence(path, path.stat().st_mtime_ns)


@lru_cache(maxsize=4)
def _load_review_evidence(path: Path, modified_ns: int) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported review evidence schema")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not all(isinstance(row, dict) for row in entries):
        raise ValueError("invalid review evidence entries")
    return [dict(row) for row in entries]


def review_blocks(evidence: list[dict[str, Any]], document_id: str, lyrics_hash: str) -> bool:
    return any(
        row["document_id"] == document_id and row["lyrics_hash"] == lyrics_hash
        and row["status"] == "pending_adjudication"
        and row["decision"] in {
            "reported_identity_mismatch", "reported_text_defect", "reported_identity_uncertain",
        }
        for row in evidence
    )
