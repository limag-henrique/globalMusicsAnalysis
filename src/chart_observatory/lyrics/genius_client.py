"""Genius lyrics scraper — API-free HTML scraping with optional API token support."""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import quote

import httpx

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
        # Remove feat. from title for URL construction
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
        """Use the Genius API to search, then scrape the lyrics page."""
        if not self._token:
            return None
        query = f"{artist.split(',', 1)[0].strip()} {title}"
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

        # Match the best hit
        wanted_title = normalize_lookup_text(title)
        wanted_artist = normalize_lookup_text(artist.split(",", 1)[0])

        for hit in hits[:5]:
            result = hit.get("result", {})
            hit_title = normalize_lookup_text(str(result.get("title", "")))
            hit_artist = normalize_lookup_text(
                str(result.get("primary_artist", {}).get("name", ""))
            )
            if hit_title == wanted_title and hit_artist == wanted_artist:
                page_url = result.get("url")
                if page_url:
                    return self._scrape_lyrics_page(page_url)

        # Fallback: try the first result if title matches
        first = hits[0].get("result", {})
        first_title = normalize_lookup_text(str(first.get("title", "")))
        if first_title == wanted_title:
            page_url = first.get("url")
            if page_url:
                return self._scrape_lyrics_page(page_url)

        return None

    def _try_site_search(self, title: str, artist: str) -> str | None:
        """Search Genius via their site search and scrape the result."""
        query = f"{artist.split(',', 1)[0].strip()} {title}"
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
        wanted_artist = normalize_lookup_text(artist.split(",", 1)[0])

        for section in sections:
            if section.get("type") != "song":
                continue
            for hit in section.get("hits", [])[:5]:
                result = hit.get("result", {})
                hit_title = normalize_lookup_text(str(result.get("title", "")))
                hit_artist = normalize_lookup_text(
                    str(result.get("primary_artist", {}).get("name", ""))
                )
                if hit_title == wanted_title or (
                    wanted_artist in hit_artist and wanted_title in hit_title
                ):
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
        """Extract lyrics text from a Genius page HTML string.

        Genius wraps lyrics in containers with ``data-lyrics-container="true"``.
        We use regex rather than BeautifulSoup for this specific extraction to
        keep dependencies light — the HTML structure is predictable.
        """
        # Find all lyrics containers
        containers = re.findall(
            r'<div[^>]*data-lyrics-container="true"[^>]*>(.*?)</div>',
            html,
            re.DOTALL,
        )
        if not containers:
            # Fallback: try the older Genius lyrics div structure
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

        # Clean Genius metadata noise from extracted text
        # Remove "N ContributorsTranslations..." prefix line
        full_lyrics = re.sub(
            r"^\d+\s+Contributor[s]?.*?(?=\n\[|\n[A-Z])", "", full_lyrics, count=1, flags=re.DOTALL
        )
        # Remove "Song Title Lyrics" header line
        full_lyrics = re.sub(r"^.*?\bLyrics\s*\n", "", full_lyrics, count=1)
        # Clean up excessive newlines
        full_lyrics = re.sub(r"\n{3,}", "\n\n", full_lyrics)
        full_lyrics = full_lyrics.strip()

        return full_lyrics if len(full_lyrics) > 20 else None
