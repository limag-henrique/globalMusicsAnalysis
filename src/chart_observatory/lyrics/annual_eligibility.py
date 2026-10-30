"""Shared post-ranking contract for daily and weekly annual chart adapters.

Evidence is an explicit adjudication record, never inferred from scrape success,
text length, model output or agreement between potentially mirrored websites.
"""

import re
from collections import defaultdict
from urllib.parse import urlparse

SHA256 = re.compile(r"[0-9a-f]{64}")
GROUP = ("country_code", "year", "platform", "window")


def select_eligible(candidates, validations, *, current_documents, blocked=(),
                    reusable_classifications=()):
    """Return both samples, loss accounting and a recording/hash-deduplicated queue.

    current_documents maps document ID to the database recording ID and hash.
    reusable_classifications contains already filtered recording/hash signatures
    for the requested model, taxonomy and prompt; other historical runs do not count.
    """
    evidence = defaultdict(list)
    for entry in validations:
        evidence[entry["candidate_id"]].append(entry)
    blocked, reusable = set(blocked), set(reusable_classifications)
    groups = defaultdict(list)
    for row in candidates:
        groups[tuple(row[k] for k in GROUP)].append(row)
    original, eligible, coverage, queue = [], [], [], {}
    for group, rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda row: row["position"])
        positions = [r["position"] for r in rows]
        if len(set(positions)) != len(positions) or any(p < 1 for p in positions):
            raise ValueError("duplicate or invalid annual positions")
        selected, seen_recordings = [], set()
        losses = 0
        for row in rows:
            binding, reason = _validate(row, evidence[row["candidate_id"]],
                                        current_documents, blocked)
            signature = None
            if binding:
                signature = (binding["recording_id"], binding["lyrics_hash"])
                if binding["recording_id"] in seen_recordings:
                    reason = "duplicate_recording"
                elif len(selected) < 80:
                    seen_recordings.add(binding["recording_id"])
            annotated = {**row, "eligibility_reason": reason}
            if row["position"] <= 80:
                original.append(annotated)
                losses += reason != "eligible"
            if reason != "eligible" or len(selected) >= 80:
                continue
            item = {**annotated, "document_id": binding["document_id"],
                    "lyrics_hash": binding["lyrics_hash"], "eligible_position": len(selected) + 1}
            selected.append(item)
            if signature not in reusable:
                task = queue.setdefault(signature, {
                    "recording_id": signature[0], "lyrics_hash": signature[1],
                    "document_id": binding["document_id"], "memberships": [],
                    "status": "prepared_not_submitted",
                })
                task["memberships"].append({k: item[k] for k in (*GROUP, "position")})
        eligible.extend(selected)
        coverage.append({**dict(zip(GROUP, group, strict=True)),
                         "candidates": len(rows), "eligible_tracks": len(selected),
                         "deficit": 80 - len(selected), "original_losses": losses,
                         "original_positions_available": sum(r["position"] <= 80 for r in rows),
                         "reserve_entries": sum(r["position"] > 80 for r in selected),
                         "status": "COMPLETE" if len(selected) == 80 else "INCOMPLETE"})
    return {"original_top80": original, "eligible": eligible, "coverage": coverage,
            "classification_queue": list(queue.values())}


def _validate(row, entries, documents, blocked):
    if row.get("coverage_status") != "COMPLETE":
        return None, "coverage_incomplete"
    if not row.get("recording_id"):
        return None, "identity_unresolved"
    if not entries:
        return None, "validation_missing"
    if len(entries) != 1:
        return None, "validation_ambiguous"
    entry = entries[0]
    document, digest = entry.get("document_id"), entry.get("lyrics_hash", "")
    if (entry.get("recording_id") != row["recording_id"]
            or documents.get(document) != (row["recording_id"], digest)
            or not SHA256.fullmatch(digest)):
        return None, "validation_binding_mismatch"
    if (document, digest) in blocked:
        return None, "review_blocked"
    if entry.get("identity_verified") is not True:
        return None, "identity_unverified"
    if entry.get("integrity_verified") is not True:
        return None, "integrity_unverified"
    parsed = urlparse(entry.get("evidence_url", ""))
    if (entry.get("method") not in {"official_transcription", "human_audio_verification"}
            or parsed.scheme != "https" or not parsed.hostname
            or not SHA256.fullmatch(entry.get("evidence_sha256", ""))
            or not entry.get("verified_at")):
        return None, "integrity_evidence_missing"
    return entry, "eligible"
