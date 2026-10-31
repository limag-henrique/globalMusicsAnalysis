"""Discover real provider URLs, keeping exact song/version checks before extraction."""

import hashlib
import re
import threading
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlparse

from chart_observatory.lyrics.quota_acquisition import (
    candidate,
    extract_html,
    fetch_candidate,
    identity,
    lrclib_text,
)
from chart_observatory.lyrics.text_quality import prepare_lyric_derivative


def recover_with_fallback(title, artist, http, *, first_time=False, browser=None):
    """Try paced alternative HTML sources even for previously attempted candidates."""
    payload = dict(title=title, artist=artist)

    def acceptable(result):
        audit = audit_saved_result(payload, result)
        return bool(result.get("text")) and not (
            audit["source_quarantined"] or audit["text_quality_flags"]
        )

    initial = fetch_candidate(title, artist, http) if first_time else {}
    if acceptable(initial):
        return initial
    discovered = discover_candidate(title, artist, http, browser=browser)
    if acceptable(discovered):
        return discovered
    alternative = fetch_candidate(title, artist, http, html_sources={"AZLYRICS", "MUSIXMATCH"})
    if acceptable(alternative):
        return alternative
    # Keep rejected evidence available for review; never label it validated.
    if discovered.get("text"):
        return discovered
    if initial.get("text"):
        return initial
    return {
        **discovered,
        "source_errors": list(discovered.get("source_errors", []))
        + list(alternative.get("source_errors", [])),
    }


def search_identities(title, artist):
    """Artist credit separators may differ; song/version words are never removed."""
    if (
        not isinstance(title, str)
        or not title.strip()
        or not isinstance(artist, str)
        or not artist.strip()
    ):
        return []
    artists = [artist]
    if "|" in artist:
        credits = [value.strip() for value in artist.split("|") if value.strip()]
        # Discovery queries may vary; acceptance still requires the original full credits.
        artists = [" ".join(credits), *credits[:3]]
    return list(dict.fromkeys(artists))


FEATURE_CREDIT = re.compile(r"[\[(]\s*(?:feat\.?|ft\.?|featuring|with)\s+([^\])]+)[\])]", re.I)


def match_genius_identity(title, artist, result):
    """Only credit annotations may differ, and featured performers must be evidenced."""
    primary = result.get("primary_artist") or {}
    if not isinstance(primary, dict):
        return False
    featured = result.get("featured_artists") or []
    leads = result.get("primary_artists") or [primary]
    if not isinstance(leads, list):
        leads = [primary]
    names = [r.get("name", "") for r in leads if isinstance(r, dict)] + [
        r.get("name", "") for r in featured if isinstance(r, dict)
    ]
    names = [name for name in names if isinstance(name, str) and name.strip()]
    if not names:
        return False
    if "|" in artist:
        required = {identity(value) for value in artist.split("|") if value.strip()}
        supporting = []
        for field in ("producer_artists", "writer_artists"):
            values = result.get(field) or []
            if isinstance(values, list):
                supporting.extend(r.get("name", "") for r in values if isinstance(r, dict))
        credits = {identity(name) for name in names + supporting if isinstance(name, str)}
        lead_names = {identity(r.get("name")) for r in leads if isinstance(r, dict)}
        allowed_performers = required | {identity(value) for value in FEATURE_CREDIT.findall(title)}
        artist_matches = (
            required.issubset(credits)
            and bool(required & lead_names)
            and {identity(name) for name in names}.issubset(allowed_performers)
        )
    else:
        extra = [name for name in names if identity(name) != identity(artist)]
        annotated = {identity(value) for value in FEATURE_CREDIT.findall(title)}
        all_extras_annotated = (
            not extra
            or all(identity(name) in annotated for name in extra)
            or identity(" | ".join(extra)) in annotated
        )
        artist_matches = identity(" | ".join(names)) == identity(artist) or (
            identity(primary.get("name")) == identity(artist) and all_extras_annotated
        )
    if not artist_matches:
        return False
    if identity(result.get("title")) == identity(title):
        return True
    credits = FEATURE_CREDIT.findall(title)
    if not credits or identity(FEATURE_CREDIT.sub("", title)) != identity(result.get("title")):
        return False
    observed = {identity(name) for name in names[1:]}
    observed.add(identity(" | ".join(names[1:])))
    return all(identity(credit) in observed for credit in credits)


