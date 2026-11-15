"""Conservative full-container retrieval and content-addressed candidate storage."""

import base64
import hashlib
import json
import math
import re
import shutil
import sqlite3
import threading
import time
import unicodedata
from contextlib import closing
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from chart_observatory.lyrics.genius_client import _slugify
from chart_observatory.lyrics.letras_client import _slugify_letras
from chart_observatory.lyrics.recovery_web import CachedRecoveryHTTP
from chart_observatory.lyrics.revision_protocol import NORMALIZATION_VERSION, normalize_text
from chart_observatory.lyrics.text_quality import (
    has_partial_lyrics_notice,
    html_lyric_text,
    outer_lyric_containers,
    prepare_lyric_derivative,
    recording_duration_mismatch,
)


_SEMITIC_OPTIONAL_MARKS = re.compile(r"[\u064b-\u065f\u0670\u0640\u0591-\u05c7]")

_VERSION_OR_TRANSLATION_QUALIFIER = re.compile(
    r"\b(?:live|ao\s+vivo|remix|mix|remaster(?:ed)?|radio\s+edit|edit|version|ver\.?|"
    r"acoustic|ac[uú]stic[oa]?|unplugged|symphonic|instrumental|karaoke|clean|explicit|"
    r"sped\s+up|slowed|reverb|demo|cover|tribute|medley|reprise|skit|pt\.?\s*\d+|part\s+\d+|"
    r"translation|translations|romanized|romanization|"
    r"tradu[cç][aã]o|traducci[oó]n|traduzioni|перевод|번역|翻訳|الترجمة|체크|"
    r"feat\.?|ft\.?|featuring|with|prod\.?|bonus|deluxe|edition|intro|outro|interlude|"
    r"ost|soundtrack|annotated|calendar)\b",
    re.I,
)

_NON_ORIGINAL_ARTIST_MARKER = re.compile(
    r"\b(?:translations?|romanizations?|tradu[cç][õo]es|traducciones?|traduzioni|překlady|české|ceviriler)\b"
    r"|перевод|번역|翻訳|الترجمات|الترجمة|歌詞和訳",
    re.I,
)

FEATURE_CREDIT = re.compile(r"[\[(]\s*(?:feat\.?|ft\.?|featuring|with)\s+([^\])]+)[\])]", re.I)

_VERSION_SUFFIX = re.compile(
    r"\s+-\s+(?=(?:\d{4}\s+)?(?:live|ao vivo|remix|remaster(?:ed)?|radio edit|"
    r"acoustic|instrumental|clean|explicit|sped up|slowed)\b)",
    re.I,
)


def split_feature_credits(title):
    """Remove performer annotations while retaining explicit version suffixes."""
    credits = []

    def replace(match):
        parts = _VERSION_SUFFIX.split(match[1], maxsplit=1)
        credits.append(parts[0].strip())
        return f"({parts[1].strip()})" if len(parts) == 2 else ""

    return FEATURE_CREDIT.sub(replace, title).strip(), credits


def _expand_feature_credits(credits):
    """Split multi-performer feature strings like 'A, B & with C' into individual names."""
    expanded = []
    for credit in credits:
        if not isinstance(credit, str) or not credit.strip():
            continue
        cleaned = re.sub(r"^(?:with|feat\.?|ft\.?|featuring)\s+", "", credit.strip(), flags=re.I)
        parts = [
            re.sub(r"^(?:with|feat\.?|ft\.?|featuring)\s+", "", part.strip(), flags=re.I)
            for part in re.split(r"\s*,\s*&\s*|\s*,\s+|\s+&\s+|\s+\band\b\s+", cleaned, flags=re.I)
            if part.strip()
        ]
        if len(parts) > 1:
            expanded.append((credit.strip(), tuple(parts)))
        else:
            expanded.append((cleaned, (cleaned,)))
    return expanded


def identity(value):
    # Preserve remix/live/clean/explicit qualifiers and featured performers.
    if not isinstance(value, str):
        return ""
    base_norm = unicodedata.normalize("NFKC", value).casefold().strip()
    stripped = _SEMITIC_OPTIONAL_MARKS.sub("", base_norm)
    chars = [
        ch
        if (ch.isalnum() or ch == "_" or unicodedata.category(ch) in ("Mn", "Mc"))
        else " "
        for ch in stripped
    ]
    words = " ".join("".join(chars).split())
    return words or base_norm


def _script_families(text):
    families = set()
    for ch in text:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        for family in (
            "LATIN",
            "CYRILLIC",
            "ARABIC",
            "HEBREW",
            "GREEK",
            "HANGUL",
            "CJK",
            "HIRAGANA",
            "KATAKANA",
            "THAI",
            "DEVANAGARI",
        ):
            if family in name:
                families.add("CJK" if family in ("CJK", "HIRAGANA", "KATAKANA") else family)
                break
    return families


