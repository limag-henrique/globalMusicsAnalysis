import copy
import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from chart_observatory.lyrics.quota_acquisition import (
    AcquisitionStore,
    PacedHTTP,
    decode_js_json_literal,
    extract_html,
    fetch_candidate,
    identity,
    lrclib_text,
    ranking_recovery_priority,
    reconcile_task_metadata,
)


def test_recovery_prioritizes_top_ranks_then_shared_cells_without_mutating_bindings():
    bindings = [dict(country_code="BR", year=2020, position=1)]
    leading = {"chart_bindings": bindings}
    later = {"chart_bindings": [dict(country_code="IN", year=2020, position=2)]}
    shared = {"chart_bindings": [*bindings, dict(country_code="IN", year=2020, position=10)]}
    assert ranking_recovery_priority(shared) < ranking_recovery_priority(leading)
    assert ranking_recovery_priority(leading) < ranking_recovery_priority(later)
    assert bindings == [dict(country_code="BR", year=2020, position=1)]


def test_restricted_html_recovery_keeps_exact_artist_and_last_line(tmp_path):
    from chart_observatory.lyrics.quota_discovery import audit_saved_result

    calls = []
    lines = [f"Fixture verse line number {n}" for n in range(20)]
    html = (
        '<title>Tyler, The Creator - "Fixture Song" Lyrics | AZLyrics.com</title>'
        '<div class="col-lg-8 text-center"><div>' + "<br>".join(lines) + "</div></div>"
    )

    def respond(request):
        calls.append(request.url.host)
        if request.url.host == "lrclib.net":
            return httpx.Response(200, json=[])
        assert request.url.host == "www.azlyrics.com"
        return httpx.Response(200, text=html)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = fetch_candidate(
            "Fixture Song",
            "Tyler, The Creator",
            PacedHTTP(tmp_path, client),
            html_sources={"AZLYRICS"},
        )
    assert calls == ["lrclib.net", "www.azlyrics.com"]
    assert result["text"].endswith(lines[-1])
    assert result["source_metadata"]["observed_artist"] == "Tyler, The Creator"
    audit = audit_saved_result({"title": "Fixture Song", "artist": "Tyler, The Creator"}, result)
    assert not audit["text_quality_flags"]


def test_native_metadata_refresh_preserves_history_and_rejects_another_candidate():
    payload = dict(
        recording_id="SPOTIFY:one",
        title="Song",
        artist="Old Artist",
        chart_bindings=[{"year": 2021}],
    )
    display = dict(
        candidate_id="SPOTIFY:one",
        title="Song",
        artist="Verified Artist",
        metadata_resolution={"basis": "native_uri"},
    )
    updated = reconcile_task_metadata(payload, display)
    assert updated["requires_metadata_reconciliation"]
    assert updated["metadata_revision_history"][0]["artist"] == "Old Artist"
    assert (
        payload["artist"] == "Old Artist" and updated["chart_bindings"] == payload["chart_bindings"]
    )
    import pytest

    with pytest.raises(ValueError, match="another retrieval"):
        reconcile_task_metadata(payload, {**display, "candidate_id": "SPOTIFY:other"})


def test_timestamped_lyrics_keep_all_lines_and_reject_unparsed_content():
    assert (
        lrclib_text(
            {
                "plainLyrics": None,
                "syncedLyrics": (
                    "[00:01.23]First line\n[00:05.12]Repeated chorus\n"
                    "[00:09.00]Repeated chorus\n[03:20.00]Final line"
                ),
            }
        )
        == "First line\nRepeated chorus\nRepeated chorus\nFinal line"
    )
    assert lrclib_text({"syncedLyrics": "[00:01.00]First\nUNPARSED LINE"}) is None
    assert lrclib_text({"plainLyrics": [], "syncedLyrics": None}) is None


def test_symbol_only_song_titles_are_distinct_and_not_missing_metadata():
    assert identity("+") == "+"
    assert identity("!") == "!"
    assert identity("+") != identity("!")
    assert identity(None) == ""


def test_wrong_version_is_rejected_and_all_html_sections_are_preserved():
    metadata = json.dumps(
        {"@type": "MusicRecording", "name": "Song (Live)", "byArtist": {"name": "Artist"}}
    )
    html = (
        f'<script type="application/ld+json">{metadata}</script>'
        '<div data-lyrics-container="true">First verse<br>Last line of verse</div>'
        '<div data-lyrics-container="true">Final verse<br>Last line of the song</div>'
    )
    assert extract_html(html, "GENIUS", "Song", "Artist") is None
    text = extract_html(html, "GENIUS", "Song (Live)", "Artist")
    assert text.startswith("First verse")
    assert text.endswith("Last line of the song")
    assert text.count("Final verse") == 1