def genius_performer_names(proof):
    leads = proof.get("primary_artists") or [proof.get("primary_artist")]
    featured = proof.get("featured_artists") or []
    if not isinstance(leads, list) or not isinstance(featured, list):
        return []
    people = leads + featured
    if not people or any(
        not isinstance(person, dict)
        or not isinstance(person.get("name"), str)
        or not person["name"].strip()
        for person in people
    ):
        return []
    return [person["name"] for person in people]


def match_lrclib_credit_binding(title, artist, observed_artist, metadata):
    proof = metadata.get("provider_credit_evidence") or {}
    url = metadata.get("credit_binding_url")
    if not isinstance(proof, dict) or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    song_id = proof.get("song_id")
    if (
        metadata.get("credit_binding_provider") != "GENIUS"
        or parsed.scheme != "https"
        or parsed.hostname != "genius.com"
        or parsed.username
        or not isinstance(song_id, int)
        or isinstance(song_id, bool)
        or song_id <= 0
    ):
        return False
    names = genius_performer_names(proof)
    return (
        bool(names)
        and identity(observed_artist) == identity(" | ".join(names))
        and (
            match_genius_identity(
                title, artist, {**proof, "title": metadata.get("credit_binding_title")}
            )
        )
    )


def role_bound_lrclib_candidate(title, artist, rows, proofs):
    matches = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or row.get("instrumental")
            or identity(row.get("trackName")) != identity(title)
            or not lrclib_text(row)
        ):
            continue
        for url, _lead, credit_title, proof in proofs:
            metadata = dict(
                credit_binding_provider="GENIUS",
                credit_binding_url=url,
                credit_binding_title=credit_title,
                provider_credit_evidence=proof,
            )
            if match_lrclib_credit_binding(title, artist, row.get("artistName"), metadata):
                matches.append((row, metadata))
    texts = {lrclib_text(row) for row, _metadata in matches}
    if len(texts) != 1:
        return None, len(texts) > 1
    row, metadata = matches[0]
    return candidate(
        next(iter(texts)),
        "LRCLIB",
        id=row.get("id"),
        observed_title=row["trackName"],
        observed_artist=row["artistName"],
        requested_artist=artist,
        full_requested_artist_credit_matched=True,
        lyric_representation="plain" if row.get("plainLyrics") else "timestamped_lrc",
        discovery="exact_title_and_role_bound_performers",
        **metadata,
    ), False


