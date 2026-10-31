import httpx

from chart_observatory.lyrics.quota_acquisition import PacedHTTP
from chart_observatory.lyrics.quota_discovery import (
    audit_saved_result,
    discover_candidate,
    match_lrclib_credit_binding,
    role_bound_lrclib_candidate,
    settle_metadata_reconciliation,
)


def proof():
    return dict(
        song_id=123,
        primary_artist={"name": "Singer"},
        primary_artists=[],
        featured_artists=[],
        producer_artists=[{"name": "Producer"}],
        writer_artists=[],
    )


def metadata(credits=None):
    return dict(
        credit_binding_provider="GENIUS",
        credit_binding_url="https://genius.com/singer-song-lyrics",
        credit_binding_title="Song",
        provider_credit_evidence=credits or proof(),
    )


def lyric_row(text=None):
    return dict(
        id=5,
        trackName="Song",
        artistName="Singer",
        instrumental=False,
        plainLyrics=text or "\n".join(f"Fixture verse number {n}" for n in range(25)),
    )


def test_role_binding_requires_every_requested_credit_and_all_actual_performers():
    assert match_lrclib_credit_binding("Song", "Producer | Singer", "Singer", metadata())
    assert not match_lrclib_credit_binding("Song", "Producer | Singer", "Producer", metadata())
    assert not match_lrclib_credit_binding("Song (Live)", "Producer | Singer", "Singer", metadata())
    assert not match_lrclib_credit_binding(
        "Song", "Producer | Singer", "Singer", metadata({**proof(), "producer_artists": []})
    )
    assert not match_lrclib_credit_binding(
        "Song",
        "Producer | Singer",
        "Singer",
        metadata({**proof(), "featured_artists": [{"name": "Unexpected Guest"}]}),
    )
    group = {**proof(), "primary_artist": {"name": "Group"}, "writer_artists": [{"name": "Singer"}]}
    assert not match_lrclib_credit_binding("Song", "Group | Singer", "Singer", metadata(group))
    assert not match_lrclib_credit_binding(
        "Song",
        "Producer | Singer",
        "Singer",
        {**metadata(), "credit_binding_url": "https://other.test/song"},
    )


def test_bound_candidate_records_roles_and_clears_only_naming_reconciliation():
    payload = dict(title="Song", artist="Producer | Singer", requires_metadata_reconciliation=True)
    proofs = [(metadata()["credit_binding_url"], "Singer", "Song", proof())]
    result, conflict = role_bound_lrclib_candidate("Song", payload["artist"], [lyric_row()], proofs)
    assert result and not conflict and result["source_metadata"]["observed_artist"] == "Singer"
    audit = audit_saved_result(payload, result)
    assert not audit["text_quality_flags"] and not audit["classification_ready"]
    assert not settle_metadata_reconciliation(payload, result)["requires_metadata_reconciliation"]
    result["source_metadata"]["provider_credit_evidence"]["producer_artists"] = []
    assert (
        "requested_title_or_artist_metadata_mismatch"
        in audit_saved_result(payload, result)["text_quality_flags"]
    )


def test_bound_lyrics_refuse_multiple_text_editions():
    proofs = [(metadata()["credit_binding_url"], "Singer", "Song", proof())]
    result, conflict = role_bound_lrclib_candidate(
        "Song", "Producer | Singer", [lyric_row(), lyric_row("Divergent fixture")], proofs
    )
    assert result is None and conflict


def test_discovery_uses_role_proof_only_after_direct_source_does_not_supply_text(tmp_path):
    def respond(request):
        if request.url.host == "lrclib.net":
            return httpx.Response(200, json=[lyric_row()])
        if request.url.path == "/api/search/multi":
            song = {**proof(), "id": 123, "title": "Song", "url": metadata()["credit_binding_url"]}
            return httpx.Response(
                200, json={"response": {"sections": [{"type": "song", "hits": [{"result": song}]}]}}
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        http = PacedHTTP(tmp_path, client)
        http.interval = 0
        result = discover_candidate("Song", "Producer | Singer", http)
    assert result["source"] == "LRCLIB"
    assert result["source_metadata"]["credit_binding_provider"] == "GENIUS"
    assert not audit_saved_result({"title": "Song", "artist": "Producer | Singer"}, result)[
        "text_quality_flags"
    ]
