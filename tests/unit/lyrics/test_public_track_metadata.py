import json

from scripts.resolve_public_track_metadata import kworb_metadata, spotify_entity


def test_public_embed_requires_exact_uri_and_does_not_return_session_data():
    entity = dict(uri="spotify:track:abc", type="track", title="Song", artists=[{"name": "Artist"}])
    data = {
        "props": {
            "pageProps": {
                "state": {
                    "data": {"entity": entity},
                    "settings": {"session": {"accessToken": "do-not-persist"}},
                }
            }
        }
    }
    html = f'<script id="__NEXT_DATA__">{json.dumps(data)}</script>'
    assert spotify_entity(html, "different") is None
    result = spotify_entity(html, "abc")
    assert result == dict(title="Song", artist="Artist", uri="spotify:track:abc")
    assert "do-not-persist" not in json.dumps(result)


def test_kworb_archive_extracts_explicit_track_metadata_without_reading_chart_rows():
    html = """<div class="subcontainer" id="mainmenu">Navigation</div>
    <div class="subcontainer"><span class="pagetitle">Spotify Chart History</span><br>
    Title: Song - Live<br>
    Artists: <a href="../artist/4xJWG181b96Z3nxVLGr3Ct.html">Artist</a>,
    <a href="../artist/3CWP6fXUDZPG72CAiEOBTy.html">Guest</a><br>
    <div class="daily"><table><tr><td>Other text</td></tr></table></div></div>"""
    assert kworb_metadata(html) == dict(title="Song - Live", artist="Artist | Guest")
    assert kworb_metadata("<div>Generic page</div>") is None


def test_public_embed_keeps_exact_track_duration_without_session_fields():
    entity = dict(uri="spotify:track:abc", type="track", title="Song",
                  duration=200506, artists=[{"name": "Artist"}])
    data = dict(props=dict(pageProps=dict(state=dict(data=dict(entity=entity)))))
    html = '<script id="__NEXT_DATA__">' + json.dumps(data) + '</script>'
    assert spotify_entity(html, "abc")["duration_ms"] == 200506
    entity["duration"] = True
    data["props"]["pageProps"]["state"]["data"]["entity"] = entity
    html = '<script id="__NEXT_DATA__">' + json.dumps(data) + '</script>'
    assert "duration_ms" not in spotify_entity(html, "abc")