def test_html_rejects_unrequested_guest_even_when_primary_artist_matches():
    metadata = json.dumps(
        {
            "@type": "MusicRecording",
            "name": "Song",
            "byArtist": [{"name": "Artist"}, {"name": "Guest"}],
        }
    )
    html = (
        f'<script type="application/ld+json">{metadata}</script>'
        '<div data-lyrics-container="true">Full verse</div>'
    )
    assert extract_html(html, "GENIUS", "Song", "Artist") is None
    assert extract_html(html, "GENIUS", "Song", "Artist", ["Artist", "Guest"]) == "Full verse"
    assert extract_html(html, "GENIUS", "Song", "Artist", ["Artist", "Different Guest"]) is None


def test_recommendation_metadata_cannot_identify_a_different_pages_lyrics():
    recording = {
        "@type": "MusicRecording",
        "name": "Requested Song",
        "byArtist": {"name": "Artist"},
    }
    data = {
        "@type": "WebPage",
        "mainEntity": {**recording, "name": "Different Song"},
        "mentions": [recording],
        "relatedLink": {"itemListElement": [recording]},
    }
    html = (
        f'<script type="application/ld+json">{json.dumps(data)}</script>'
        '<div data-lyrics-container="true">Different song lyrics</div>'
    )
    assert extract_html(html, "GENIUS", "Requested Song", "Artist") is None
    assert extract_html(html, "GENIUS", "Different Song", "Artist") == "Different song lyrics"


def test_persistent_claims_prevent_repeated_downloads_and_text_blob_is_unique(tmp_path):
    store = AcquisitionStore(tmp_path)
    store.enqueue("one", {"title": "Song"})
    assert store.claim("one")
    store.finish("one", {"status": "candidate_pending_validation", "text": "Full lyric"})
    store.conn.close()
    store = AcquisitionStore(tmp_path)
    store.enqueue("one", {"title": "Song"})
    assert not store.claim("one")
    store.enqueue("two", {"title": "Same text on another item"})
    assert store.claim("two")
    store.finish("two", {"status": "candidate_pending_validation", "text": "Full lyric"})
    assert len(list((tmp_path / "texts").glob("*.txt"))) == 1
    store.enqueue("unselected_previous_campaign", {"title": "Old track"})
    store.set_scope({"one", "two"})
    assert store.summary() == {"candidate_pending_validation": 2}
    result = json.loads(
        store.conn.execute("SELECT result FROM tasks WHERE identity='one'").fetchone()[0]
    )
    assert result["identity_validated"] is False
    assert result["completeness_validated"] is False
    store.conn.close()


def test_exact_lrclib_identity_uses_one_response_and_reuses_http_cache(tmp_path):
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json=[
                dict(
                    trackName="Song (Live)",
                    artistName="Artist",
                    plainLyrics="First verse\nFinal verse",
                    id=1,
                )
            ],
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        http = PacedHTTP(tmp_path, client)
        first = fetch_candidate("Song (Live)", "Artist", http)
        second = fetch_candidate("Song (Live)", "Artist", http)
    assert len(calls) == 1
    assert first["text"] == second["text"] == "First verse\nFinal verse"


def test_domain_access_failure_pauses_further_requests(tmp_path):
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(403)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        http = PacedHTTP(tmp_path, client)
        assert http.get("https://genius.com/one").status_code == 403
        assert http.get("https://genius.com/two").status_code == 429
    assert len(calls) == 1


def test_search_waits_only_when_both_sources_are_paused_and_honors_retry_after(tmp_path):
    calls = []

    def respond(request):
        calls.append(request.url.host)
        if request.url.host == "genius.com":
            return httpx.Response(429, headers={"retry-after": "3600"})
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        http = PacedHTTP(tmp_path, client)
        assert http.search_retry_delay() == 0
        http.get("https://genius.com/search")
        assert http.search_retry_delay() == 0  # LRCLIB can still work.
        http.get("https://lrclib.net/api/search")
        assert 55 < http.search_retry_delay() <= 60.01
        # A late concurrent 5xx response must not shorten a previous hour-long pause.
        with http._domain_guard:
            http._pause_domain("genius.com", httpx.Response(503))
        http._blocked_until.pop("lrclib.net")
        http.get("https://lrclib.net/api/search?q=next")
        assert 55 < http.search_retry_delay() <= 60.01
        import time

        assert http._blocked_until["genius.com"] - time.monotonic() > 3500
        http.get("https://genius.com/another")
    assert calls == ["genius.com", "lrclib.net", "lrclib.net"]


def test_retry_after_http_date_is_respected(tmp_path):
    later = format_datetime(datetime.now(UTC) + timedelta(hours=1), usegmt=True)
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"retry-after": later})
        )
    ) as client:
        http = PacedHTTP(tmp_path, client)
        http.get("https://genius.com/search")
        http.get("https://lrclib.net/api/search")
        assert 3500 < http.search_retry_delay() <= 3600


