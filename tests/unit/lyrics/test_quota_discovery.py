import httpx

from chart_observatory.lyrics.quota_acquisition import PacedHTTP
from chart_observatory.lyrics.quota_discovery import (
    audit_saved_result,
    discover_candidate,
    match_genius_identity,
    search_identities,
    settle_metadata_reconciliation,
    usable_cached_repair,
    usable_cached_replay,
)


def test_cached_repair_requires_flagged_old_hash_and_exact_current_identity():
    payload = dict(recording_id="SPOTIFY:one", title="Song", artist="Artist")
    old = dict(source="LETRAS", text_sha256="a" * 64, text_path="previous.txt")
    replay = dict(
        replay_kind="flagged_repair",
        replaces_text_sha256="a" * 64,
        payload=payload,
        result=dict(
            source="LRCLIB",
            generated_by_ai=False,
            text="Full replacement fixture text",
            source_metadata=dict(observed_title="Song", observed_artist="Artist"),
        ),
    )
    assert usable_cached_repair(payload, old, replay) is replay["result"]
    assert old == dict(source="LETRAS", text_sha256="a" * 64, text_path="previous.txt")
    assert usable_cached_repair(payload, {**old, "text_sha256": "b" * 64}, replay) is None
    assert usable_cached_repair(payload, old, {**replay, "replay_kind": "missing_text"}) is None
    assert usable_cached_repair({**payload, "recording_id": "SPOTIFY:other"}, old, replay) is None
    assert usable_cached_repair({**payload, "title": "Song (Live)"}, old, replay) is None
    protected = {
        **old,
        "source": "LRCLIB",
        "source_metadata": dict(observed_title="Song", observed_artist="Artist"),
    }
    assert usable_cached_repair(payload, protected, replay) is None
    replay["result"]["generated_by_ai"] = True
    assert usable_cached_repair(payload, old, replay) is None


def test_html_replay_requires_observed_names_and_exact_identity_scope():
    payload = dict(recording_id="SPOTIFY:one", title="Song", artist="Artist")
    result = dict(
        source="AZLYRICS",
        generated_by_ai=False,
        text="Fixture complete text",
        source_metadata={},
    )
    replay = dict(payload=payload, result=result)
    assert usable_cached_replay(payload, {}, replay) is None
    result["source_metadata"].update(
        observed_title="Song", observed_artist="Artist", page_identity_scope="exact_page_title"
    )
    assert usable_cached_replay(payload, {}, replay) is result
    assert usable_cached_replay({**payload, "title": "Song (Live)"}, {}, replay) is None
    result["source_metadata"]["observed_artist"] = "Other Artist"
    assert usable_cached_replay(payload, {}, replay) is None


def test_cached_replay_only_fills_the_same_song_without_replacing_existing_text():
    payload = dict(recording_id="SPOTIFY:one", title="Song", artist="Artist")
    replay = dict(
        payload=payload,
        result=dict(
            source="LRCLIB",
            text="Full fixture text",
            generated_by_ai=False,
            source_metadata=dict(observed_title="Song", observed_artist="Artist"),
        ),
    )
    assert usable_cached_replay(payload, {}, replay)
    assert usable_cached_replay(payload, {"text_sha256": "saved"}, replay) is None
    assert usable_cached_replay({**payload, "recording_id": "SPOTIFY:other"}, {}, replay) is None
    assert usable_cached_replay({**payload, "artist": "Different Artist"}, {}, replay) is None
    assert usable_cached_replay({**payload, "title": None}, {}, replay) is None


def test_metadata_reconciliation_requires_current_source_names_without_approving_identity():
    payload = dict(
        title="Song",
        artist="Verified Artist",
        requires_metadata_reconciliation=True,
        identity_validated=False,
        not_for_paid_submission=True,
    )
    result = dict(
        source="LRCLIB",
        text="Full text",
        source_metadata={"observed_title": "Song", "observed_artist": "Old Artist"},
    )
    assert settle_metadata_reconciliation(payload, result)["requires_metadata_reconciliation"]
    result["source_metadata"]["observed_artist"] = "Verified Artist"
    updated = settle_metadata_reconciliation(payload, result)
    assert not updated["requires_metadata_reconciliation"]
    assert updated["identity_validated"] is False and updated["not_for_paid_submission"]


