import httpx
import pytest

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
                                            "featured_artists": [],
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
    old = dict(
        source="LRCLIB",
        text_path=str(path),
        text_sha256=digest,
        source_metadata=dict(observed_title="Song", observed_artist="Artist"),
    )
    result = dict(
        source="LRCLIB",
        generated_by_ai=False,
        text="A complete fixture line\n" * 30,
        source_metadata=dict(observed_title="Song", observed_artist="Artist"),
    )
    replay = dict(
        replay_kind="flagged_repair", replaces_text_sha256=digest, payload=payload, result=result
    )
    assert usable_cached_repair(payload, old, replay) is result
    assert "text_quality_flags" not in old
    path.write_bytes(b"changed blob")
    assert usable_cached_repair(payload, old, replay) is None


def test_retry_uses_alternative_sources_and_rejects_wrong_song(monkeypatch):
    import chart_observatory.lyrics.quota_discovery as module

    monkeypatch.setattr(
        module,
        "discover_candidate",
        lambda *a, **k: {
            "status": "not_found_or_unverified",
            "source_errors": ["GENIUS_SEARCH:403"],
        },
    )
    calls = []

    def fetch(*args, **kwargs):
        calls.append(kwargs)
        return dict(
            source="AZLYRICS",
            text="A complete fixture line\n" * 30,
            source_metadata=dict(
                observed_title="Song",
                observed_artist="Artist",
                page_identity_scope="exact_page_title",
            ),
        )

    monkeypatch.setattr(module, "fetch_candidate", fetch)
    result = module.recover_with_fallback("Song", "Artist", object())
    assert result["source"] == "AZLYRICS"
    assert calls == [{"html_sources": {"AZLYRICS", "MUSIXMATCH"}}]
    rejected = module.recover_with_fallback("Song (Live)", "Artist", object())
    assert not rejected.get("text")
    assert "GENIUS_SEARCH:403" in rejected["source_errors"]


def test_discovery_timeout_preserves_error_and_reaches_alternative(monkeypatch):
    import httpx

    import chart_observatory.lyrics.quota_discovery as module

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("fixture timeout")

    monkeypatch.setattr(module, "discover_candidate", timeout)
    monkeypatch.setattr(
        module,
        "fetch_candidate",
        lambda *a, **k: dict(
            source="AZLYRICS",
            text="Fixture line\n" * 30,
            source_metadata=dict(
                observed_title="Song",
                observed_artist="Artist",
                page_identity_scope="exact_page_title",
            ),
        ),
    )
    result = module.recover_with_fallback("Song", "Artist", object())
    assert result["source"] == "AZLYRICS"
    assert "IDENTITY_DISCOVERY:ReadTimeout" in result["source_errors"]
    assert not result.get("classification_ready")


def test_duration_mismatch_is_held_without_certifying_matching_duration():
    payload = dict(title="Song", artist="Artist", metadata_resolution=dict(duration_ms=200506))
    result = dict(
        source="LRCLIB",
        source_metadata=dict(observed_title="Song", observed_artist="Artist", duration_seconds=240),
    )
    audit = audit_saved_result(payload, result)
    assert "recording_duration_mismatch" in audit["text_quality_flags"]
    result["source_metadata"]["duration_seconds"] = 201
    audit = audit_saved_result(payload, result)
    assert "recording_duration_mismatch" not in audit["text_quality_flags"]
    assert not audit["identity_validated"] and not audit["completeness_validated"]
    result["source_metadata"]["duration_seconds"] = float("nan")
    flags = audit_saved_result(payload, result)["text_quality_flags"]
    assert "recording_duration_mismatch" not in flags


def test_duration_difference_continues_to_alternative_source(monkeypatch):
    import chart_observatory.lyrics.quota_discovery as module

    mismatched = dict(
        source="LRCLIB",
        text="A complete fixture line\n" * 30,
        source_metadata=dict(observed_title="Song", observed_artist="Artist", duration_seconds=240),
    )
    alternative = dict(
        source="AZLYRICS",
        text="Another complete fixture line\n" * 30,
        source_metadata=dict(
            observed_title="Song", observed_artist="Artist", page_identity_scope="exact_page_title"
        ),
    )
    monkeypatch.setattr(module, "discover_candidate", lambda *a, **k: mismatched)
    calls = []

    def fetch(*args, **kwargs):
        calls.append(kwargs)
        return alternative

    monkeypatch.setattr(module, "fetch_candidate", fetch)
    assert (
        module.recover_with_fallback(
            "Song", "Artist", object(), metadata_resolution=dict(duration_ms=200506)
        )["source"]
        == alternative["source"]
    )
    assert calls == [{"html_sources": {"AZLYRICS", "MUSIXMATCH"}, "expected_duration_ms": 200506}]
    assert mismatched["source_metadata"]["duration_seconds"] == 240


@pytest.mark.parametrize(
    "version", ["Live", "Ao Vivo", "2018 Remaster", "Radio Edit", "Live at Wembley 1986", "Remix"]
)
def test_feature_credit_does_not_remove_recording_version(version):
    from chart_observatory.lyrics.quota_discovery import split_feature_credits

    requested = f"Song (feat. Guest - {version})"
    title, credits = split_feature_credits(requested)
    assert title == f"Song ({version})" and credits == ["Guest"]
    hit = dict(
        title=title, primary_artist=dict(name="Artist"), featured_artists=[dict(name="Guest")]
    )
    assert match_genius_identity(requested, "Artist", hit)
    assert not match_genius_identity(requested, "Artist", {**hit, "title": "Song"})
    assert not match_genius_identity(
        requested, "Artist", {**hit, "featured_artists": [dict(name="Different Guest")]}
    )