def discover_candidate(title, artist, http, browser=None):
    http.start_trace()
    errors, urls, seen = [], [], set()
    lyric_rows = []
    artists = search_identities(title, artist)
    if not artists:
        return dict(
            status="metadata_missing", source_errors=["title_or_artist_missing"], http_evidence=[]
        )
    accepted_artists = {identity(artist)}
    for credited in artists:
        response = http.get("https://lrclib.net/api/search", params={"q": f"{credited} {title}"})
        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                data = []
            if isinstance(data, list):
                lyric_rows.extend(data)
            exact = (
                [
                    r
                    for r in data
                    if isinstance(r, dict)
                    and identity(r.get("trackName")) == identity(title)
                    and identity(r.get("artistName")) in accepted_artists
                    and not r.get("instrumental")
                    and lrclib_text(r)
                ]
                if isinstance(data, list)
                else []
            )
            texts = {lrclib_text(r) for r in exact}
            if len(texts) == 1:
                result = candidate(
                    next(iter(texts)),
                    "LRCLIB",
                    id=exact[0].get("id"),
                    observed_title=exact[0].get("trackName"),
                    observed_artist=exact[0].get("artistName"),
                    requested_artist=artist,
                    lyric_representation="plain"
                    if exact[0].get("plainLyrics")
                    else "timestamped_lrc",
                    discovery="free_text_search_exact_result",
                    full_requested_artist_credit_matched=True,
                )
                if result:
                    return {**result, "http_evidence": list(http.trace)}
            if len(texts) > 1:
                errors.append("divergent_exact_lrclib_editions")
        else:
            errors.append(f"LRCLIB:{response.status_code}")
        response = http.get(
            "https://genius.com/api/search/multi",
            params={"per_page": 5, "q": f"{credited} {FEATURE_CREDIT.sub('', title).strip()}"},
        )
        if response.status_code != 200:
            errors.append(f"GENIUS_SEARCH:{response.status_code}")
            continue
        try:
            data = response.json()
        except ValueError:
            errors.append("GENIUS_SEARCH:invalid_json")
            continue
        if not isinstance(data, dict):
            continue
        envelope = data.get("response")
        if not isinstance(envelope, dict):
            continue
        for section in envelope.get("sections", []):
            if not isinstance(section, dict) or section.get("type") not in ("song", "top_hit"):
                continue
            for hit in section.get("hits", []):
                result = hit.get("result") if isinstance(hit, dict) else None
                if not isinstance(result, dict):
                    continue
                primary = result.get("primary_artist") or {}
                if not isinstance(primary, dict):
                    continue
                if result.get("lyrics_state") not in (None, "complete"):
                    errors.append("GENIUS_SEARCH:lyrics_declared_incomplete")
                    continue
                if not match_genius_identity(title, artist, result):
                    primary_name = identity(primary.get("name"))
                    requested_names = {identity(value) for value in artist.split("|")}
                    title_matches = identity(result.get("title")) in {
                        identity(title),
                        identity(FEATURE_CREDIT.sub("", title)),
                    }
                    song_id = result.get("id")
                    if not (
                        title_matches
                        and primary_name in requested_names
                        and isinstance(song_id, int)
                        and not isinstance(song_id, bool)
                    ):
                        continue
                    detail = http.get(f"https://genius.com/api/songs/{song_id}")
                    if detail.status_code != 200:
                        errors.append(f"GENIUS_CREDITS:{detail.status_code}")
                        continue
                    try:
                        detailed = detail.json().get("response", {}).get("song", {})
                    except (ValueError, AttributeError):
                        continue
                    if (
                        not isinstance(detailed, dict)
                        or detailed.get("id") != song_id
                        or not match_genius_identity(title, artist, detailed)
                    ):
                        continue
                    result = detailed
                    primary = result.get("primary_artist") or primary
                if result.get("lyrics_state") not in (None, "complete"):
                    errors.append("GENIUS_CREDITS:lyrics_declared_incomplete")
                    continue
                url = result.get("url")
                if (
                    isinstance(url, str)
                    and urlparse(url).scheme == "https"
                    and urlparse(url).hostname == "genius.com"
                    and url not in seen
                ):
                    seen.add(url)
                    credits = {
                        field: [
                            {"id": person.get("id"), "name": person.get("name")}
                            for person in result.get(field, []) or []
                            if isinstance(person, dict)
                        ]
                        for field in (
                            "primary_artists",
                            "featured_artists",
                            "producer_artists",
                            "writer_artists",
                        )
                    }
                    credits["primary_artist"] = {
                        "id": primary.get("id"),
                        "name": primary.get("name"),
                    }
                    credits["song_id"] = result.get("id")
                    credits["lyrics_state"] = result.get("lyrics_state")
                    urls.append((url, primary.get("name"), result.get("title"), credits))
    for url, credited, observed_title, credits in urls[:3]:
        allowed_artists = [credits["primary_artist"].get("name")]
        for field in ("primary_artists", "featured_artists"):
            allowed_artists.extend(person.get("name") for person in credits[field])
        response = http.get(url)
        if response.status_code != 200:
            errors.append(f"GENIUS_PAGE:{response.status_code}")
            continue
        value = extract_html(
            response.text,
            "GENIUS",
            observed_title,
            credited,
            allowed_artists,
            provider_song_id=credits["song_id"],
        )
        if not value and browser is not None:
            rendered = browser.fetch(url)
            if rendered:
                value = extract_html(
                    rendered,
                    "GENIUS",
                    observed_title,
                    credited,
                    allowed_artists,
                    provider_song_id=credits["song_id"],
                )
        result = candidate(
            value,
            "GENIUS",
            url=str(response.url),
            discovery="provider_search_exact_result",
            observed_title=observed_title,
            observed_artist=credited,
            requested_artist=artist,
            full_requested_artist_credit_matched=True,
            provider_credit_evidence=credits,
            page_identity_scope="main_entity_only",
        )
        if result:
            return {**result, "http_evidence": list(http.trace)}
        errors.append("GENIUS_PAGE:identity_or_container_unverified")
    role_proofs = [
        item
        for item in urls[:3]
        if identity(" | ".join(genius_performer_names(item[3]))) != identity(artist)
    ]
    bound, conflicting = role_bound_lrclib_candidate(title, artist, lyric_rows, role_proofs)
    if bound:
        return {**bound, "http_evidence": list(http.trace)}
    if role_proofs and not conflicting:
        queries = list(
            dict.fromkeys(
                [
                    artist.split("|", 1)[0].strip(),
                    *(" | ".join(genius_performer_names(item[3])) for item in role_proofs),
                ]
            )
        )
        for query_artist in queries[:4]:
            if not query_artist:
                continue
            response = http.get(
                "https://lrclib.net/api/search",
                params={
                    "track_name": title,
                    "artist_name": query_artist,
                },
            )
            if response.status_code != 200:
                errors.append(f"LRCLIB_ROLE_BINDING:{response.status_code}")
                continue
            try:
                rows = response.json()
            except ValueError:
                continue
            if isinstance(rows, list):
                lyric_rows.extend(rows)
        bound, conflicting = role_bound_lrclib_candidate(title, artist, lyric_rows, role_proofs)
        if bound:
            return {**bound, "http_evidence": list(http.trace)}
    if conflicting:
        errors.append("divergent_role_bound_lrclib_editions")
    return dict(
        status="not_found_or_unverified",
        source_errors=errors,
        discovered_urls=[row[0] for row in urls],
        http_evidence=list(http.trace),
    )


