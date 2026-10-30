"""Cached conventional HTTP acquisition; retrieved text still requires validation."""

from __future__ import annotations

import base64
import errno
import hashlib
import json
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from shutil import disk_usage
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

from chart_observatory.lyrics.gemini_pipeline import LrclibClient
from chart_observatory.lyrics.genius_client import GeniusClient
from chart_observatory.lyrics.text_quality import prepare_lyric_derivative

MIN_FREE_CACHE_BYTES = 1024 ** 3


class CachedRecoveryHTTP:
    """Serialize starts per domain; retain successful raw responses for replay."""

    def __init__(self, cache: Path, client: httpx.Client, interval: float = 0.3):
        self.cache, self.client, self.interval = cache, client, interval
        self.cache.mkdir(parents=True, exist_ok=True)
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self._pace_locks: dict[str, threading.Lock] = {}
        self._slots: dict[str, threading.BoundedSemaphore] = {}
        self._last: dict[str, float] = {}
        self._local = threading.local()

    def start_trace(self) -> None:
        self._local.trace = []

    @property
    def trace(self) -> list[dict[str, Any]]:
        if not hasattr(self._local, "trace"):
            self.start_trace()
        trace: list[dict[str, Any]] = self._local.trace
        return trace

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        request = self.client.build_request("GET", url, **kwargs)
        key = hashlib.sha256(str(request.url).encode()).hexdigest()
        path = self.cache / f"{key}.json"
        domain = urlparse(str(request.url)).netloc
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
            pace_lock = self._pace_locks.setdefault(domain, threading.Lock())
            slots = self._slots.setdefault(domain, threading.BoundedSemaphore(2))
        with lock:
            if path.exists():
                try:
                    cached = json.loads(path.read_text(encoding="utf-8"))
                    original = (base64.b64decode(cached["body_base64"], validate=True)
                                if "body_base64" in cached else cached["body"].encode("utf-8"))
                    raw_preserved = hashlib.sha256(original).hexdigest() == cached["body_sha256"]
                    if not raw_preserved and ("body_base64" in cached
                                              or cached.get("cache_schema_version") == 2):
                            raise ValueError("cached original response hash mismatch")
                    if raw_preserved:
                        response = httpx.Response(
                            200, content=original,
                            headers={"content-type": cached.get("content_type") or "text/plain"},
                            request=httpx.Request("GET", cached.get("final_url", str(request.url))),
                        )
                        response.encoding = cached.get("encoding") or "utf-8"
                    else:
                        response = httpx.Response(200, text=cached["body"], request=request)
                    self.trace.append({
                        "url": str(request.url), "status": 200, "cache_path": str(path),
                        "body_sha256": cached["body_sha256"], "cached": True,
                        "raw_bytes_preserved": raw_preserved,
                    })
                    return response
                except (ValueError, KeyError, TypeError):
                    path.rename(path.with_suffix(f".interrupted-{uuid4()}"))
            if disk_usage(self.cache).free < MIN_FREE_CACHE_BYTES:
                raise OSError(errno.ENOSPC, "recovery paused: less than 1 GiB free on cache volume")
            for attempt in range(3):
                try:
                    with slots:
                        with pace_lock:
                            elapsed = time.monotonic() - self._last.get(domain, 0)
                            time.sleep(max(0, self.interval - elapsed))
                            self._last[domain] = time.monotonic()
                        response = self.client.send(request, follow_redirects=True)
                except httpx.HTTPError:
                    if attempt == 2:
                        self.trace.append({"url": str(request.url), "status": None})
                        raise
                    time.sleep(2 ** attempt)
                    continue
                if response.status_code == 200:
                    temporary = path.with_suffix(".tmp")
                    cache_record = {
                        "url": str(request.url), "final_url": str(response.url),
                        "retrieved_at": datetime.now(UTC).isoformat(), "body": response.text,
                        "body_sha256": hashlib.sha256(response.content).hexdigest(),
                        "encoding": response.encoding,
                        "content_type": response.headers.get("content-type"),
                        "cache_schema_version": 2,
                    }
                    # UTF-8 text plus its verified byte hash reconstructs the exact
                    # response without a second full copy. Other encodings need bytes.
                    if response.text.encode("utf-8") != response.content:
                        cache_record["body_base64"] = base64.b64encode(
                            response.content).decode("ascii")
                    payload = json.dumps(cache_record, ensure_ascii=False).encode("utf-8")
                    if disk_usage(self.cache).free < MIN_FREE_CACHE_BYTES + 2 * len(payload):
                        raise OSError(errno.ENOSPC, "recovery paused before cache write")
                    temporary.write_bytes(payload)
                    temporary.replace(path)
                    self.trace.append({
                        "url": str(request.url), "status": 200, "cache_path": str(path),
                        "body_sha256": hashlib.sha256(response.content).hexdigest(),
                        "cached": False,
                        "raw_bytes_preserved": True,
                    })
                    return response
                if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                    self.trace.append({"url": str(request.url), "status": response.status_code})
                    return response
                try:
                    header = response.headers.get("Retry-After", 2 ** attempt)
                    delay = min(30, max(1, float(header)))
                except ValueError:
                    delay = 2 ** attempt
                time.sleep(delay)
        raise RuntimeError("unreachable HTTP retry state")


