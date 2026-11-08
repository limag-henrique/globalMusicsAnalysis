"""Re-extract private web evidence and compare to stored text, without network or approval."""

import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from chart_observatory.lyrics.quota_acquisition import extract_html, identity, lrclib_text
from chart_observatory.lyrics.quota_discovery import audit_saved_result, genius_performer_names
from chart_observatory.lyrics.revision_protocol import normalize_text


def verify_source_chain(payload, result, body, digest, root):
    outcome = dict(
        identity_validated=False,
        completeness_validated=False,
        classification_ready=False,
        source=result.get("source", "UNKNOWN"),
    )
    if body is None:
        return dict(outcome, status="unavailable")
    if hashlib.sha256(body.encode()).hexdigest() != digest:
        return dict(outcome, status="stored_hash_mismatch")
    audit = audit_saved_result(payload, result)
    outcome["metadata_flags"] = audit["text_quality_flags"]
    metadata = result.get("source_metadata") or {}
    source = result.get("source")
    errors, extracted = [], []
    for event in result.get("http_evidence", []):
        if event.get("status") != 200 or not event.get("cache_path"):
            continue
        url = urlparse(event.get("url") or "")
        if source == "LRCLIB" and url.hostname != "lrclib.net":
            continue
        if source in {"GENIUS", "AZLYRICS", "LETRAS", "MUSIXMATCH"}:
            target = metadata.get("url")
            if not target or url.path != urlparse(target).path:
                continue
        path = Path(event["cache_path"]).resolve()
        if not path.is_relative_to(Path(root).resolve()):
            errors.append("evidence_outside_project")
            continue
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            raw = (
                base64.b64decode(saved["body_base64"], validate=True)
                if "body_base64" in saved
                else saved["body"].encode()
            )
            actual = hashlib.sha256(raw).hexdigest()
            if actual != saved.get("body_sha256") or actual != event.get("body_sha256"):
                errors.append("raw_response_hash_mismatch")
                continue
            value = raw.decode(saved.get("encoding") or "utf-8")
            if source == "LRCLIB":
                data = json.loads(value)
                rows = data if isinstance(data, list) else [data]
                for row in rows:
                    if (
                        not isinstance(row, dict)
                        or metadata.get("id") is None
                        or row.get("id") != metadata["id"]
                    ):
                        continue
                    if (
                        identity(row.get("trackName")) != identity(metadata.get("observed_title"))
                        or identity(row.get("artistName"))
                        != identity(metadata.get("observed_artist"))
                        or row.get("instrumental") is True
                    ):
                        errors.append("provider_identity_mismatch")
                        continue
                    if candidate := lrclib_text(row):
                        extracted.append((candidate, actual, event.get("url")))
            elif source in {"GENIUS", "AZLYRICS", "LETRAS", "MUSIXMATCH"}:
                proof = metadata.get("provider_credit_evidence") or {}
                candidate = extract_html(
                    value,
                    source,
                    metadata.get("observed_title"),
                    metadata.get("observed_artist"),
                    genius_performer_names(proof),
                    provider_song_id=proof.get("song_id"),
                )
                if candidate:
                    extracted.append((candidate, actual, event.get("url")))
        except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
            errors.append(type(error).__name__)
    matching = [
        r
        for r in extracted
        if normalize_text(r[0]).normalized_hash == normalize_text(body).normalized_hash
    ]
    if matching:
        pending = bool(audit["source_quarantined"] or audit["text_quality_flags"])
        return dict(
            outcome,
            status="source_chain_match_metadata_pending" if pending else "source_chain_matched",
            evidence_sha256=matching[0][1],
            source_url=matching[0][2],
            errors=errors,
        )
    return dict(
        outcome,
        status="source_text_difference" if extracted else "raw_evidence_unresolved",
        errors=errors,
    )
