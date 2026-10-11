from __future__ import annotations

import httpx
import pytest

from chart_observatory.lyrics.gemini_pipeline import LrclibClient


def test_fetch_recovers_identical_editions_with_the_resolved_edition_metadata() -> None:
    first = {
        "id": 1,
        "trackName": "Example",
        "artistName": "Artist",
        "albumName": "Standard",
        "duration": 120,
        "instrumental": False,
        "plainLyrics": "We walk together.\nWe find our way.",
    }
    resolved = {**first, "id": 2, "albumName": "Deluxe"}

    def provider(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/search":
            return httpx.Response(200, json=[first, resolved])
        return httpx.Response(200, json=resolved)

    with httpx.Client(transport=httpx.MockTransport(provider)) as http:
        result = LrclibClient(http_client=http).fetch("Example", "Artist")

    assert result == (
        "We walk together.\nWe find our way.",
        {"id": 2, "album_name": "Deluxe", "duration": 120, "instrumental": False},
    )


@pytest.mark.parametrize(
    "edition_lyrics",
    [
        "We walk together.\n\nWe find our way.",
        "WE WALK TOGETHER! We find our way",
    ],
)
def test_fetch_accepts_editions_with_only_lyric_formatting_differences(
    edition_lyrics: str,
) -> None:
    first = {
        "trackName": "Example",
        "artistName": "Artist",
        "plainLyrics": "We walk together.\nWe find our way.",
    }
    resolved = {**first, "id": 2, "plainLyrics": edition_lyrics}

    def provider(request: httpx.Request) -> httpx.Response:
        payload = [first, resolved] if request.url.path == "/api/search" else resolved
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(provider)) as http:
        result = LrclibClient(http_client=http).fetch("Example", "Artist")

    assert result is not None
    assert result[0] == edition_lyrics
    assert result[1]["id"] == 2


@pytest.mark.parametrize(
    "resolved_changes",
    [
        {"artistName": "Other artist"},
        {"trackName": "Example (Live)"},
        {"plainLyrics": "We never walk together. We lose our way."},
        {"instrumental": True},
    ],
)
def test_fetch_rejects_a_resolved_edition_that_conflicts_with_the_search(
    resolved_changes: dict[str, object],
) -> None:
    first = {
        "trackName": "Example",
        "artistName": "Artist",
        "plainLyrics": "We walk together. We find our way.",
        "instrumental": False,
    }

    def provider(request: httpx.Request) -> httpx.Response:
        payload = [first, {**first, "id": 2}] if request.url.path == "/api/search" else {
            **first, **resolved_changes,
        }
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(provider)) as http:
        assert LrclibClient(http_client=http).fetch("Example", "Artist") is None


def test_fetch_keeps_verified_identical_lyrics_when_edition_lookup_times_out() -> None:
    first = {
        "id": 1,
        "trackName": "Example",
        "artistName": "Artist",
        "plainLyrics": "We walk together. We find our way.",
    }

    def provider(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/search":
            return httpx.Response(200, json=[first, {**first, "id": 2}])
        raise httpx.ReadTimeout("Edition endpoint unavailable", request=request)

    with httpx.Client(transport=httpx.MockTransport(provider)) as http:
        result = LrclibClient(http_client=http).fetch("Example", "Artist")

    assert result is not None
    assert result[0] == "We walk together. We find our way."
    assert result[1]["id"] == 1


def test_fetch_holds_different_lyric_versions_even_when_get_selects_one() -> None:
    first = {
        "trackName": "Example",
        "artistName": "Artist",
        "plainLyrics": "We walk together. We find our way.",
    }
    other = {**first, "plainLyrics": "We walk alone. We lose our way."}

    def provider(request: httpx.Request) -> httpx.Response:
        payload = [first, other] if request.url.path == "/api/search" else first
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(provider)) as http:
        assert LrclibClient(http_client=http).fetch("Example", "Artist") is None


@pytest.mark.parametrize("status", [404, 429, 503])
def test_fetch_can_reuse_identical_search_results_when_get_is_unavailable(status: int) -> None:
    first = {
        "id": 1,
        "trackName": "Example",
        "artistName": "Artist",
        "plainLyrics": "We walk together. We find our way.",
    }

    def provider(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/search":
            return httpx.Response(200, json=[first, {**first, "id": 2}])
        return httpx.Response(status)

    with httpx.Client(transport=httpx.MockTransport(provider)) as http:
        result = LrclibClient(http_client=http).fetch("Example", "Artist")

    assert result is not None
    assert result[0] == "We walk together. We find our way."
    assert result[1]["id"] == 1
