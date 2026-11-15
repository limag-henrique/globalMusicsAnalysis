"""Compare captured lyrics with a fresh public source; agreement is never adjudication."""

import base64
import hashlib
import json
import shutil
from datetime import datetime
from urllib.parse import urlparse

from chart_observatory.lyrics.quota_acquisition import candidate, identity, lrclib_text
from chart_observatory.lyrics.quota_discovery import (
    audit_saved_result,
    match_lrclib_credit_binding,
)
from chart_observatory.lyrics.revision_protocol import normalize_text
from chart_observatory.lyrics.text_quality import recording_duration_mismatch


def reuse_recent_web_responses(source, destination, now, max_age_seconds=86400):
    """Extend the same comparison pass without changing response bytes or dates."""
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in source.glob("*.json"):
        target = destination / path.name
        if target.exists():
            continue
        try:
            raw = path.read_bytes()
            record = json.loads(raw)
            url = record["url"]
            parsed = urlparse(url)
            observed = datetime.fromisoformat(record["retrieved_at"])
            if (
                parsed.scheme != "https"
                or parsed.hostname != "lrclib.net"
                or parsed.username
                or observed.tzinfo is None
                or not 0 <= (now - observed).total_seconds() <= max_age_seconds
                or path.name != hashlib.sha256(url.encode()).hexdigest() + ".json"
            ):
                continue
            body = (
                base64.b64decode(record["body_base64"], validate=True)
                if "body_base64" in record
                else record["body"].encode("utf-8")
            )
            if hashlib.sha256(body).hexdigest() != record["body_sha256"]:
                continue
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if shutil.disk_usage(destination).free < 1024**3 + 2 * len(raw):
            raise OSError("insufficient disk space for response evidence")
        part = target.with_suffix(".part")
        part.write_bytes(raw)
        part.replace(target)
        copied += 1
    return copied


def compare_lrclib(payload, baseline, body, expected_hash, rows, evidence):
    outcome = dict(
        identity_validated=False,
        completeness_validated=False,
        classification_ready=False,
        stored_sha256=expected_hash,
    )
    if body is not None and hashlib.sha256(body.encode()).hexdigest() != expected_hash:
        return dict(outcome, status="stored_hash_mismatch"), None
    metadata = baseline.get("source_metadata") or {}
    binding = dict(metadata)
    if baseline.get("source") == "GENIUS":
        binding.update(
            credit_binding_provider="GENIUS",
            credit_binding_url=metadata.get("url"),
            credit_binding_title=metadata.get("observed_title"),
        )
    matches = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if (
            identity(row.get("trackName")) != identity(payload.get("title"))
            or recording_duration_mismatch(
                (payload.get("metadata_resolution") or {}).get("duration_ms"), row.get("duration")
            )
            or row.get("instrumental") is True
            or not lrclib_text(row)
        ):
            continue
        direct = identity(row.get("artistName")) == identity(payload.get("artist"))
        role_bound = match_lrclib_credit_binding(
            payload.get("title"), payload.get("artist"), row.get("artistName"), binding
        )
        if not direct and not role_bound:
            continue
        matches.append((row, role_bound and not direct))
    signatures = {normalize_text(lrclib_text(row)).normalized_hash for row, _ in matches}
    if not signatures:
        return dict(outcome, status="no_matching_web_text"), None
    if len(signatures) != 1:
        return dict(
            outcome,
            status="ambiguous_web_editions",
            editions=len(signatures),
            provider_ids=[r.get("id") for r, _ in matches],
        ), None
    row, role_bound = matches[0]
    remote = lrclib_text(row)
    matched = body is not None and normalize_text(body).normalized_hash in signatures
    if body is None:
        status = "web_candidate_available"
    elif not matched:
        status = "web_text_differs"
    else:
        status = (
            "same_provider_text_matches"
            if baseline.get("source") == "LRCLIB"
            else "cross_provider_text_matches"
        )
    result = candidate(
        remote,
        "LRCLIB",
        id=row.get("id"),
        observed_title=row.get("trackName"),
        observed_artist=row.get("artistName"),
        duration_seconds=row.get("duration"),
        requested_artist=payload.get("artist"),
        full_requested_artist_credit_matched=True,
        **(
            {
                k: binding[k]
                for k in (
                    "credit_binding_provider",
                    "credit_binding_url",
                    "credit_binding_title",
                    "provider_credit_evidence",
                )
                if k in binding
            }
            if role_bound
            else {}
        ),
    )
    outcome.update(
        status=status,
        remote_sha256=hashlib.sha256(remote.encode()).hexdigest(),
        provider_id=row.get("id"),
        provider_title=row.get("trackName"),
        provider_artist=row.get("artistName"),
        provider_duration_seconds=row.get("duration"),
        http_evidence=evidence,
    )
    if result is None:
        return dict(outcome, status="web_text_declares_partial"), None
    result["http_evidence"] = evidence
    audit = audit_saved_result(payload, result)
    outcome["candidate_flags"] = audit["text_quality_flags"]
    if audit["source_quarantined"] or audit["text_quality_flags"]:
        return outcome, None
    return outcome, result