def test_discovery_can_find_singer_when_producer_is_first_without_relaxing_match():
    assert search_identities("Song (Live)", "Producer | Singer") == [
        "Producer Singer",
        "Producer",
        "Singer",
    ]
    assert not match_genius_identity(
        "Song (Live)",
        "Producer | Singer",
        {"title": "Song (Live)", "primary_artist": {"name": "Singer"}},
    )


def test_feature_credit_can_differ_only_when_provider_evidences_the_performer():
    hit = dict(
        title="Song", primary_artist={"name": "Artist"}, featured_artists=[{"name": "Guest"}]
    )
    assert match_genius_identity("Song (feat. Guest)", "Artist", hit)
    assert not match_genius_identity("Song", "Artist", hit)
    assert not match_genius_identity(
        "Song (feat. Guest)",
        "Artist",
        {**hit, "featured_artists": [{"name": "Guest"}, {"name": "Unrequested Guest"}]},
    )
    assert not match_genius_identity("Song (feat. Someone Else)", "Artist", hit)
    assert not match_genius_identity("Song (Remix)", "Artist", hit)
    assert not match_genius_identity("Song (Live)", "Artist", hit)
    assert match_genius_identity("Song", "Artist, Guest", hit)
    assert match_genius_identity("Song", "Artist|Guest", hit)
    assert not match_genius_identity("Song", "Artist|Other Guest", hit)
    produced = dict(
        title="Song",
        primary_artist={"name": "Singer"},
        producer_artists=[{"name": "Producer"}],
        featured_artists=[],
    )
    assert match_genius_identity("Song", "Producer|Singer", produced)
    assert not match_genius_identity("Song", "Producer|Other Singer", produced)
    wrong_cover = {
        **produced,
        "primary_artist": {"name": "Cover Singer"},
        "writer_artists": [{"name": "Singer"}],
    }
    assert not match_genius_identity("Song", "Producer|Singer", wrong_cover)


def test_absent_chart_metadata_stays_explicit_without_network(tmp_path):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(AssertionError("must not request unknown song"))
        )
    ) as client:
        result = discover_candidate(None, None, PacedHTTP(tmp_path, client))
    assert result["status"] == "metadata_missing"


