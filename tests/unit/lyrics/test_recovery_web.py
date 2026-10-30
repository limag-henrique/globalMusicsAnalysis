import errno
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import pytest

from chart_observatory.lyrics.recovery_web import CachedRecoveryHTTP, recover_candidate


def test_low_disk_space_stops_before_writing_cache(tmp_path, monkeypatch):
    import chart_observatory.lyrics.recovery_web as recovery

    monkeypatch.setattr(recovery, "disk_usage", lambda _: SimpleNamespace(free=0), raising=False)
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text="provider response")
    )) as client:
        http = CachedRecoveryHTTP(tmp_path, client, 0)
        with pytest.raises(OSError) as error:
            http.get("https://example.test/lyrics")
    assert error.value.errno == errno.ENOSPC
    assert not list(tmp_path.glob("*.json"))


def test_google_discovery_returns_links_without_importing_lyric_snippets(tmp_path):
    from chart_observatory.lyrics.recovery_web import discover_google_sources

    html = '''<a href="/url?q=https%3A%2F%2Fartist.example%2Fsong&amp;sa=U">
        <h3>Official song lyrics</h3></a><div>A truncated lyric snippet</div>
        <a href="https://accounts.google.com/login"><h3>Login</h3></a>'''
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text=html)
    )) as client:
        sources = discover_google_sources("Song", "Artist", CachedRecoveryHTTP(tmp_path, client, 0))
    assert sources == [{"url": "https://artist.example/song",
                        "title": "Official song lyrics", "verification": "unverified"}]


def test_two_requests_can_overlap_within_same_domain(tmp_path):
    barrier = threading.Barrier(2, timeout=2)

    def respond(request):
        barrier.wait()
        return httpx.Response(200, text="provider response")

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        http = CachedRecoveryHTTP(tmp_path, client, interval=0)
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(http.get, [f"https://example.test/{i}" for i in range(4)]))
    assert all(response.status_code == 200 for response in responses)


def test_interrupted_cache_is_preserved_and_refetched(tmp_path):
    key = hashlib.sha256(b"https://example.test/lyrics").hexdigest()
    (tmp_path / f"{key}.json").write_text("", encoding="utf-8")
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text="restored response")
    )) as client:
        http = CachedRecoveryHTTP(tmp_path, client, 0)
        assert http.get("https://example.test/lyrics").text == "restored response"
    assert list(tmp_path.glob("*.interrupted-*"))


def test_successful_response_is_cached_without_another_network_request(tmp_path):
    calls = []

    def respond(request):
        calls.append(request.url)
        return httpx.Response(200, text="response body")

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        http = CachedRecoveryHTTP(tmp_path, client, interval=0)
        assert http.get("https://example.test/lyrics").text == "response body"
        assert http.get("https://example.test/lyrics").text == "response body"
    assert len(calls) == 1


def test_original_response_bytes_and_encoding_survive_cache_replay(tmp_path):
    calls = []
    original = "Canção completa".encode("iso-8859-1")

    def respond(request):
        calls.append(request.url)
        return httpx.Response(200, content=original,
                              headers={"content-type": "text/plain; charset=iso-8859-1"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        http = CachedRecoveryHTTP(tmp_path, client, interval=0)
        assert http.get("https://example.test/latin1").content == original
        replay = http.get("https://example.test/latin1")
        assert replay.content == original
        assert replay.text == "Canção completa"
        assert http.trace[-1]["raw_bytes_preserved"] is True
    assert len(calls) == 1


def test_unavailable_api_does_not_prevent_scraping_other_source(tmp_path):
    def respond(request):
        if request.url.host == "lrclib.net":
            raise httpx.ConnectError("unavailable", request=request)
        return httpx.Response(200, text='''<div data-lyrics-container="true">
            [Verse 1]<br>First complete verse with sufficient words<br>Another lyric line</div>''')

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = recover_candidate("Song", "Artist", CachedRecoveryHTTP(tmp_path, client, 0))
    assert result["source"] == "GENIUS"
    assert result["status"] == "candidate_pending_validation"
    assert result["identity_validated"] is False
    assert result["generated_by_ai"] is False
    assert any(
        row["url"].startswith("https://genius.com/") and row["status"] == 200
        for row in result["http_evidence"]
    )


def test_collect_all_preserves_disagreeing_sources_without_claiming_validation(tmp_path):
    def respond(request):
        if request.url.host == "lrclib.net":
            return httpx.Response(200, json=[{
                "trackName": "Song", "artistName": "Artist", "id": 1,
                "plainLyrics": "A first provider lyric\nAnother complete lyric line",
            }])
        return httpx.Response(200, text='''<div data-lyrics-container="true">
            A different provider lyric<br>Another complete lyric line</div>''')

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = recover_candidate(
            "Song", "Artist", CachedRecoveryHTTP(tmp_path, client, 0), collect_all=True,
        )
    assert {row["source"] for row in result["variants"]} == {"LRCLIB", "GENIUS"}
    assert result["cross_source_text_agreement"] is False
    assert result["completeness_validated"] is False
    for variant in result["variants"]:
        assert len(variant["original_text_sha256"]) == 64
        assert variant["derivative_version"] == "lyrics-text-quality-v2"
        assert variant["extraction_method"] == "conventional_api_or_html"
        assert isinstance(variant["transformations"], list)