def _split_trailing_parens(value):
    text = value.rstrip()
    if not text.endswith(")"):
        return None
    depth = 0
    for idx in range(len(text) - 1, -1, -1):
        ch = text[idx]
        if ch == ")":
            depth += 1
        elif ch == "(":
            depth -= 1
            if depth == 0:
                base = text[:idx].strip()
                inner = text[idx + 1 : -1].strip()
                return (base, inner) if base and inner else None
    return None


def bilingual_identity_variants(value, *, is_artist=False):
    """Return normalized exact identity plus safe cross-script bilingual aliases."""
    if not isinstance(value, str) or not value.strip():
        return set()
    cur = value.strip()
    out = {identity(cur)}
    if is_artist and _NON_ORIGINAL_ARTIST_MARKER.search(cur):
        out.discard("")
        return out
    if is_artist:
        country_tag = re.fullmatch(r"^(.*\S)\s*\([A-Z]{2,3}\)\s*$", cur)
        if country_tag:
            cur = country_tag[1].strip()
            out.add(identity(cur))
    paren_parts = _split_trailing_parens(cur)
    if paren_parts:
        base, inner = paren_parts
        fams_a, fams_b = _script_families(base), _script_families(inner)
        qualifier_blocked = not is_artist and (
            _VERSION_OR_TRANSLATION_QUALIFIER.search(base)
            or _VERSION_OR_TRANSLATION_QUALIFIER.search(inner)
        )
        if not qualifier_blocked and fams_a and fams_b and fams_a.isdisjoint(fams_b):
            out.add(identity(base))
            out.add(identity(inner))
    if " - " in cur:
        parts = [part.strip() for part in cur.split(" - ") if part.strip()]
        if len(parts) == 2:
            left, right = parts
            fams_a, fams_b = _script_families(left), _script_families(right)
            qualifier_blocked = not is_artist and (
                _VERSION_OR_TRANSLATION_QUALIFIER.search(left)
                or _VERSION_OR_TRANSLATION_QUALIFIER.search(right)
            )
            if not qualifier_blocked and fams_a and fams_b and fams_a.isdisjoint(fams_b):
                out.add(identity(left))
                out.add(identity(right))
    out.discard("")
    return out


def identities_compatible(requested, observed, *, is_artist=False):
    """Match exact identities or strictly disjoint cross-script bilingual equivalents."""
    req_norm, obs_norm = identity(requested), identity(observed)
    if not req_norm or not obs_norm:
        return False
    if req_norm == obs_norm:
        return True
    return bool(
        bilingual_identity_variants(requested, is_artist=is_artist)
        & bilingual_identity_variants(observed, is_artist=is_artist)
    )


