"""Letras.mus.br lyrics scraper — HTML scraping for Brazilian and international music."""

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
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _slugify_letras(text: str) -> str:
    """Convert text to a Letras.mus.br URL slug.

    Letras uses lowercase, hyphen-separated, ASCII-only slugs.
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[&]", "e", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text


def _strip_html_tags(html: str) -> str:
    """Remove HTML tags, keeping text content and converting <br>/<p> to newlines."""
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</p>", "\n\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "", html)
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&#x27;", "'").replace("&quot;", '"')
    return html.strip()


class LetrasClient:
    """Scrape lyrics from Letras.mus.br.

    Strategy:
    1. Build the canonical URL ``https://www.letras.mus.br/<artist>/<title>/``
    2. Fallback: search via ``https://www.letras.mus.br/busca/?q=<query>``
    3. Extract lyrics from the page HTML
    """

    def __init__(
        self,
        http_client: Any | None = None,
    ) -> None:
        self._http = http_client or httpx.Client(
            timeout=30.0, follow_redirects=True, headers=_HEADERS,
        )

    def fetch(self, title: str, artist: str) -> str | None:
        """Try to find lyrics on Letras.mus.br. Returns cleaned text or None."""
        # Strategy 1: direct URL
        lyrics = self._try_direct_url(title, artist)
        if lyrics:
            return lyrics

        # Strategy 2: site search
        lyrics = self._try_search(title, artist)
        return lyrics

    def _try_direct_url(self, title: str, artist: str) -> str | None:
        """Construct the canonical Letras URL and try to scrape it."""
        clean_title = re.sub(
            r"\s*[\[(]\s*(?:feat\.?|ft\.?|featuring)\b.*?[\])]", "", title, flags=re.I
        )
        artist_slug = _slugify_letras(artist.split(",", 1)[0].strip())
        title_slug = _slugify_letras(clean_title.strip())
        url = f"https://www.letras.mus.br/{artist_slug}/{title_slug}/"

        try:
            resp = self._http.get(url)
            if resp.status_code == 200:
                return self._extract_lyrics(resp.text, title, artist)
        except (httpx.HTTPError, httpx.TimeoutException):
            pass
        return None

    def _try_search(self, title: str, artist: str) -> str | None:
        """Search Letras.mus.br and scrape the best matching result."""
        query = f"{artist.split(',', 1)[0].strip()} {title}"
        search_url = f"https://www.letras.mus.br/busca/?q={quote(query)}"

        try:
            resp = self._http.get(search_url)
            if resp.status_code != 200:
                return None
        except (httpx.HTTPError, httpx.TimeoutException):
            return None

        # Extract song links from search results
        # Letras search results have links in the format /artist/song/
        song_links = re.findall(
            r'href="(https?://www\.letras\.mus\.br/[^"]+/[^"]+/)"',
            resp.text,
        )
        if not song_links:
            # Try relative links
            song_links_rel = re.findall(
                r'href="(/[a-z0-9][\w-]*/[\w-]+/)"',
                resp.text,
            )
            song_links = [
                f"https://www.letras.mus.br{link}" for link in song_links_rel
            ]

        wanted_title = normalize_lookup_text(title)
        wanted_artist = normalize_lookup_text(artist.split(",", 1)[0])

        for link in song_links[:5]:
            # Check if this link looks relevant by extracting artist/title from URL
            parts = link.rstrip("/").split("/")
            if len(parts) >= 2:
                url_artist = parts[-2]
                url_title = parts[-1]
                norm_url_artist = normalize_lookup_text(url_artist.replace("-", " "))
                norm_url_title = normalize_lookup_text(url_title.replace("-", " "))

                if norm_url_title == wanted_title or (
                    wanted_artist in norm_url_artist
                    and self._fuzzy_title_match(norm_url_title, wanted_title)
                ):
                    try:
                        page_resp = self._http.get(link)
                        if page_resp.status_code == 200:
                            lyrics = self._extract_lyrics(
                                page_resp.text, title, artist
                            )
                            if lyrics:
                                return lyrics
                    except (httpx.HTTPError, httpx.TimeoutException):
                        continue
        return None

    def _fuzzy_title_match(self, a: str, b: str) -> bool:
        """Check if two normalized titles are close enough to match."""
        if a == b:
            return True
        # One contains the other
        if a in b or b in a:
            return True
        # Check word overlap
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return False
        overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
        return overlap >= 0.6

    def _extract_lyrics(self, html: str, title: str, artist: str) -> str | None:
        """Extract lyrics text from a Letras.mus.br page.

        Letras.mus.br uses various structures:
        - ``<div class="lyric-original">`` for the original lyrics
        - ``<div class="cnt-letra">`` older format
        - ``<article>`` with ``<p>`` tags containing lyrics lines
        """
        # Strategy 1: lyric-original div (modern layout)
        match = re.search(
            r'<div[^>]*class="[^"]*lyric-original[^"]*"[^>]*>(.*?)</div>\s*(?:<div|</article)',
            html,
            re.DOTALL,
        )
        if match:
            lyrics = _strip_html_tags(match.group(1))
            if lyrics and len(lyrics) > 20:
                return self._clean_lyrics(lyrics)

        # Strategy 2: cnt-letra (older layout)
        match = re.search(
            r'<div[^>]*class="[^"]*cnt-letra[^"]*"[^>]*>(.*?)</div>',
            html,
            re.DOTALL,
        )
        if match:
            lyrics = _strip_html_tags(match.group(1))
            if lyrics and len(lyrics) > 20:
                return self._clean_lyrics(lyrics)

        # Strategy 3: Look for <p> tags inside lyrics containers
        # Letras often uses <p> tags with line breaks
        lyrics_blocks = re.findall(
            r'<div[^>]*class="[^"]*lyric[^"]*"[^>]*>(.*?)</div>',
            html,
            re.DOTALL,
        )
        if lyrics_blocks:
            all_text = []
            for block in lyrics_blocks:
                paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", block, re.DOTALL)
                if paragraphs:
                    for p in paragraphs:
                        text = _strip_html_tags(p)
                        if text:
                            all_text.append(text)
                else:
                    text = _strip_html_tags(block)
                    if text:
                        all_text.append(text)
            if all_text:
                full = "\n\n".join(all_text)
                if len(full) > 20:
                    return self._clean_lyrics(full)

        # Strategy 4: JSON-LD or embedded data
        match = re.search(r'"lyrics"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
        if match:
            lyrics = match.group(1)
            lyrics = lyrics.encode().decode("unicode_escape", errors="replace")
            lyrics = _strip_html_tags(lyrics)
            if lyrics and len(lyrics) > 20:
                return self._clean_lyrics(lyrics)

        return None

    def _clean_lyrics(self, text: str) -> str:
        """Clean up extracted lyrics text."""
        # Normalize whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        # Remove common artifacts
        text = re.sub(r"^\s*Enviada por.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*Corrigida por.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*Revisões por.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*Viu algum erro.*$", "", text, flags=re.MULTILINE)
        return text.strip()
