"""Automated, evidence-bound lyric identity and source-field completeness checks."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse

from chart_observatory.lyrics.quota_acquisition import (
    identities_compatible,
    match_genius_identity,
)
from chart_observatory.lyrics.quota_discovery import match_lrclib_credit_binding

VALIDATION_VERSION = "lyric-identity-completeness-v1"

_IDENTITY_BLOCKERS = {
    "requested_title_or_artist_metadata_mismatch",
    "requested_collaboration_credits_unverified",
    "full_provider_performer_evidence_missing",
    "page_identity_scope_unverified",
    "source_identity_evidence_missing",
    "provider_performer_or_version_mismatch",
    "recording_duration_mismatch",
    "same_text_different_titles",
    "same_text_different_performers",
}
_COMPLETENESS_BLOCKERS = {
    "explicit_partial_lyrics_notice",
    "provider_declares_incomplete_lyrics",
    "possible_missing_initial_section",
    "short_text",
    "very_short_text",
    "stored_text_hash_mismatch",
    "source_result_hash_mismatch",
}


def _valid_provider_identity(
    record: dict[str, Any], source_chain: dict[str, Any]
) -> tuple[bool, list[str]]:
    payload = record.get("payload") or {}
    result = record.get("source_result") or {}
    metadata = result.get("source_metadata") or {}
    source = result.get("source")
    title, artist = payload.get("title"), payload.get("artist")
    reasons: list[str] = []
    url = urlparse(str(source_chain.get("source_url") or metadata.get("url") or ""))
    if source == "GENIUS":
        proof = metadata.get("provider_credit_evidence")
        if not isinstance(proof, dict):
            reasons.append("genius_credit_evidence_missing")
        else:
            song_id = proof.get("song_id")
            if not isinstance(song_id, int) or isinstance(song_id, bool) or song_id <= 0:
                reasons.append("genius_song_id_missing")
            if not match_genius_identity(
                title,
                artist,
                {**proof, "title": metadata.get("observed_title")},
            ):
                reasons.append("genius_title_or_performer_credits_do_not_match")
        if url.hostname not in {"genius.com", "www.genius.com"} or url.scheme != "https":
            reasons.append("genius_source_url_unverified")
    elif source == "LRCLIB":
        source_id = metadata.get("id")
        if not isinstance(source_id, int) or isinstance(source_id, bool) or source_id <= 0:
            reasons.append("lrclib_record_id_missing")
        if not identities_compatible(title, metadata.get("observed_title")):
            reasons.append("lrclib_title_mismatch")
        artist_match = identities_compatible(
            artist, metadata.get("observed_artist"), is_artist=True
        ) or match_lrclib_credit_binding(title, artist, metadata.get("observed_artist"), metadata)
        if not artist_match:
            reasons.append("lrclib_performer_credit_mismatch")
        if url.hostname != "lrclib.net":
            reasons.append("lrclib_source_url_unexpected")
    elif source in {"AZLYRICS", "MUSIXMATCH"}:
        expected_host = "azlyrics.com" if source == "AZLYRICS" else "musixmatch.com"
        if url.hostname != expected_host or url.scheme != "https":
            reasons.append("provider_source_url_unverified")
        if not identities_compatible(title, metadata.get("observed_title")):
            reasons.append("provider_title_mismatch")
        if not identities_compatible(artist, metadata.get("observed_artist"), is_artist=True):
            reasons.append("provider_performer_mismatch")
    else:
        reasons.append("provider_not_supported_for_automatic_identity")
    return not reasons, reasons


def assess_lyric_identity_completeness(
    record: dict[str, Any],
    text: str | None,
    source_chain: dict[str, Any],
) -> dict[str, Any]:
    """Assess title/credit identity and completeness against the source's full field.

    This does not claim audio-to-transcription verification, edition equivalence,
    scientific approval, rights clearance, or Vertex/classification readiness.
    """
    digest = record.get("text_sha256")
    audit = record.get("audit") or {}
    source_result = record.get("source_result") or {}
    flags = set(audit.get("text_quality_flags") or [])
    blockers_identity = set(flags & _IDENTITY_BLOCKERS)
    blockers_complete = sorted(flags & _COMPLETENESS_BLOCKERS)
    actual_digest = hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None
    stored_text_ok = bool(
        digest and actual_digest == digest and source_result.get("text_sha256") == digest
    )
    chain_status = source_chain.get("status")
    chain_matched = chain_status in {
        "source_chain_matched",
        "source_chain_match_metadata_pending",
    }
    replay_digest = source_chain.get("extracted_text_sha256")
    exact_replay = source_chain.get("exact_text_hash_match") is True
    source_integrity_ok = bool(
        stored_text_ok
        and chain_matched
        and isinstance(replay_digest, str)
        and len(replay_digest) == 64
        and isinstance(source_chain.get("evidence_sha256"), str)
        and len(source_chain["evidence_sha256"]) == 64
    )

    provider_identity_ok, provider_identity_reasons = _valid_provider_identity(record, source_chain)
    # The fresh native-ID/credit binding below supersedes these legacy metadata-only warnings.
    if provider_identity_ok and source_integrity_ok:
        blockers_identity -= {
            "requested_collaboration_credits_unverified",
            "full_provider_performer_evidence_missing",
            "page_identity_scope_unverified",
            "source_identity_evidence_missing",
        }
    blockers_identity = sorted(blockers_identity)
    identity_pass = (
        source_integrity_ok
        and provider_identity_ok
        and not blockers_identity
        and not audit.get("source_quarantined")
    )
    identity_status = (
        "passed"
        if identity_pass
        else "failed"
        if blockers_identity or any("mismatch" in reason for reason in provider_identity_reasons)
        else "pending"
    )

    source = source_result.get("source")
    metadata = source_result.get("source_metadata") or {}
    proof = metadata.get("provider_credit_evidence") or {}
    if source == "GENIUS":
        provider_declares_complete = proof.get("lyrics_state") == "complete"
        completeness_basis = (
            "provider_declares_complete_and_replayed_dom_container"
            if provider_declares_complete
            else "replayed_full_dom_container_provider_marker_unavailable"
        )
    elif source == "LRCLIB":
        provider_declares_complete = (
            metadata.get("lyric_representation") in {"plain", "timestamped_lrc"}
            and isinstance(metadata.get("duration_seconds"), (int, float))
            and metadata.get("duration_seconds", 0) > 0
        )
        completeness_basis = (
            "provider_full_lyrics_field_replayed_by_record_id"
            if provider_declares_complete
            else "replayed_lrclib_lyrics_field_metadata_incomplete"
        )
    elif source in {"AZLYRICS", "MUSIXMATCH"}:
        completeness_basis = "replayed_designated_provider_lyrics_container"
        provider_declares_complete = False
    else:
        completeness_basis = "no_supported_full_field_evidence"
        provider_declares_complete = False
    provider_field_replayed = source in {"GENIUS", "LRCLIB", "AZLYRICS", "MUSIXMATCH"}

    completeness_pass = (
        source_integrity_ok
        and provider_field_replayed
        and not blockers_complete
        and not audit.get("source_quarantined")
    )
    completeness_status = (
        "passed"
        if completeness_pass
        else "failed"
        if blockers_complete or source_chain.get("status") == "source_text_difference"
        else "pending"
    )
    overall = "passed" if identity_pass and completeness_pass else "pending_review"

    recording_metadata = (record.get("payload") or {}).get("metadata_resolution") or {}
    recording_binding = (
        "duration_evidence_available"
        if recording_metadata.get("duration_ms") and "recording_duration_mismatch" not in flags
        else "not_established_by_lyrics_source"
    )
    return {
        "schema_version": VALIDATION_VERSION,
        "source_text_integrity": {
            "status": "passed" if source_integrity_ok else "pending",
            "stored_hash_verified": stored_text_ok,
            "source_replay_matched": chain_matched,
            "exact_replay_hash_match": exact_replay,
            "stored_text_sha256": digest,
            "replayed_text_sha256": replay_digest,
            "raw_response_sha256": source_chain.get("evidence_sha256"),
            "source_chain_status": chain_status,
            "match_mode": "exact" if exact_replay else "whitespace_normalized",
        },
        "identity": {
            "status": identity_status,
            "scope": "provider song title and billed performer credits",
            "provider_identity_evidence_passed": provider_identity_ok,
            "provider_identity_reasons": provider_identity_reasons,
            "blocking_quality_flags": blockers_identity,
            "recording_version_binding": recording_binding,
        },
        "completeness": {
            "status": completeness_status,
            "scope": "complete text field/container supplied by the lyric provider",
            "basis": completeness_basis,
            "provider_declares_complete": provider_declares_complete,
            "full_provider_field_replayed": provider_field_replayed and source_integrity_ok,
            "normalized_source_replay_sufficient": True,
            "exact_source_replay_passed": exact_replay,
            "blocking_quality_flags": blockers_complete,
        },
        "automated_overall": overall,
        "scientific_approval_status": "not_approved",
        "classification_eligibility": "blocked_pending_gates",
        "limitations": [
            "Does not compare the lyrics with the audio recording.",
            "Does not approve a particular recording edition or live/remix performance.",
            "Does not grant rights or scientific approval.",
        ],
    }
