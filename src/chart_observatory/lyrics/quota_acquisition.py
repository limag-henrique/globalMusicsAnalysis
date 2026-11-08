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


def identity(value):
    # Preserve remix/live/clean/explicit qualifiers and featured performers.
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    words = " ".join(re.sub(r"[^\w]+", " ", normalized).split())
    return words or normalized


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
    ):
        # The scheduler owns provider retries and observes the complete Retry-After.
        super().__init__(cache, client, interval=0.5, attempts=1)
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
        with self._domain_guard:
            if response.status_code in (401, 403, 429, 500, 502, 503, 504):
                self._pause_domain(domain, response)
            if response.status_code == 404:
                self._negative.add(key)
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
        observed = {identity(name) for name in names if name}
        allowed = {identity(name) for name in allowed_artists if name}
        artists_match = identity(" | ".join(names)) == identity(artist) or (
            bool(allowed) and identity(artist) in observed and observed.issubset(allowed)
        )
        if identity(str(item.get("name", ""))) == identity(title) and artists_match:
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


def genius_main_entity_identity(page, title, artist, allowed_artists, song_id):
    """Bind current songPage only to an already matched provider song ID."""
    if not isinstance(song_id, int) or isinstance(song_id, bool) or song_id <= 0:
        return False
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
            if (
                state.get("currentPage") != "songPage"
                or state.get("songPage", {}).get("song") != song_id
            ):
                continue
            entities = state["entities"]
            song = entities["songs"][str(song_id)]
            if song.get("id") != song_id or identity(song.get("title")) != identity(title):
                continue
            if song.get("lyricsState") not in (None, "complete"):
                continue
            url = song.get("url")
            parsed = urlparse(url)
            canonical = page.select_one('meta[property="og:url"]')
            if (
                parsed.scheme != "https"
                or parsed.hostname != "genius.com"
                or parsed.username
                or not canonical
                or canonical.get("content") != url
            ):
                continue
            ids = song.get("primaryArtists", []) + song.get("featuredArtists", [])
            if not ids:
                continue
            names = []
            for person in ids:
                record = person if isinstance(person, dict) else entities["artists"][str(person)]
                names.append(record["name"])
            observed = {identity(name) for name in names}
            allowed = {identity(name) for name in allowed_artists if name}
            if identity(artist) in observed and observed.issubset(allowed):
                return True
        except (ValueError, TypeError, KeyError, AttributeError, SyntaxError, RecursionError):
            continue
    return False


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
            text = extract_html(response.text, source, title, primary_artist)
            result = candidate(
                text,
                source,
                url=str(response.url),
                observed_title=title,
                observed_artist=primary_artist,
                requested_artist=artist,
                full_requested_artist_credit_matched=identity(primary_artist) == identity(artist),
                page_identity_scope="exact_page_title"
                if source == "AZLYRICS"
                else "main_entity_only",
            )
            if result:
                if identity(primary_artist) != identity(artist):
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
