"""Letras.mus.br lyrics scraper — HTML scraping for Brazilian and international music."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from chart_observatory.lyrics.gemini_pipeline import normalize_lookup_text
from chart_observatory.lyrics.text_quality import (
    html_fragment_text,
    html_lyric_text,
    prepare_lyric_derivative,
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _slugify_letras(text: str) -> str:
    """Convert text to a Letras.mus.br URL slug."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[&]", "e", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text


class LetrasClient:
    """Scrape lyrics from Letras.mus.br.

    Strategy:
    1. Build the canonical URL ``https://www.letras.mus.br/<artist>/<title>/``
    2. Fallback: search via ``https://www.letras.mus.br/busca/?q=<query>``
    3. Extract lyrics from the page HTML with strict cleaning
    """

    def __init__(
        self,
        http_client: Any | None = None,
    ) -> None:
        self._http = http_client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers=_HEADERS,
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
                return self._extract_lyrics(resp.text)
        except (httpx.HTTPError, httpx.TimeoutException):
            pass
        return None

    def _try_search(self, title: str, artist: str) -> str | None:
        """Search Letras.mus.br and scrape the best matching result."""
        primary_artist = artist.split(",", 1)[0].strip()
        query = f"{primary_artist} {title}"
        search_url = f"https://www.letras.mus.br/busca/?q={quote(query)}"

        try:
            resp = self._http.get(search_url)
            if resp.status_code != 200:
                return None
        except (httpx.HTTPError, httpx.TimeoutException):
            return None

        # Extract song links from search results
        song_links = re.findall(
            r'href="(https?://www\.letras\.mus\.br/[^"]+/[^"]+/)"',
            resp.text,
        )
        if not song_links:
            song_links_rel = re.findall(
                r'href="(/[a-z0-9][\w-]*/[\w-]+/)"',
                resp.text,
            )
            song_links = [f"https://www.letras.mus.br{link}" for link in song_links_rel]

        wanted_title = normalize_lookup_text(title)
        wanted_artist = normalize_lookup_text(primary_artist)

        for link in song_links[:5]:
            parts = link.rstrip("/").split("/")
            if len(parts) >= 2:
                url_artist = parts[-2].replace("-", " ")
                url_title = parts[-1].replace("-", " ")
                norm_url_artist = normalize_lookup_text(url_artist)
                norm_url_title = normalize_lookup_text(url_title)

                title_score = fuzz.token_set_ratio(wanted_title, norm_url_title)
                artist_score = fuzz.token_set_ratio(wanted_artist, norm_url_artist)

                if title_score >= 80 and artist_score >= 70:
                    try:
                        page_resp = self._http.get(link)
                        if page_resp.status_code == 200:
                            lyrics = self._extract_lyrics(page_resp.text)
                            if lyrics:
                                return lyrics
                    except (httpx.HTTPError, httpx.TimeoutException):
                        continue
        return None

    def _extract_lyrics(self, html: str) -> str | None:
        """Extract lyrics text from a Letras.mus.br page."""
        page = BeautifulSoup(html, "html.parser")
        for selector in (".lyric-original", ".cnt-letra"):
            containers = page.select(selector)
            if containers:
                lyrics = "\n\n".join(html_lyric_text(node) for node in containers)
                cleaned = self._clean_lyrics(lyrics)
                if cleaned:
                    return cleaned
        # Fallback DOM containers, avoiding duplicate nested lyric blocks.
        blocks = page.find_all("div", class_=re.compile("lyric"))
        outer = [node for node in blocks if not any(parent in blocks for parent in node.parents)]
        if outer:
            cleaned = self._clean_lyrics("\n\n".join(html_lyric_text(node) for node in outer))
            if cleaned:
                return cleaned

        # Strategy 4: JSON-LD or embedded data
        match = re.search(r'"lyrics"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
        if match:
            try:
                lyrics = json.loads('"' + match.group(1) + '"')
            except json.JSONDecodeError:
                return None
            lyrics = html_fragment_text(lyrics)
            if lyrics and len(lyrics) > 30:
                return self._clean_lyrics(lyrics)

        return None

    def _clean_lyrics(self, text: str) -> str | None:
        """Clean up extracted lyrics text."""
        text = prepare_lyric_derivative(text, "LETRAS").text
        text = "\n".join(line.strip() for line in text.splitlines())
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"^\s*Enviada por.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*Corrigida por.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*Revisões por.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*Viu algum erro.*$", "", text, flags=re.MULTILINE)
        text = text.strip()
        if len(text) < 30 or "\n" not in text:
            return None
        return text