def test_genius_embedded_song_identity_requires_current_page_id_url_and_all_performers():
    state = dict(
        currentPage="songPage",
        songPage={"song": 123},
        entities=dict(
            songs={
                "123": dict(
                    id=123,
                    title="Song",
                    url="https://genius.com/artist-song-lyrics",
                    primaryArtists=[1],
                    featuredArtists=[2],
                ),
                "999": dict(id=999, title="Song"),
            },
            artists={"1": {"name": "Artist"}, "2": {"name": "Guest"}},
        ),
    )

    def extract(value, *, song_id=123, url="https://genius.com/artist-song-lyrics"):
        literal = json.dumps(value).replace("\\", "\\\\").replace("'", "\\'")
        html = (
            f'<meta property="og:url" content="{url}">'
            f"<script>window.__PRELOADED_STATE__ = JSON.parse('{literal}')</script>"
            '<div data-lyrics-container="true">First verse<br>Final verse</div>'
        )
        return extract_html(
            html, "GENIUS", "Song", "Artist", ["Artist", "Guest"], provider_song_id=song_id
        )

    assert extract(state) == "First verse\nFinal verse"
    assert extract(state, song_id=None) is None
    assert extract(state, song_id=999) is None
    assert extract(state, url="https://genius.com/another-song-lyrics") is None
    for mutation in ("page", "id", "title", "guest", "missing_artist", "incomplete"):
        changed = copy.deepcopy(state)
        if mutation == "page":
            changed["songPage"]["song"] = 999
        elif mutation == "id":
            changed["entities"]["songs"]["123"]["id"] = 999
        elif mutation == "title":
            changed["entities"]["songs"]["123"]["title"] = "Song (Live)"
        elif mutation == "guest":
            changed["entities"]["artists"]["2"]["name"] = "Unexpected Guest"
        elif mutation == "missing_artist":
            del changed["entities"]["artists"]["2"]
        else:
            changed["entities"]["songs"]["123"]["lyricsState"] = "incomplete"
        assert extract(changed) is None


def test_embedded_json_decoder_preserves_unicode_and_js_non_escape_characters():
    value = {"title": "Song's $ title / café 🎵", "artist": 'An "Artist"'}
    literal = json.dumps(value, ensure_ascii=True).replace("\\", "\\\\").replace("'", "\\'")
    literal = "'" + literal.replace("$", "\\$") + "'"
    assert decode_js_json_literal(literal) == value
    assert decode_js_json_literal(r"'{\x22id\x22:123}'") == {"id": 123}
    with pytest.raises(ValueError):
        decode_js_json_literal(r"'{\xZZid:123}'")


def test_previous_acquisition_cache_is_reused_without_another_download(tmp_path):
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="saved full page"))
    ) as client:
        old = PacedHTTP(tmp_path / "old", client)
        old.get("https://genius.com/artist-song-lyrics")
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(AssertionError("duplicate network request"))
        )
    ) as client:
        current = PacedHTTP(tmp_path / "current", client, cache_sources=[tmp_path / "old"])
        response = current.get("https://genius.com/artist-song-lyrics")
    assert response.text == "saved full page"
    assert current.trace[-1]["cached"] is True


def test_domain_pause_allows_verified_local_replay_but_no_new_download(tmp_path):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return (
            httpx.Response(200, text="Full saved lyrics")
            if request.url.path == "/saved"
            else httpx.Response(403)
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        http = PacedHTTP(tmp_path, client)
        assert http.get("https://genius.com/saved").status_code == 200
        assert http.get("https://genius.com/blocked").status_code == 403
        assert http.get("https://genius.com/saved").text == "Full saved lyrics"
        assert http.trace[-1]["provider_paused"] is True
        assert http.get("https://genius.com/unknown").status_code == 429
        saved = next(tmp_path.glob("*.json"))
        data = json.loads(saved.read_text(encoding="utf-8"))
        data["body"] = "corrupted"
        saved.write_text(json.dumps(data), encoding="utf-8")
        assert http.get("https://genius.com/saved").status_code == 429
    assert calls == ["/saved", "/blocked"]


def test_alternative_provider_availability_prevents_global_pause(tmp_path):
    import time

    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(404))) as client:
        http = PacedHTTP(tmp_path, client)
        domains = ("lrclib.net", "genius.com", "www.azlyrics.com", "www.musixmatch.com")
        until = time.monotonic() + 60
        http._blocked_until.update({domain: until for domain in domains[:2]})
        assert http.search_retry_delay() > 0
        assert http.search_retry_delay(domains) == 0
        http._blocked_until.update({domain: until for domain in domains[2:]})
        assert 55 < http.search_retry_delay(domains) <= 60
        with pytest.raises(ValueError, match="at least one"):
            http.search_retry_delay(())