def match_genius_identity(title, artist, result):
    """Only credit annotations may differ, and featured performers must be evidenced."""
    if any(not isinstance(value, str) or not value.strip() for value in (title, artist)):
        return False
    feature_title, feature_credits = split_feature_credits(title)
    # Exact provider titles retain the original annotation interpretation.
    if identities_compatible(result.get("title"), title, is_artist=False):
        feature_credits = FEATURE_CREDIT.findall(title)
    primary = result.get("primary_artist") or {}
    if not isinstance(primary, dict):
        return False
    featured = result.get("featured_artists")
    leads = result.get("primary_artists", [primary])
    if not isinstance(featured, list) or not isinstance(leads, list):
        return False
    leads = leads or [primary]
    if any(
        not isinstance(person, dict)
        or not isinstance(person.get("name"), str)
        or not person["name"].strip()
        for person in leads + featured
    ):
        return False
    names = [r.get("name", "") for r in leads if isinstance(r, dict)] + [
        r.get("name", "") for r in featured if isinstance(r, dict)
    ]
    names = [name for name in names if isinstance(name, str) and name.strip()]
    if not names:
        return False
    if "|" in artist:
        req_list = [value.strip() for value in artist.split("|") if value.strip()]
        supporting = []
        for field in ("producer_artists", "writer_artists"):
            values = result.get(field) or []
            if isinstance(values, list):
                supporting.extend(r.get("name", "") for r in values if isinstance(r, dict))
        credit_variants = set()
        for name in names + supporting:
            if isinstance(name, str) and name.strip():
                credit_variants |= bilingual_identity_variants(name, is_artist=True)
        lead_variants = set()
        for r in leads:
            if isinstance(r, dict) and isinstance(r.get("name"), str):
                lead_variants |= bilingual_identity_variants(r["name"], is_artist=True)
        allowed_variants = set()
        for value in req_list:
            allowed_variants |= bilingual_identity_variants(value, is_artist=True)
        for full_credit, split_parts in _expand_feature_credits(feature_credits):
            allowed_variants |= bilingual_identity_variants(full_credit, is_artist=True)
            for part in split_parts:
                allowed_variants |= bilingual_identity_variants(part, is_artist=True)
        artist_matches = (
            all(bilingual_identity_variants(v, is_artist=True) & credit_variants for v in req_list)
            and bool(any(bilingual_identity_variants(v, is_artist=True) & lead_variants for v in req_list))
            and all(bilingual_identity_variants(n, is_artist=True) & allowed_variants for n in names)
        )
    else:
        extra = [name for name in names if not identities_compatible(name, artist, is_artist=True)]
        expanded = _expand_feature_credits(feature_credits)
        annotated = set()
        for full_credit, split_parts in expanded:
            annotated |= bilingual_identity_variants(full_credit, is_artist=True)
            for part in split_parts:
                annotated |= bilingual_identity_variants(part, is_artist=True)
        all_extras_annotated = (
            not extra
            or all(bool(bilingual_identity_variants(name, is_artist=True) & annotated) for name in extra)
            or identity(" | ".join(extra)) in annotated
        )
        artist_matches = identities_compatible(" | ".join(names), artist, is_artist=True) or (
            identities_compatible(primary.get("name"), artist, is_artist=True) and all_extras_annotated
        )
    if not artist_matches:
        return False
    if identities_compatible(result.get("title"), title, is_artist=False):
        return True
    if not feature_credits or not identities_compatible(feature_title, result.get("title"), is_artist=False):
        return False
    observed = set()
    for name in names[1:]:
        observed |= bilingual_identity_variants(name, is_artist=True)
    observed.add(identity(" | ".join(names[1:])))
    for full_credit, split_parts in _expand_feature_credits(feature_credits):
        if bilingual_identity_variants(full_credit, is_artist=True) & observed:
            continue
        if not all(bool(bilingual_identity_variants(part, is_artist=True) & observed) for part in split_parts):
            return False
    return True


def ranking_recovery_priority(payload):
    """Recover leading ranks and shared memberships first without changing selection."""
    bindings = payload.get("chart_bindings", [])
    return (
        min((int(binding["position"]) for binding in bindings), default=10**9),
        -len({(binding["country_code"], int(binding["year"])) for binding in bindings}),
    )


def lrclib_text(row):
    """Use plain text, or a fully timestamped LRC body without inventing lines."""
    plain = row.get("plainLyrics")
    if isinstance(plain, str) and plain.strip():
        return plain.strip()
    synced = row.get("syncedLyrics")
    if not isinstance(synced, str) or not synced.strip():
        return None
    lines = []
    for line in synced.splitlines():
        if not line.strip():
            lines.append("")
            continue
        match = re.match(r"^(?:\[\d{1,3}:[0-5]\d(?:[.:]\d{1,3})?\])+\s?(.*)$", line)
        if not match:
            return None
        lines.append(match[1])
    return "\n".join(lines).strip() or None


def lrclib_text_signature(row):
    """Compare formatting only; retain order, punctuation, sections and repetitions."""
    value = lrclib_text(row)
    return normalize_text(value).normalized_hash if value is not None else None


def recovery_cache_sources(root, primary):
    """Include recent campaign caches in local reuse, preserving their raw evidence."""
    root = Path(root).resolve()
    recent = list((root / "data/runtime").glob("import-all-lyrics-*/acquisition/http-cache"))
    recent.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    quality = root / "data/derived/research_quality"
    paths = [
        *recent,
        Path(primary),
        *(root / "data/derived/lyrics").glob("*/http-cache"),
        *quality.glob("corpus-revision-*/*/http-cache"),
        *quality.glob("recovery-expanded-*/http-cache"),
        *(root / "data/derived/annual_revision").glob("*/acquisition/http-cache"),
    ]
    return tuple(
        dict.fromkeys(
            path.resolve()
            for path in paths
            if path.is_dir() and path.resolve().is_relative_to(root)
        )
    )


def reconcile_task_metadata(payload, display):
    """Keep retrieval history and require fresh matching when the native name changes."""
    if payload["recording_id"] != display["candidate_id"]:
        raise ValueError("native display proof belongs to another retrieval candidate")
    updated = dict(payload)
    changed = any(
        identity(payload.get(field)) != identity(display.get(field))
        for field in ("title", "artist")
    )
    if changed:
        history = list(payload.get("metadata_revision_history", []))
        history.append(
            {field: payload.get(field) for field in ("title", "artist", "metadata_resolution")}
        )
        updated.update(metadata_revision_history=history, requires_metadata_reconciliation=True)
    updated.update({field: display[field] for field in ("title", "artist", "metadata_resolution")})
    return updated


