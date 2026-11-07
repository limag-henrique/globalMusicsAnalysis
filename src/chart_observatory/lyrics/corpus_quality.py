"""Conservative quality states for acquired candidates, never automatic approval."""

from __future__ import annotations

import hashlib

from chart_observatory.lyrics.quota_discovery import audit_saved_result
from chart_observatory.lyrics.text_quality import prepare_lyric_derivative

QUALITY_AUDIT_VERSION = "quota-corpus-quality-v1"


def assess_acquired_lyric(payload, source_result, text, expected_hash):
    if text is None:
        return dict(
            quality_state="unavailable",
            flags=["no_local_text"],
            hash_verified=False,
            identity_validated=False,
            completeness_validated=False,
            classification_ready=False,
        )
    source_audit = audit_saved_result(
        {**payload, "title": payload.get("title") or "", "artist": payload.get("artist") or ""},
        source_result,
    )
    derivative = prepare_lyric_derivative(text, source_result.get("source", "UNKNOWN"))
    flags = set(source_audit["text_quality_flags"]) | set(derivative.flags)
    if not payload.get("title") or not payload.get("artist"):
        flags.add("recording_metadata_missing")
    actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if actual != expected_hash:
        flags.add("stored_text_hash_mismatch")
    if actual != source_result.get("text_sha256"):
        flags.add("source_result_hash_mismatch")
    if "explicit_partial_lyrics_notice" in flags or any(
        "declared_incomplete" in flag or "declares_incomplete" in flag for flag in flags
    ):
        state = "source_declared_partial"
    elif source_audit["source_quarantined"] or any(
        any(
            key in f for key in ("mismatch", "conflict", "different_titles", "different_performers")
        )
        for f in flags
    ):
        state = "identity_conflict"
    elif any(
        any(key in f for key in ("short_text", "missing_initial", "partial", "residue", "encoded"))
        for f in flags
    ):
        state = "suspected_partial"
    elif flags:
        state = "pending_adjudication"
    else:
        state = "acquired_unverified"
    return dict(
        quality_state=state,
        flags=sorted(flags),
        hash_verified=actual == expected_hash,
        characters=len(text),
        original_sha256=actual,
        derivative_sha256=derivative.derivative_sha256,
        transformations=list(derivative.transformations),
        source_quarantined=source_audit["source_quarantined"],
        identity_validated=False,
        completeness_validated=False,
        classification_ready=False,
    )
