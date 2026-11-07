"""Genius lyrics scraper — API-free HTML scraping with optional API token support."""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from bs4 import BeautifulSoup

from chart_observatory.lyrics.text_quality import html_lyric_text, outer_lyric_containers

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug (Genius-style)."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[&]", "-and-", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text.title()


class GeniusClient:
    """Scrape lyrics from Genius.com using search + page scraping.

    If a ``GENIUS_ACCESS_TOKEN`` is provided, uses the official search API for
    higher accuracy. Otherwise, falls back to the public search page scraping.
    """

    def __init__(
        self,
        access_token: str | None = None,
        http_client: Any | None = None,
    ) -> None:
        self._token = access_token
        self._http = http_client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers=_HEADERS,
        )

    # -- public API -----------------------------------------------------------

    def fetch(self, title: str, artist: str) -> str | None:
        """Try to find lyrics for a song. Returns cleaned lyrics text or None."""
        if not title.strip() or not artist.strip():
            return None
        # Strategy 1: Direct URL construction (fastest)
        lyrics = self._try_direct_url(title, artist)
        if lyrics:
            return lyrics

        # Strategy 2: API search (if token available)
        if self._token:
            lyrics = self._try_api_search(title, artist)
            if lyrics:
                return lyrics

        # Strategy 3: Site search scraping
        lyrics = self._try_site_search(title, artist)
        return lyrics

    # -- strategy helpers -----------------------------------------------------

    def _try_direct_url(self, title: str, artist: str) -> str | None:
        """Construct the canonical Genius URL and try to scrape it."""
        clean_title = re.sub(
            r"\s*[\[(]\s*(?:feat\.?|ft\.?|featuring)\b.*?[\])]", "", title, flags=re.I
        )
        slug = f"{_slugify(artist.strip())}-{_slugify(clean_title.strip())}-lyrics"
        return self._scrape_lyrics_page(f"https://genius.com/{slug}", title, artist)

    def _try_api_search(self, title: str, artist: str) -> str | None:
        """Search the official API and require exact page identity."""
        if not self._token:
            return None
        primary_artist = artist.strip()
        query = f"{primary_artist} {title}"
        try:
            resp = self._http.get(
                "https://api.genius.com/search",
                params={"q": query},
                headers={"Authorization": f"Bearer {self._token}"},
            )
            if resp.status_code in (401, 403):
                self._token = None
            if resp.status_code != 200:
                return None
            data = resp.json()
        except (httpx.HTTPError, httpx.TimeoutException, ValueError):
            return None

        hits = data.get("response", {}).get("hits", [])
        if not hits:
            return None

        for hit in hits[:8]:
            lyrics = self._scrape_search_result(hit.get("result", {}), title, artist)
            if lyrics:
                return lyrics
        return None

    def _try_site_search(self, title: str, artist: str) -> str | None:
        """Search the public endpoint and require exact page identity."""
        primary_artist = artist.strip()
        query = f"{primary_artist} {title}"
        search_url = f"https://genius.com/api/search/multi?per_page=5&q={quote(query)}"

        try:
            resp = self._http.get(search_url)
            if resp.status_code != 200:
                return None
            data = resp.json()
        except (httpx.HTTPError, httpx.TimeoutException, ValueError):
            return None

        sections = data.get("response", {}).get("sections", [])
        for section in sections:
            if section.get("type") != "song":
                continue
            for hit in section.get("hits", [])[:5]:
                lyrics = self._scrape_search_result(hit.get("result", {}), title, artist)
                if lyrics:
                    return lyrics
        return None

    def _scrape_search_result(self, result: dict, title: str, artist: str) -> str | None:
        from chart_observatory.lyrics.quota_acquisition import identity
        from chart_observatory.lyrics.quota_discovery import (
            match_genius_identity,
            split_feature_credits,
        )

        if not isinstance(result, dict):
            return None
        if not match_genius_identity(title, artist, result):
            primary = result.get("primary_artist") or {}
            song_id = result.get("id")
            if (
                not isinstance(primary, dict)
                or identity(primary.get("name"))
                not in {identity(name) for name in artist.split("|")}
                or identity(result.get("title"))
                not in {identity(title), identity(split_feature_credits(title)[0])}
                or not isinstance(song_id, int)
                or isinstance(song_id, bool)
                or song_id <= 0
            ):
                return None
            try:
                response = self._http.get(f"https://genius.com/api/songs/{song_id}")
                if response.status_code != 200:
                    return None
                detailed = response.json().get("response", {}).get("song", {})
            except (httpx.HTTPError, ValueError, AttributeError):
                return None
            if (
                not isinstance(detailed, dict)
                or detailed.get("id") != song_id
                or not match_genius_identity(title, artist, detailed)
            ):
                return None
            result = detailed
        if result.get("lyrics_state") not in (None, "complete"):
            return None
        return self._scrape_lyrics_page(result.get("url", ""), title, artist, result)

    def _scrape_lyrics_page(
        self, url: str, title: str, artist: str, result: dict | None = None
    ) -> str | None:
        """Extract text only after verifying the page's song and performer identity."""
        from chart_observatory.lyrics.quota_acquisition import (
            genius_main_entity_identity,
            structured_identity,
        )
        from chart_observatory.lyrics.quota_discovery import genius_performer_names

        if not isinstance(url, str):
            return None
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "genius.com":
            return None
        try:
            resp = self._http.get(url)
            if resp.status_code != 200:
                return None
            page = BeautifulSoup(resp.text, "html.parser")
            expected_title, expected_artist, performers = title, artist, []
            if result is not None:
                expected_title = result.get("title", "")
                expected_artist = (result.get("primary_artist") or {}).get("name", "")
                performers = genius_performer_names(result)
            verified = structured_identity(page, expected_title, expected_artist, performers)
            if not verified and result is not None:
                verified = genius_main_entity_identity(
                    page, expected_title, expected_artist, performers, result.get("id")
                )
            if not verified:
                return None
            return self._extract_lyrics_from_html(resp.text, expected_title)
        except (httpx.HTTPError, httpx.TimeoutException):
            return None

    def _extract_lyrics_from_html(self, html: str, title: str = "") -> str | None:
        """Extract lyrics text from a Genius page HTML string."""
        # Find all lyrics containers
        page = BeautifulSoup(html, "html.parser")
        containers = page.select('[data-lyrics-container="true"]')
        if not containers:
            containers = page.select("div.lyrics")

        if not containers:
            return None

        lines: list[str] = []
        for container in outer_lyric_containers(list(containers)):
            text = html_lyric_text(container)
            if text:
                lines.append(text)

        full_lyrics = "\n".join(lines).strip()

        # Remove only exact standalone metadata at the beginning. Generic phrases
        # such as "Lyrics", "You might also like" or "Embed" may be real verses.
        lyric_lines = full_lyrics.splitlines()
        if lyric_lines and re.fullmatch(r"\d+\s+Contributors?", lyric_lines[0].strip()):
            lyric_lines.pop(0)
        while lyric_lines and not lyric_lines[0].strip():
            lyric_lines.pop(0)
        if (
            title
            and lyric_lines
            and lyric_lines[0].strip().casefold() == f"{title} Lyrics".casefold()
        ):
            lyric_lines.pop(0)
        full_lyrics = re.sub(r"\n{3,}", "\n\n", "\n".join(lyric_lines)).strip()

        # Length/line count are quality signals, not evidence of incompleteness.
        # Identity is checked by the caller; short texts still require adjudication.
        return full_lyrics or None