def _words(value: str) -> list[str]:
    return re.findall(r"\w+", re.sub(r"\[[^\]]*\]", "", value).casefold())


def discover_google_sources(
    title: str, artist: str, http: CachedRecoveryHTTP,
) -> list[dict[str, str]]:
    """Discover page URLs only; neither snippets nor AI overviews become lyrics."""
    response = http.get("https://www.google.com/search", params={
        "q": f'"{title}" "{artist}" lyrics official', "num": 5,
    })
    if response.status_code != 200:
        return []
    sources: list[dict[str, str]] = []
    seen = set()
    for link in BeautifulSoup(response.text, "html.parser").select("a[href]"):
        heading = link.find("h3")
        if heading is None:
            continue
        url = str(link.get("href", ""))
        parsed = urlparse(url)
        if parsed.path == "/url":
            query = parse_qs(parsed.query)
            url = (query.get("q") or query.get("url") or [""])[0]
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https" or not host or host == "google.com"
            or host.endswith(".google.com") or url in seen
        ):
            continue
        seen.add(url)
        sources.append({"url": url, "title": heading.get_text(" ", strip=True),
                        "verification": "unverified"})
    return sources


def recover_candidate(
    title: str, artist: str, http: CachedRecoveryHTTP, *, collect_all: bool = False,
    discover_google: bool = False,
) -> dict[str, Any]:
    """Keep conventional provider candidates separate; agreement is not validation."""
    errors = []
    variants: list[dict[str, Any]] = []
    http.start_trace()
    discovered = []
    if discover_google:
        try:
            discovered = discover_google_sources(title, artist, http)
        except httpx.HTTPError as exc:
            errors.append({"source": "GOOGLE_DISCOVERY", "error_type": type(exc).__name__})

    def add_variant(value: str, source: str, metadata: dict[str, Any]) -> None:
        derivative = prepare_lyric_derivative(value, source)
        variants.append({
            "source": source, "source_metadata": metadata, "text": derivative.text,
            "lyrics_hash": derivative.derivative_sha256, "signals": list(derivative.flags),
            "original_text_sha256": derivative.original_sha256,
            "derivative_version": derivative.version,
            "transformations": list(derivative.transformations),
            "extraction_method": "conventional_api_or_html",
            "http_evidence": list(http.trace),
        })

    try:
        result = LrclibClient(http_client=http).fetch(title, artist)
    except httpx.HTTPError as exc:
        errors.append({"source": "LRCLIB", "error_type": type(exc).__name__})
        result = None
    if result:
        value, metadata = result
        add_variant(value, "LRCLIB", metadata)
    if collect_all or not variants:
        scraped = GeniusClient(http_client=http).fetch(title, artist)
        if scraped:
            add_variant(scraped, "GENIUS", {})
    if not variants:
        unavailable = errors or any(row["status"] in {None, 429, 503} for row in http.trace)
        return {"status": "http_error" if unavailable else "not_found", "title": title,
                "artist": artist, "source_errors": errors, "http_evidence": http.trace,
                "discovered_sources": discovered,
                "lookup_mode": "all_sources" if collect_all else "first_source"}
    return {
        **variants[0],
        "status": "candidate_pending_validation", "title": title, "artist": artist,
        "variants": variants,
        "cross_source_text_agreement": (
            all(_words(row["text"]) == _words(variants[0]["text"]) for row in variants[1:])
            if len(variants) > 1 else None
        ),
        "lookup_mode": "all_sources" if collect_all else "first_source",
        "discovered_sources": discovered,
        "identity_validated": False, "completeness_validated": False,
        "generated_by_ai": False, "retrieved_at": datetime.now(UTC).isoformat(),
        "source_errors": errors,
        "http_evidence": http.trace,
    }
