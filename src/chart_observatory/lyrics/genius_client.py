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
        from chart_observatory.lyrics.quota_discovery import match_genius_identity

        if not isinstance(result, dict) or not match_genius_identity(title, artist, result):
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
            return self._extract_lyrics_from_html(resp.text)
        except (httpx.HTTPError, httpx.TimeoutException):
            return None

    def _extract_lyrics_from_html(self, html: str) -> str | None:
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

        # Clean Genius metadata noise
        # 1. Remove "N ContributorsTranslations..." prefix
        full_lyrics = re.sub(
            r"^\d+\s*Contributor[s]?.*?(?=\n\[|\n[A-Z0-9])",
            "",
            full_lyrics,
            count=1,
            flags=re.DOTALL,
        )
        # 2. Remove "Song Title Lyrics" header
        full_lyrics = re.sub(r"^.*?\bLyrics\s*\n", "", full_lyrics, count=1)
        # 3. Remove "You might also like"
        full_lyrics = re.sub(r"\bYou might also like\b", "", full_lyrics, flags=re.I)
        # 4. Remove trailing "Embed" or "123Embed"
        full_lyrics = re.sub(r"\d*Embed$", "", full_lyrics.strip())
        # 5. Clean up excessive newlines
        full_lyrics = re.sub(r"\n{3,}", "\n\n", full_lyrics).strip()

        # Must have at least 30 characters and at least 2 lines to be valid lyrics
        if len(full_lyrics) < 30 or "\n" not in full_lyrics:
            return None

        return full_lyrics