def test_known_incomplete_provider_text_is_not_downloaded_or_accepted(tmp_path):
    hit = dict(
        id=123,
        title="Song",
        primary_artist={"name": "Artist"},
        lyrics_state="incomplete",
        url="https://genius.com/artist-song-lyrics",
    )
    calls = []

    def respond(request):
        calls.append(request.url.path)
        if request.url.host == "lrclib.net":
            return httpx.Response(200, json=[])
        assert request.url.path == "/api/search/multi", "must not download incomplete lyrics"
        return httpx.Response(
            200, json={"response": {"sections": [{"type": "song", "hits": [{"result": hit}]}]}}
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = discover_candidate("Song", "Artist", PacedHTTP(tmp_path, client))
    assert result["status"] == "not_found_or_unverified"
    assert "GENIUS_SEARCH:lyrics_declared_incomplete" in result["source_errors"]
    assert "/artist-song-lyrics" not in calls
    audit = audit_saved_result(
        {"title": "Song", "artist": "Artist"},
        {
            "source": "GENIUS",
            "source_metadata": {
                "page_identity_scope": "main_entity_only",
                "observed_title": "Song",
                "provider_credit_evidence": hit,
            },
        },
    )
    assert "provider_declares_incomplete_lyrics" in audit["text_quality_flags"]
    assert not audit["completeness_validated"]


def test_legacy_primary_artist_only_evidence_does_not_pass_collaboration_audit():
    payload = dict(title="Song", artist="Artist|Guest")
    audit = audit_saved_result(payload, {"source": "GENIUS", "source_metadata": {}})
    assert "requested_collaboration_credits_unverified" in audit["text_quality_flags"]
    checked = audit_saved_result(
        payload,
        {
            "source": "GENIUS",
            "source_metadata": {
                "full_requested_artist_credit_matched": True,
                "requested_artist": "Artist|Guest",
                "observed_title": "Song",
                "page_identity_scope": "main_entity_only",
                "provider_credit_evidence": {
                    "primary_artist": {"name": "Artist"},
                    "featured_artists": [{"name": "Guest"}],
                },
            },
        },
    )
    assert not checked["text_quality_flags"]


def test_search_discovers_real_url_but_rejects_another_version(tmp_path):
    requests = []

    def respond(request):
        requests.append(str(request.url))
        if request.url.host == "lrclib.net":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json={
                "response": {
                    "sections": [
                        {
                            "type": "song",
                            "hits": [
                                {
                                    "result": {
                                        "title": "Song (Remix)",
                                        "primary_artist": {"name": "Artist"},
                                        "url": "https://genius.com/wrong-lyrics",
                                    }
                                }
                            ],
                        }
                    ]
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = discover_candidate("Song", "Artist", PacedHTTP(tmp_path, client))
    assert result["status"] == "not_found_or_unverified"
    assert not any("wrong-lyrics" in url for url in requests)


def test_discovery_matches_provider_metadata_and_keeps_last_line(tmp_path):
    def respond(request):
        if request.url.host == "lrclib.net":
            return httpx.Response(200, json=[])
        if "/api/search/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "response": {
                        "sections": [
                            {
                                "type": "song",
                                "hits": [
                                    {
                                        "result": {
                                            "title": "Song",
                                            "primary_artist": {"name": "Artist"},
                                            "url": "https://genius.com/real-lyrics",
                                        }
                                    }
                                ],
                            }
                        ]
                    }
                },
            )
        return httpx.Response(
            200,
            text="""<script type="application/ld+json">{
            "@type":"MusicRecording","name":"Song","byArtist":{"name":"Artist"}}
            </script><div data-lyrics-container="true">First verse<br>Last verse</div>""",
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = discover_candidate("Song", "Artist", PacedHTTP(tmp_path, client))
    assert result["source"] == "GENIUS"
    assert result["text"].endswith("Last verse")
    assert (
        result["source_metadata"]["provider_credit_evidence"]["primary_artist"]["name"] == "Artist"
    )


def test_malformed_provider_search_payload_does_not_raise_attribute_error(tmp_path):
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"response": None}))
    ) as client:
        result = discover_candidate("Song", "Artist", PacedHTTP(tmp_path, client))
    assert result["status"] == "not_found_or_unverified"


def test_repair_rechecks_old_blob_quality_without_mutating_history(tmp_path):
    import hashlib

    payload = dict(recording_id="SPOTIFY:one", title="Song", artist="Artist")
    path = tmp_path / "old.txt"
    raw = b"Only a portion of these lyrics is available"
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    old = dict(source="LRCLIB", text_path=str(path), text_sha256=digest,
               source_metadata=dict(observed_title="Song", observed_artist="Artist"))
    result = dict(source="LRCLIB", generated_by_ai=False,
                  text="A complete fixture line\n" * 30,
                  source_metadata=dict(observed_title="Song", observed_artist="Artist"))
    replay = dict(replay_kind="flagged_repair", replaces_text_sha256=digest,
                  payload=payload, result=result)
    assert usable_cached_repair(payload, old, replay) is result
    assert "text_quality_flags" not in old
    path.write_bytes(b"changed blob")
    assert usable_cached_repair(payload, old, replay) is None


def test_retry_uses_alternative_sources_and_rejects_wrong_song(monkeypatch):
    import chart_observatory.lyrics.quota_discovery as module

    monkeypatch.setattr(module, "discover_candidate", lambda *a, **k: {
        "status": "not_found_or_unverified", "source_errors": ["GENIUS_SEARCH:403"]})
    calls = []
    def fetch(*args, **kwargs):
        calls.append(kwargs)
        return dict(source="AZLYRICS", text="A complete fixture line\n" * 30,
                    source_metadata=dict(observed_title="Song", observed_artist="Artist",
                                         page_identity_scope="exact_page_title"))
    monkeypatch.setattr(module, "fetch_candidate", fetch)
    result = module.recover_with_fallback("Song", "Artist", object())
    assert result["source"] == "AZLYRICS"
    assert calls == [{"html_sources": {"AZLYRICS", "MUSIXMATCH"}}]
    rejected = module.recover_with_fallback("Song (Live)", "Artist", object())
    assert not rejected.get("text")
    assert "GENIUS_SEARCH:403" in rejected["source_errors"]
