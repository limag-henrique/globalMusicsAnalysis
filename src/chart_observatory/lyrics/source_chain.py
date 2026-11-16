"""Re-extract private web evidence and compare to stored text, without network or approval."""

import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from chart_observatory.lyrics.quota_acquisition import (
    extract_genius_preloaded_credits,
    extract_html,
    identity,
    lrclib_text,
    match_genius_identity,
)
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
            if not target:
                continue
        path = Path(event["cache_path"]).resolve()
        if not path.is_relative_to(Path(root).resolve()):
            errors.append("evidence_outside_project")
            continue
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            if source in {"GENIUS", "AZLYRICS", "LETRAS", "MUSIXMATCH"}:
                target_url = urlparse(metadata["url"])
                final_url = urlparse(saved.get("final_url") or event.get("url") or "")
                allowed_hosts = {
                    "GENIUS": {"genius.com", "www.genius.com"},
                    "AZLYRICS": {"azlyrics.com", "www.azlyrics.com"},
                    "LETRAS": {"letras.mus.br", "www.letras.mus.br"},
                    "MUSIXMATCH": {"musixmatch.com", "www.musixmatch.com"},
                }[source]
                if (
                    target_url.hostname not in allowed_hosts
                    or final_url.hostname not in allowed_hosts
                ):
                    continue
                # Accept recorded redirects, never case-fold arbitrary URL paths.
                if target_url.path not in {url.path, final_url.path}:
                    continue
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
                        extracted.append((candidate, actual, event.get("url"), None, None, None))
            elif source in {"GENIUS", "AZLYRICS", "LETRAS", "MUSIXMATCH"}:
                proof = metadata.get("provider_credit_evidence") or {}
                obs_title = metadata.get("observed_title")
                obs_artist = metadata.get("observed_artist")
                song_id = proof.get("song_id") if isinstance(proof, dict) else None
                allowed = genius_performer_names(proof) if isinstance(proof, dict) else []
                reextracted_proof = None
                if source == "GENIUS" and (not proof or not obs_title or not obs_artist):
                    preloaded = extract_genius_preloaded_credits(
                        BeautifulSoup(value, "html.parser")
                    )
                    if preloaded:
                        if not match_genius_identity(
                            payload.get("title"), payload.get("artist"), preloaded
                        ):
                            errors.append("provider_identity_mismatch")
                            continue
                        proof = preloaded
                        reextracted_proof = preloaded
                        obs_title = preloaded.get("title")
                        obs_artist = (preloaded.get("primary_artist") or {}).get("name")
                        song_id = preloaded.get("song_id")
                        allowed = genius_performer_names(preloaded)
                    elif not obs_title or not obs_artist:
                        obs_title = obs_title or payload.get("title")
                        obs_artist = (
                            obs_artist or (payload.get("artist") or "").split("|", 1)[0].strip()
                        )
                candidate = extract_html(
                    value,
                    source,
                    obs_title,
                    obs_artist,
                    allowed,
                    provider_song_id=song_id,
                )
                if candidate:
                    extracted.append(
                        (
                            candidate,
                            actual,
                            event.get("url"),
                            reextracted_proof,
                            obs_title,
                            obs_artist,
                        )
                    )
        except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
            errors.append(type(error).__name__)
    matching = [
        r
        for r in extracted
        if normalize_text(r[0]).normalized_hash == normalize_text(body).normalized_hash
    ]
    if matching:
        pending = bool(audit["source_quarantined"] or audit["text_quality_flags"])
        exact = next(
            (item for item in matching if hashlib.sha256(item[0].encode()).hexdigest() == digest),
            None,
        )
        selected = exact or matching[0]
        extra = {}
        if selected[3] is not None:
            extra = {
                "reextracted_provider_credit_evidence": selected[3],
                "reextracted_observed_title": selected[4],
                "reextracted_observed_artist": selected[5],
            }
        return dict(
            outcome,
            status="source_chain_match_metadata_pending" if pending else "source_chain_matched",
            evidence_sha256=selected[1],
            source_url=selected[2],
            exact_text_hash_match=exact is not None,
            extracted_text_sha256=hashlib.sha256(selected[0].encode()).hexdigest(),
            errors=errors,
            **extra,
        )
    return dict(
        outcome,
        status="source_text_difference" if extracted else "raw_evidence_unresolved",
        errors=errors,
    )