@pytest.mark.parametrize("requested, expected", [("Artist", False), ("Artist|Guest", True)])
def test_partial_search_hit_requires_full_credit_lookup(tmp_path, requested, expected):
    partial = dict(
        id=123,
        title="Song",
        primary_artist=dict(name="Artist"),
        url="https://genius.com/artist-song-lyrics",
    )
    paths = []

    def respond(request):
        paths.append(request.url.path)
        if request.url.host == "lrclib.net":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/search/multi":
            return httpx.Response(
                200,
                json={"response": {"sections": [{"type": "song", "hits": [{"result": partial}]}]}},
            )
        if request.url.path == "/api/songs/123":
            return httpx.Response(
                200,
                json={
                    "response": {
                        "song": {**partial, "featured_artists": [dict(id=2, name="Guest")]}
                    }
                },
            )
        assert expected, "must not download a song with an unrequested guest"
        return httpx.Response(
            200,
            text=(
                '<script type="application/ld+json">{"@type":"MusicRecording",'
                '"name":"Song","byArtist":{"name":"Artist"}}</script>'
                '<div data-lyrics-container="true">'
                + "<br>".join(f"Complete fixture verse {i}" for i in range(25))
                + "</div>"
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = discover_candidate("Song", requested, PacedHTTP(tmp_path, client))
    assert "/api/songs/123" in paths
    assert bool(result.get("text")) is expected
    if expected:
        assert (
            result["source_metadata"]["provider_credit_evidence"][
                "performer_credit_fields_explicit"
            ]
            is True
        )


@pytest.mark.parametrize("featured", [None, {}, "Guest", ["Guest"], [{}]])
def test_unknown_or_malformed_featured_credits_do_not_mean_solo(featured):
    hit = dict(title="Song", primary_artist=dict(name="Artist"), featured_artists=featured)
    assert not match_genius_identity("Song", "Artist", hit)


def test_fallback_preserves_all_failure_stages_without_duplicating_timeout(monkeypatch):
    import chart_observatory.lyrics.quota_discovery as module

    request = httpx.Request("GET", "https://example.org/test")

    def discovery(*_args, **_kwargs):
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    def fetch(*_args, **kwargs):
        stage = "alternate" if kwargs.get("html_sources") else "initial"
        return dict(
            status="not_found_or_unverified",
            source_errors=[stage + ":404"],
            http_evidence=[dict(url="https://example.org/" + stage, status=404)],
        )

    monkeypatch.setattr(module, "discover_candidate", discovery)
    monkeypatch.setattr(module, "fetch_candidate", fetch)
    result = module.recover_with_fallback("Song", "Artist", object(), first_time=True)
    assert result["source_errors"] == [
        "initial:404",
        "IDENTITY_DISCOVERY:ReadTimeout",
        "alternate:404",
    ]
    assert [e["acquisition_stage"] for e in result["http_evidence"]] == [
        "INITIAL_FETCH",
        "ALTERNATIVE_FETCH",
    ]
    assert len(result["acquisition_attempts"]) == 3
    assert not result.get("classification_ready")


def test_formatting_only_lrclib_variants_preserve_original_and_real_repetition(tmp_path):
    a = "Original verse.\n\n[Refrão]\nAmor!\nAmor!"
    b = "  Original\t verse.\r\n\r\n[Refrão]\r\nAmor! \r\nAmor!"
    rows = [
        dict(id=i, trackName="Song", artistName="Artist", plainLyrics=t)
        for i, t in enumerate([a, b], 1)
    ]

    def respond(request):
        assert request.url.host == "lrclib.net"
        return httpx.Response(200, json=rows)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = discover_candidate("Song", "Artist", PacedHTTP(tmp_path, client))
    assert result["text"] == a
    assert result["text"].count("Amor!") == 2
    assert result["source_metadata"]["equivalent_provider_records"] == [1, 2]
    assert not result.get("identity_validated")


def test_lrclib_signature_does_not_merge_missing_verses_or_versions():
    from chart_observatory.lyrics.quota_acquisition import lrclib_text_signature

    first = dict(plainLyrics="First verse\nRefrain\nRefrain\nLast verse")
    shorter = dict(plainLyrics="First verse\nRefrain\nLast verse")
    assert lrclib_text_signature(first) != lrclib_text_signature(shorter)


def test_replay_cache_inventory_includes_recent_campaigns(tmp_path):
    from chart_observatory.lyrics.quota_acquisition import recovery_cache_sources

    primary = tmp_path / "data/derived/lyrics/quota/http-cache"
    recent = tmp_path / "data/runtime/import-all-lyrics-20261107/acquisition/http-cache"
    primary.mkdir(parents=True)
    recent.mkdir(parents=True)
    sources = recovery_cache_sources(tmp_path, primary)
    assert recent.resolve() in sources and primary.resolve() in sources
    assert len(sources) == len(set(sources))
