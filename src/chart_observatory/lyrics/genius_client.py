"""Genius lyrics scraper — API-free HTML scraping with optional API token support."""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import quote

import httpx
from rapidfuzz import fuzz

from chart_observatory.lyrics.gemini_pipeline import normalize_lookup_text

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _strip_html_tags(html: str) -> str:
    """Remove HTML tags, keeping text content and converting <br> to newlines."""
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "", html)
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&#x27;", "'").replace("&quot;", '"')
    return html.strip()


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
            timeout=30.0, follow_redirects=True, headers=_HEADERS,
        )

    # -- public API -----------------------------------------------------------

    def fetch(self, title: str, artist: str) -> str | None:
        """Try to find lyrics for a song. Returns cleaned lyrics text or None."""
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
        slug = f"{_slugify(artist.split(',', 1)[0].strip())}-{_slugify(clean_title.strip())}-lyrics"
        url = f"https://genius.com/{slug}"

        try:
            resp = self._http.get(url)
            if resp.status_code == 200:
                return self._extract_lyrics_from_html(resp.text)
        except (httpx.HTTPError, httpx.TimeoutException):
            pass
        return None

    def _try_api_search(self, title: str, artist: str) -> str | None:
        """Use the Genius API to search, then scrape the lyrics page with fuzzy validation."""
        if not self._token:
            return None
        primary_artist = artist.split(",", 1)[0].strip()
        query = f"{primary_artist} {title}"
        try:
            resp = self._http.get(
                "https://api.genius.com/search",
                params={"q": query},
                headers={"Authorization": f"Bearer {self._token}"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
        except (httpx.HTTPError, httpx.TimeoutException, ValueError):
            return None

        hits = data.get("response", {}).get("hits", [])
        if not hits:
            return None

        wanted_title = normalize_lookup_text(title)
        wanted_artist = normalize_lookup_text(primary_artist)

        best_hit_url: str | None = None
        best_score = 0.0

        for hit in hits[:8]:
            result = hit.get("result", {})
            hit_title = normalize_lookup_text(str(result.get("title", "")))
            hit_artist = normalize_lookup_text(
                str(result.get("primary_artist", {}).get("name", ""))
            )
            
            title_score = fuzz.token_set_ratio(wanted_title, hit_title)
            artist_score = fuzz.token_set_ratio(wanted_artist, hit_artist)
            combined = (title_score * 0.6) + (artist_score * 0.4)

            # Strict threshold to avoid wrong song attribution
            if title_score >= 80 and artist_score >= 70 and combined > best_score:
                best_score = combined
                best_hit_url = result.get("url")

        if best_hit_url:
            lyrics = self._scrape_lyrics_page(best_hit_url)
            if lyrics:
                return lyrics

        return None

    def _try_site_search(self, title: str, artist: str) -> str | None:
        """Search Genius via their site search and scrape the result with fuzzy validation."""
        primary_artist = artist.split(",", 1)[0].strip()
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
        wanted_title = normalize_lookup_text(title)
        wanted_artist = normalize_lookup_text(primary_artist)

        for section in sections:
            if section.get("type") != "song":
                continue
            for hit in section.get("hits", [])[:5]:
                result = hit.get("result", {})
                hit_title = normalize_lookup_text(str(result.get("title", "")))
                hit_artist = normalize_lookup_text(
                    str(result.get("primary_artist", {}).get("name", ""))
                )
                title_score = fuzz.token_set_ratio(wanted_title, hit_title)
                artist_score = fuzz.token_set_ratio(wanted_artist, hit_artist)
                
                if title_score >= 80 and artist_score >= 70:
                    page_url = result.get("url")
                    if page_url:
                        lyrics = self._scrape_lyrics_page(page_url)
                        if lyrics:
                            return lyrics
        return None

    # -- scraping helpers -----------------------------------------------------

    def _scrape_lyrics_page(self, url: str) -> str | None:
        """Fetch a Genius lyrics page and extract text."""
        try:
            resp = self._http.get(url)
            if resp.status_code != 200:
                return None
            return self._extract_lyrics_from_html(resp.text)
        except (httpx.HTTPError, httpx.TimeoutException):
            return None

    def _extract_lyrics_from_html(self, html: str) -> str | None:
        """Extract lyrics text from a Genius page HTML string."""
        # Find all lyrics containers
        containers = re.findall(
            r'<div[^>]*data-lyrics-container="true"[^>]*>(.*?)</div>',
            html,
            re.DOTALL,
        )
        if not containers:
            match = re.search(
                r'<div\s+class="lyrics"[^>]*>(.*?)</div>',
                html,
                re.DOTALL,
            )
            if match:
                containers = [match.group(1)]

        if not containers:
            return None

        lines: list[str] = []
        for container in containers:
            text = _strip_html_tags(container)
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