class PublicBrowser:
    """Bounded standard Chromium rendering; no login, CAPTCHA or access-control bypass."""

    def __init__(self, maximum_pages=200):
        self.maximum_pages = maximum_pages
        self.pages = 0
        self.guard = threading.Lock()
        self.slots = threading.BoundedSemaphore(2)

    def fetch(self, url):
        if urlparse(url).hostname != "genius.com":
            return None
        with self.guard:
            if self.pages >= self.maximum_pages:
                return None
            self.pages += 1
        with self.slots:
            from playwright.sync_api import Error, sync_playwright

            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    page = browser.new_page()
                    response = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    if not response or response.status != 200:
                        browser.close()
                        return None
                    with suppress(Error):
                        page.locator('[data-lyrics-container="true"]').first.wait_for(timeout=5000)
                    html = page.content()
                    browser.close()
                    return html
            except Error:
                return None


def audit_saved_result(payload, result):
    """Audit evidence already stored; never equate metadata matching with completeness."""
    flags = list(result.get("text_quality_flags", []))
    requested = payload.get("artist") or ""
    metadata = result.get("source_metadata") or {}
    evidenced_artist = metadata.get("requested_artist") or metadata.get("observed_artist")
    if ("|" in requested or ", " in requested) and (
        metadata.get("full_requested_artist_credit_matched") is not True
        or identity(evidenced_artist) != identity(requested)
    ):
        flags.append("requested_collaboration_credits_unverified")
    source = result.get("source", "UNKNOWN")
    role_bound = source == "LRCLIB" and match_lrclib_credit_binding(
        payload.get("title"), requested, metadata.get("observed_artist"), metadata
    )
    if source in {"LRCLIB", "AZLYRICS", "MUSIXMATCH"} and (
        identity(metadata.get("observed_title")) != identity(payload.get("title"))
        or (identity(metadata.get("observed_artist")) != identity(requested) and not role_bound)
    ):
        flags.append("requested_title_or_artist_metadata_mismatch")
    expected_scope = {"AZLYRICS": "exact_page_title", "MUSIXMATCH": "main_entity_only"}
    if source in expected_scope and metadata.get("page_identity_scope") != expected_scope[source]:
        flags.append("page_identity_scope_unverified")
    if source == "GENIUS":
        if metadata.get("page_identity_scope") != "main_entity_only":
            flags.append("page_identity_scope_unverified")
        proof = metadata.get("provider_credit_evidence")
        if isinstance(proof, dict) and proof.get("lyrics_state") not in (None, "complete"):
            flags.append("provider_declares_incomplete_lyrics")
        if not isinstance(proof, dict):
            flags.append("full_provider_performer_evidence_missing")
        elif not match_genius_identity(
            payload["title"], requested, {**proof, "title": metadata.get("observed_title")}
        ):
            flags.append("provider_performer_or_version_mismatch")
    if (
        result.get("identity_check") == "cached_exact_metadata_not_recording_validation"
        or metadata.get("existing_document_id")
        or metadata.get("existing_acquisition")
    ):
        flags.append("source_identity_evidence_missing")
    return dict(
        requested_title=payload["title"],
        requested_artist=payload["artist"],
        source=source,
        source_quarantined=source == "LETRAS" or result.get("quarantined_source", False),
        identity_evidence=result.get("identity_check", "unknown"),
        text_quality_flags=flags,
        identity_validated=False,
        completeness_validated=False,
        status="review_required",
        classification_ready=False,
        reason="Source metadata and full DOM extraction do not prove the recording transcription",
    )


