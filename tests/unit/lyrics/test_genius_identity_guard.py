import json

import httpx
import pytest

from chart_observatory.lyrics.genius_client import GeniusClient


@pytest.mark.parametrize(
    "nodes",
    [
        [],
        [{"@type": "MusicRecording", "name": "Example (Live)", "byArtist": {"name": "Artist"}}],
        [{"@type": "MusicRecording", "name": "Example", "byArtist": {"name": "Cover Singer"}}],
        [
            {"@type": "MusicRecording", "name": "Different", "byArtist": {"name": "Artist"}},
            {"@type": "MusicRecording", "name": "Example", "byArtist": {"name": "Artist"}},
        ],
    ],
)
def test_unverified_or_ambiguous_pages_are_rejected(nodes):
    html = (
        '<script type="application/ld+json">'
        + json.dumps({"@graph": nodes})
        + '</script><div data-lyrics-container="true">First complete lyric line<br>'
        "Last complete lyric line</div>"
    )

    def respond(request):
        if "/api/" in request.url.path:
            return httpx.Response(200, json={"response": {"sections": []}})
        return httpx.Response(200, text=html)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        assert GeniusClient(http_client=http).fetch("Example", "Artist") is None


def test_invalid_api_token_is_not_retried():
    authenticated = []

    def respond(request):
        if request.url.host == "api.genius.com":
            authenticated.append(request.url.path)
            return httpx.Response(401)
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = GeniusClient(access_token="test-only", http_client=http)
        client.fetch("Example", "Artist")
        client.fetch("Another", "Artist")
    assert authenticated == ["/search"]


@pytest.mark.parametrize(
    "primary, expected", [("#wanted", True), ("#other", False), ("#missing", False)]
)
def test_graph_uses_explicit_page_primary_song(primary, expected):
    from bs4 import BeautifulSoup

    from chart_observatory.lyrics.quota_acquisition import structured_identity

    data = {
        "@graph": [
            {"@type": "WebPage", "mainEntity": {"@id": primary}},
            {
                "@type": "MusicRecording",
                "@id": "#wanted",
                "name": "Example",
                "byArtist": {"name": "Artist"},
            },
            {
                "@type": "MusicRecording",
                "@id": "#other",
                "name": "Different",
                "byArtist": {"name": "Artist"},
            },
        ]
    }
    page = BeautifulSoup(
        '<script type="application/ld+json">' + json.dumps(data) + "</script>", "html.parser"
    )
    assert structured_identity(page, "Example", "Artist") is expected


@pytest.mark.parametrize("requested, accepted", [("Artist", False), ("Artist|Guest", True)])
def test_legacy_client_resolves_partial_search_credit_metadata(requested, accepted):
    partial = dict(
        id=123,
        title="Song",
        primary_artist=dict(name="Artist"),
        url="https://genius.com/artist-song-lyrics",
    )
    calls = []

    def respond(request):
        calls.append(request.url.path)
        if request.url.path == "/api/search/multi":
            return httpx.Response(
                200,
                json={"response": {"sections": [{"type": "song", "hits": [{"result": partial}]}]}},
            )
        if request.url.path == "/api/songs/123":
            return httpx.Response(
                200,
                json={"response": {"song": {**partial, "featured_artists": [dict(name="Guest")]}}},
            )
        if request.url.path == "/artist-song-lyrics":
            assert accepted
            return httpx.Response(
                200,
                text=(
                    '<script type="application/ld+json">{"@type":"MusicRecording",'
                    '"name":"Song","byArtist":{"name":"Artist"}}</script>'
                    '<div data-lyrics-container="true">First complete fixture verse<br>'
                    "Last complete fixture verse</div>"
                ),
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        text = GeniusClient(http_client=http).fetch("Song", requested)
    assert bool(text) is accepted
    assert "/api/songs/123" in calls