def reconcile_reindexed_task(previous, current):
    """Refresh selection bindings without discarding metadata reconciliation history."""
    if previous["recording_id"] != current["recording_id"]:
        raise ValueError("cannot merge different retrieval candidates")
    updated = dict(previous)
    updated.update(current)
    history = list(previous.get("metadata_revision_history", []))
    changed = any(
        identity(previous.get(field)) != identity(current.get(field))
        for field in ("title", "artist")
    )
    if changed:
        revision = {
            field: previous.get(field) for field in ("title", "artist", "metadata_resolution")
        }
        if not history or history[-1] != revision:
            history.append(revision)
        updated["previous_display_metadata"] = {
            field: previous.get(field) for field in ("title", "artist")
        }
    if history:
        updated["metadata_revision_history"] = history
    if changed or previous.get("requires_metadata_reconciliation"):
        updated["requires_metadata_reconciliation"] = True
    return updated


class AcquisitionStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.blobs = self.root / "texts"
        self.blobs.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(self.root / "acquisition.sqlite")
        self.conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS tasks(
                identity TEXT PRIMARY KEY, payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', result TEXT);
        """)
        self._scoped = False

    def set_scope(self, identities):
        self.conn.execute("CREATE TEMP TABLE IF NOT EXISTS task_scope(identity TEXT PRIMARY KEY)")
        with self.conn:
            self.conn.execute("DELETE FROM task_scope")
            self.conn.executemany(
                "INSERT OR IGNORE INTO task_scope VALUES (?)", ((key,) for key in identities)
            )
        self._scoped = True

    def enqueue(self, key, payload):
        self.conn.execute(
            "INSERT OR IGNORE INTO tasks(identity,payload) VALUES (?,?)",
            (key, json.dumps(payload, ensure_ascii=False)),
        )
        self.conn.commit()

    def claim(self, key):
        with self.conn:
            changed = self.conn.execute(
                "UPDATE tasks SET status='running' WHERE identity=? AND status='pending'", (key,)
            )
        return changed.rowcount == 1

    def finish(self, key, result):
        result = dict(result)
        value = result.pop("text", None)
        if value:
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
            path = self.blobs / f"{digest}.txt"
            if not path.exists():
                with path.open("x", encoding="utf-8", newline="") as handle:
                    handle.write(value)
            elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("stored text hash mismatch")
            result.update(text_sha256=digest, text_path=str(path), characters=len(value))
        result.update(
            identity_validated=False, completeness_validated=False, classification_ready=False
        )
        with self.conn:
            self.conn.execute(
                "UPDATE tasks SET status=?,result=? WHERE identity=?",
                (result["status"], json.dumps(result, ensure_ascii=False), key),
            )

    def summary(self):
        if self._scoped:
            return dict(
                self.conn.execute(
                    "SELECT t.status,count(*) FROM tasks t "
                    "JOIN task_scope s ON s.identity=t.identity GROUP BY t.status"
                )
            )
        return dict(self.conn.execute("SELECT status,count(*) FROM tasks GROUP BY status"))


class PacedHTTP(CachedRecoveryHTTP):
    """Cache successes and 404s; pause a domain after access or rate-limit failures."""

    def __init__(
        self,
        cache,
        client,
        cache_sources=(),
        *,
        search_cache_max_age_seconds=None,
        cooldown_path=None,
        interval=0.5,
    ):
        # The scheduler owns provider retries and observes the complete Retry-After.
        if interval <= 0:
            raise ValueError("request interval must be positive")
        super().__init__(cache, client, interval=interval, attempts=1)
        self.cache_sources = tuple(Path(path) for path in cache_sources if Path(path).is_dir())
        if search_cache_max_age_seconds is not None and search_cache_max_age_seconds <= 0:
            raise ValueError("search cache age must be positive")
        self.search_cache_max_age_seconds = search_cache_max_age_seconds
        self._reuse_guard = threading.Lock()
        self._blocked_until = {}
        self._negative = set()
        self._domain_guard = threading.Lock()
        self._cooldown_path = (
            Path(cooldown_path) if cooldown_path else self.cache / "provider-cooldowns.sqlite"
        )
        with closing(sqlite3.connect(self._cooldown_path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS provider_cooldowns("
                "domain TEXT PRIMARY KEY,until_epoch REAL NOT NULL)"
            )
            now, monotonic = time.time(), time.monotonic()
            for domain, until in db.execute("SELECT domain,until_epoch FROM provider_cooldowns"):
                if not isinstance(domain, str) or not math.isfinite(float(until)):
                    raise ValueError("invalid persisted provider cooldown")
                if until > now:
                    self._blocked_until[domain] = monotonic + (until - now)

    def search_retry_delay(self, domains=("lrclib.net", "genius.com")):
        """Wait only when all providers used by the worker are paused."""
        if not domains:
            raise ValueError("at least one provider is required")
        now = time.monotonic()
        with self._domain_guard:
            return max(
                0,
                min(self._blocked_until.get(domain, 0) - now for domain in domains),
            )

    def provider_retry_delays(self):
        now = time.monotonic()
        with self._domain_guard:
            return {
                domain: round(until - now, 1)
                for domain, until in self._blocked_until.items()
                if until > now
            }

    def _pause_domain(self, domain, response):
        duration = 900 if response.status_code in (401, 403, 429) else 60
        retry_after = response.headers.get("retry-after", "")
        try:
            delay = int(retry_after)
        except ValueError:
            try:
                date = parsedate_to_datetime(retry_after)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=UTC)
                delay = (date - datetime.now(UTC)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                delay = 0
        self._blocked_until[domain] = max(
            self._blocked_until.get(domain, 0), time.monotonic() + max(duration, delay)
        )
        until_epoch = time.time() + self._blocked_until[domain] - time.monotonic()
        with closing(sqlite3.connect(self._cooldown_path)) as db, db:
            db.execute(
                "INSERT INTO provider_cooldowns VALUES (?,?) "
                "ON CONFLICT(domain) DO UPDATE SET until_epoch="
                "MAX(provider_cooldowns.until_epoch,excluded.until_epoch)",
                (domain, until_epoch),
            )

    def _borrowable(self, path, url):
        parsed = urlparse(url)
        search = (parsed.hostname, parsed.path) in {
            ("lrclib.net", "/api/search"),
            ("genius.com", "/api/search/multi"),
        }
        if not search or self.search_cache_max_age_seconds is None:
            return True
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            retrieved = datetime.fromisoformat(saved["retrieved_at"])
            return retrieved.tzinfo is not None and (
                0
                <= (datetime.now(UTC) - retrieved).total_seconds()
                <= self.search_cache_max_age_seconds
            )
        except (ValueError, TypeError, KeyError):
            return False

    def get(self, url, **kwargs):
        request = self.client.build_request("GET", url, **kwargs)
        domain, key = urlparse(str(request.url)).netloc, str(request.url)
        cached_path = self.cache / f"{hashlib.sha256(key.encode()).hexdigest()}.json"
        with self._reuse_guard:
            if not cached_path.exists():
                for directory in self.cache_sources:
                    previous = directory / cached_path.name
                    if previous.exists() and self._borrowable(previous, key):
                        try:
                            cached_path.hardlink_to(previous)
                        except OSError:
                            shutil.copy2(previous, cached_path)
                        break
        with self._domain_guard:
            paused = self._blocked_until.get(domain, 0) > time.monotonic()
            if key in self._negative:
                return httpx.Response(404, request=request)
        if paused:
            # A provider pause prevents network access, not local verified replay.
            try:
                cached = json.loads(cached_path.read_text(encoding="utf-8"))
                raw = (
                    base64.b64decode(cached["body_base64"], validate=True)
                    if "body_base64" in cached
                    else cached["body"].encode("utf-8")
                )
                if hashlib.sha256(raw).hexdigest() != cached["body_sha256"]:
                    raise ValueError("cached response hash mismatch")
                response = httpx.Response(
                    200,
                    content=raw,
                    headers={"content-type": cached.get("content_type") or "text/plain"},
                    request=httpx.Request("GET", cached.get("final_url", key)),
                )
                response.encoding = cached.get("encoding") or "utf-8"
                self.trace.append(
                    dict(
                        url=key,
                        status=200,
                        cache_path=str(cached_path),
                        body_sha256=cached["body_sha256"],
                        cached=True,
                        raw_bytes_preserved=True,
                        provider_paused=True,
                    )
                )
                return response
            except (OSError, ValueError, KeyError, TypeError):
                self.trace.append(dict(url=key, status=429, provider_paused=True))
                return httpx.Response(429, request=request)
        response = super().get(url, **kwargs)
        azlyrics_challenge = (
            response.status_code == 200
            and domain.endswith("azlyrics.com")
            and "AZLyrics - request for access" in response.text[:2000]
        )
        with self._domain_guard:
            if (
                response.status_code in (202, 401, 403, 429, 500, 502, 503, 504)
                or azlyrics_challenge
            ):
                self._pause_domain(domain, response)
            if response.status_code == 404:
                self._negative.add(key)
        if azlyrics_challenge:
            cached_path.unlink(missing_ok=True)
            return httpx.Response(429, request=request)
        return response


def structured_identity(page, title, artist, allowed_artists=()):
    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            yield value
            # Recommendations, album tracks and mentions do not identify this page's lyric.
            for field in ("@graph", "mainEntity", "mainEntityOfPage"):
                item = value.get(field)
                if isinstance(item, (dict, list)):
                    yield from walk(item)

    recordings, entities, primary_refs = [], [], []
    for script in page.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        for item in walk(data):
            entities.append(item)
            primary = item.get("mainEntity")
            if primary is not None:
                primary_refs.extend(primary if isinstance(primary, list) else [primary])
            kinds = item.get("@type", [])
            if isinstance(kinds, str):
                kinds = [kinds]
            if not isinstance(kinds, list):
                continue
            if item not in recordings and any(
                kind in {"MusicRecording", "MusicComposition", "Song"}
                for kind in kinds
                if isinstance(kind, str)
            ):
                recordings.append(item)
    if primary_refs:
        # A page may contain recommended songs; follow its explicit primary binding.
        selected = []
        for ref in primary_refs:
            if isinstance(ref, dict) and ref in recordings:
                matches = [ref]
            else:
                ref_id = ref.get("@id") if isinstance(ref, dict) else ref
                matches = [
                    entity
                    for entity in entities
                    if isinstance(ref_id, str)
                    and ref_id
                    and entity.get("@id") == ref_id
                    and entity in recordings
                ]
            if len(matches) != 1:
                return False
            if matches[0] not in selected:
                selected.append(matches[0])
        recordings = selected
    # Unbound graphs containing several songs are ambiguous.
    if len(recordings) != 1:
        return False
    for item in recordings:
        credited = item.get("byArtist") or item.get("recordedBy")
        credited = credited if isinstance(credited, list) else [credited]
        names = [v.get("name", "") if isinstance(v, dict) else str(v or "") for v in credited]
        observed = [name for name in names if name]
        allowed = [name for name in allowed_artists if name]
        artists_match = (
            identities_compatible(" | ".join(names), artist, is_artist=True)
            or (len(observed) == 1 and identities_compatible(observed[0], artist, is_artist=True))
            or (
                bool(allowed)
                and any(identities_compatible(artist, name, is_artist=True) for name in observed)
                and all(
                    any(identities_compatible(name, allow, is_artist=True) for allow in allowed)
                    for name in observed
                )
            )
        )
        if identities_compatible(str(item.get("name", "")), title, is_artist=False) and artists_match:
            return True
    return False


def decode_js_json_literal(literal):
    """Decode a single-quoted JS JSON string without evaluating code."""
    raw, encoded, index = literal[1:-1], [], 0
    while index < len(raw):
        char = raw[index]
        index += 1
        if char != "\\":
            encoded.append('\\"' if char == '"' else char)
            continue
        if index == len(raw):
            raise ValueError("unfinished JavaScript escape")
        char = raw[index]
        index += 1
        if char in '\\"/bfnrtu':
            encoded.append("\\" + char)
        elif char == "x":
            digits = raw[index : index + 2]
            if not re.fullmatch(r"[0-9a-fA-F]{2}", digits):
                raise ValueError("invalid hex escape")
            encoded.append("\\u00" + digits)
            index += 2
        elif char == "v":
            encoded.append("\\u000b")
        elif char == "0":
            if index < len(raw) and raw[index].isdigit():
                raise ValueError("legacy octal escape is not supported")
            encoded.append("\\u0000")
        elif char in "\n\r":
            if char == "\r" and raw[index : index + 1] == "\n":
                index += 1
        elif char.isdigit():
            raise ValueError("legacy numeric escape is not supported")
        else:
            # JavaScript NonEscapeCharacter consumes the slash (e.g. \$ or \').
            encoded.append(char)
    return json.loads(json.loads('"' + "".join(encoded) + '"'))


def _genius_person_record(person, artists):
    record = person if isinstance(person, dict) else artists[str(person)]
    if not isinstance(record, dict) or not isinstance(record.get("name"), str) or not record["name"].strip():
        raise KeyError("missing artist record")
    return {"id": record.get("id"), "name": record["name"]}


def extract_genius_preloaded_credits(page):
    """Extract canonical songPage credits from Genius embedded state when bound to og:url."""
    canonical = page.select_one('meta[property="og:url"]')
    if not canonical or not canonical.get("content"):
        return None
    for script in page.find_all("script"):
        raw = script.string or script.get_text()
        if len(raw) > 2_000_000:
            continue
        match = re.search(
            r"window\.__PRELOADED_STATE__\s*=\s*JSON\.parse\(('(?:\\.|[^'\\])*')\)", raw
        )
        if not match:
            continue
        try:
            state = decode_js_json_literal(match[1])
            song_id = state.get("songPage", {}).get("song")
            if (
                state.get("currentPage") != "songPage"
                or not isinstance(song_id, int)
                or isinstance(song_id, bool)
                or song_id <= 0
            ):
                continue
            entities = state["entities"]
            song = entities["songs"][str(song_id)]
            if song.get("id") != song_id or song.get("lyricsState") not in (None, "complete"):
                continue
            url = song.get("url")
            parsed = urlparse(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "genius.com"
                or parsed.username
                or canonical.get("content") != url
            ):
                continue
            artists_map = entities["artists"]
            primary_artists = [_genius_person_record(p, artists_map) for p in song.get("primaryArtists", []) or []]
            featured_artists = [_genius_person_record(p, artists_map) for p in song.get("featuredArtists", []) or []]
            if not primary_artists and not featured_artists:
                continue
            supporting = {}
            for src_key, dst_key in (
                ("producerArtists", "producer_artists"),
                ("writerArtists", "writer_artists"),
            ):
                items = []
                for person in song.get(src_key, []) or []:
                    try:
                        items.append(_genius_person_record(person, artists_map))
                    except (KeyError, TypeError, AttributeError):
                        continue
                supporting[dst_key] = items
            lead = song.get("primaryArtist")
            primary_artist = (
                _genius_person_record(lead, artists_map)
                if isinstance(lead, (dict, int, str)) and lead
                else (primary_artists[0] if primary_artists else featured_artists[0])
            )
            return {
                "song_id": song_id,
                "title": song.get("title"),
                "url": url,
                "lyrics_state": song.get("lyricsState"),
                "primary_artist": primary_artist,
                "primary_artists": primary_artists,
                "featured_artists": featured_artists,
                "performer_credit_fields_explicit": True,
                **supporting,
            }
        except (ValueError, TypeError, KeyError, AttributeError, SyntaxError, RecursionError):
            continue
    return None


def genius_main_entity_identity(page, title, artist, allowed_artists, song_id):
    """Bind current songPage only to an already matched provider song ID."""
    if not isinstance(song_id, int) or isinstance(song_id, bool) or song_id <= 0:
        return False
    credits = extract_genius_preloaded_credits(page)
    if not credits or credits.get("song_id") != song_id:
        return False
    if not identities_compatible(credits.get("title"), title, is_artist=False):
        return False
    names = [p["name"] for p in credits["primary_artists"] + credits["featured_artists"]]
    allowed = [name for name in allowed_artists if name]
    return bool(
        names
        and allowed
        and any(identities_compatible(artist, name, is_artist=True) for name in names)
        and all(
            any(identities_compatible(name, allow, is_artist=True) for allow in allowed)
            for name in names
        )
    )


def extract_html(html, source, title, artist, allowed_artists=(), *, provider_song_id=None):
    page = BeautifulSoup(html, "html.parser")
    matched = structured_identity(page, title, artist, allowed_artists)
    if source == "GENIUS" and not matched:
        matched = genius_main_entity_identity(
            page, title, artist, allowed_artists, provider_song_id
        )
    if source == "AZLYRICS" and page.title:
        heading = page.title.get_text(" ", strip=True)
        match = re.match(r"(.+?)\s+-\s+(.+?)\s+Lyrics\s*\|", heading, re.I)
        matched = bool(
            match
            and identity(match[1]) == identity(artist)
            and identity(match[2].strip('"')) == identity(title)
        )
    if not matched:
        return None
    selectors = {
        "GENIUS": '[data-lyrics-container="true"], div.lyrics',
        "LETRAS": ".lyric-original, .cnt-letra",
        "MUSIXMATCH": '[data-testid="lyrics-body-text"], .mxm-lyrics__content',
    }
    if source == "AZLYRICS":
        main = page.select_one(".col-lg-8.text-center")
        nodes = (
            [
                node
                for node in main.find_all("div", recursive=False)
                if not node.get("class") and not node.get("id") and len(node.find_all("br")) > 2
            ]
            if main
            else []
        )
        if len(nodes) != 1:
            return None
    else:
        nodes = outer_lyric_containers(list(page.select(selectors[source])))
    if not nodes:
        return None
    return "\n\n".join(html_lyric_text(node) for node in nodes).strip()


def candidate(text, source, **metadata):
    if not isinstance(text, str) or not text or has_partial_lyrics_notice(text):
        return None
    derivative = prepare_lyric_derivative(text, source)
    return dict(
        status="candidate_pending_validation",
        text=text,
        source=source,
        text_quality_flags=list(derivative.flags),
        source_metadata=metadata,
        identity_check="exact_source_metadata",
        generated_by_ai=False,
    )


def fetch_candidate(title, artist, http, *, html_sources=None, expected_duration_ms=None):
    """Try one source at a time; never replace a failed version with the base song."""
    http.start_trace()
    if (
        not isinstance(title, str)
        or not title.strip()
        or not isinstance(artist, str)
        or not artist.strip()
    ):
        return dict(
            status="metadata_missing", source_errors=["title_or_artist_missing"], http_evidence=[]
        )
    primary_artist = artist.split("|", 1)[0].strip()
    errors = []
    try:
        response = http.get(
            "https://lrclib.net/api/search",
            params={"track_name": title, "artist_name": primary_artist},
        )
        if response.status_code == 200:
            rows = response.json()
            exact = (
                [
                    row
                    for row in rows
                    if isinstance(row, dict)
                    and identity(str(row.get("trackName", ""))) == identity(title)
                    and identity(str(row.get("artistName", ""))) == identity(artist)
                    and not row.get("instrumental")
                    and not recording_duration_mismatch(expected_duration_ms, row.get("duration"))
                    and lrclib_text(row)
                ]
                if isinstance(rows, list)
                else []
            )
            texts = {lrclib_text_signature(row) for row in exact}
            if len(texts) == 1:
                result = candidate(
                    lrclib_text(exact[0]),
                    "LRCLIB",
                    id=exact[0].get("id"),
                    duration_seconds=exact[0].get("duration"),
                    observed_title=exact[0].get("trackName"),
                    observed_artist=exact[0].get("artistName"),
                    requested_artist=artist,
                    lyric_representation="plain"
                    if exact[0].get("plainLyrics")
                    else "timestamped_lrc",
                    full_requested_artist_credit_matched=True,
                    comparison_normalization_version=NORMALIZATION_VERSION,
                    equivalent_provider_records=[row.get("id") for row in exact],
                )
                if result:
                    return {**result, "http_evidence": list(http.trace)}
            if len(texts) > 1:
                errors.append("divergent_exact_lrclib_editions")
    except (httpx.HTTPError, ValueError) as exc:
        errors.append(type(exc).__name__)
    slug_artist, slug_title = _slugify_letras(primary_artist), _slugify_letras(title)
    az_artist = re.sub(r"[^a-z0-9]", "", slug_artist)
    az_title = re.sub(r"[^a-z0-9]", "", slug_title)
    pages = [
        ("GENIUS", f"https://genius.com/{_slugify(primary_artist)}-{_slugify(title)}-lyrics"),
        ("LETRAS", f"https://www.letras.mus.br/{slug_artist}/{slug_title}/"),
        ("AZLYRICS", f"https://www.azlyrics.com/lyrics/{az_artist}/{az_title}.html"),
        ("MUSIXMATCH", f"https://www.musixmatch.com/lyrics/{slug_artist}/{slug_title}"),
    ]
    for source, url in pages:
        if html_sources is not None and source not in html_sources:
            continue
        try:
            response = http.get(url)
            if response.status_code != 200:
                errors.append(f"{source}:{response.status_code}")
                continue
            preloaded = (
                extract_genius_preloaded_credits(BeautifulSoup(response.text, "html.parser"))
                if source == "GENIUS"
                else None
            )
            if preloaded and match_genius_identity(title, artist, preloaded):
                allowed = [
                    person["name"]
                    for person in preloaded["primary_artists"] + preloaded["featured_artists"]
                ]
                observed_title = preloaded["title"]
                observed_artist = preloaded["primary_artist"]["name"]
                text = extract_html(
                    response.text,
                    source,
                    observed_title,
                    observed_artist,
                    allowed,
                    provider_song_id=preloaded["song_id"],
                )
                metadata = dict(
                    url=str(response.url),
                    observed_title=observed_title,
                    observed_artist=observed_artist,
                    requested_artist=artist,
                    full_requested_artist_credit_matched=True,
                    provider_credit_evidence=preloaded,
                    page_identity_scope="main_entity_only",
                )
            else:
                text = extract_html(response.text, source, title, primary_artist)
                metadata = dict(
                    url=str(response.url),
                    observed_title=title,
                    observed_artist=primary_artist,
                    requested_artist=artist,
                    full_requested_artist_credit_matched=identities_compatible(
                        primary_artist, artist, is_artist=True
                    ),
                    page_identity_scope="exact_page_title"
                    if source == "AZLYRICS"
                    else "main_entity_only",
                )
            result = candidate(text, source, **metadata)
            if result:
                if not metadata["full_requested_artist_credit_matched"]:
                    result["text_quality_flags"].append(
                        "requested_collaboration_credits_unverified"
                    )
                return {
                    **result,
                    "http_evidence": list(http.trace),
                    "quarantined_source": source == "LETRAS",
                }
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"{source}:{type(exc).__name__}")
    return dict(
        status="not_found_or_unverified", source_errors=errors, http_evidence=list(http.trace)
    )