def settle_metadata_reconciliation(payload, result):
    """Clear a naming mismatch only, never the recording or completeness review."""
    if not payload.get("requires_metadata_reconciliation") or not result.get("text"):
        return payload
    audit = audit_saved_result(payload, result)
    if audit["source_quarantined"] or audit["text_quality_flags"]:
        return payload
    meta = result.get("source_metadata") or {}
    if (
        result.get("source") != "GENIUS"
        and (
            identity(meta.get("observed_title")) != identity(payload.get("title"))
            or identity(meta.get("observed_artist")) != identity(payload.get("artist"))
        )
        and not (
            result.get("source") == "LRCLIB"
            and match_lrclib_credit_binding(
                payload.get("title"), payload.get("artist"), meta.get("observed_artist"), meta
            )
        )
    ):
        return payload
    return {
        **payload,
        "requires_metadata_reconciliation": False,
        "metadata_reconciled_with_source": True,
    }


def usable_cached_replay(payload, current_result, replay):
    """A replay may fill a gap; never replace an existing text or another song."""
    if current_result.get("text_path") or current_result.get("text_sha256"):
        return None
    if any(
        not isinstance(payload.get(field), str) or not payload[field].strip()
        for field in ("title", "artist")
    ):
        return None
    previous, result = replay.get("payload", {}), replay.get("result", {})
    if payload.get("recording_id") != previous.get("recording_id") or any(
        identity(payload.get(field)) != identity(previous.get(field))
        for field in ("title", "artist")
    ):
        return None
    if (
        result.get("source") not in {"GENIUS", "LRCLIB", "AZLYRICS", "MUSIXMATCH"}
        or result.get("generated_by_ai") is not False
    ):
        return None
    if not isinstance(result.get("text"), str) or not result["text"].strip():
        return None
    audit = audit_saved_result(payload, result)
    return result if not audit["source_quarantined"] and not audit["text_quality_flags"] else None


def usable_cached_repair(payload, current_result, replay):
    """Replace only a flagged candidate with a proposal bound to its exact old hash."""
    digest = current_result.get("text_sha256")
    if (
        not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        or replay.get("replay_kind") != "flagged_repair"
        or replay.get("replaces_text_sha256") != digest
    ):
        return None
    audit = audit_saved_result(payload, current_result)
    if not audit["source_quarantined"] and not audit["text_quality_flags"]:
        # Older saved results may predate the current text-quality rules.
        try:
            raw = Path(current_result["text_path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                return None
            quality = prepare_lyric_derivative(
                raw.decode("utf-8"), current_result.get("source", "UNKNOWN")
            )
        except (KeyError, OSError, UnicodeError):
            return None
        if not quality.flags:
            return None
    return usable_cached_replay(payload, {}, replay)
