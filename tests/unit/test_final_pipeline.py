import hashlib
import json
import sqlite3
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from chart_observatory import final_pipeline as final


def spotify_html(ranks=(1, 2), day="2026/11/14"):
    rows = "".join(
        f'<tr><td>{rank}</td><td>=</td><td><a href="../artist/a.html">Artist</a>'
        f' - <a href="../track/native{rank}.html">Song {rank}</a></td>'
        "<td>3</td><td>1</td><td>x</td><td>1,234</td></tr>"
        for rank in ranks
    )
    return f"<h1>Spotify Daily Chart - Brazil - {day}</h1><table>{rows}</table>"


def test_preserves_native_position_identity_and_streams():
    period, rows = final.parse_chart(
        spotify_html(), "SPOTIFY", today=date(2026, 11, 16), top_n=1, max_age=4
    )
    assert period == "2026-11-14"
    assert rows == [
        dict(position=1, title="Song 1", artist="Artist", native_id="native1", streams=1234)
    ]


@pytest.mark.parametrize(
    "html",
    [
        spotify_html(day="2026/10/01"),
        spotify_html(day="2026/11/17"),
        spotify_html(ranks=(1, 3)),
        spotify_html(ranks=(1, 1)),
        "<table></table>",
    ],
)
def test_rejects_stale_future_missing_and_duplicate_positions(html):
    with pytest.raises(ValueError):
        final.parse_chart(html, "SPOTIFY", today=date(2026, 11, 16), top_n=200, max_age=4)


def test_discovers_only_country_charts():
    html = (
        '<a href="country/br_daily.html">Brazil</a>'
        '<a href="country/global_daily.html">Global</a>'
        '<a href="country/br_weekly.html">Weekly</a>'
        '<a href="https://example.com/country/us_daily.html">Other</a>'
    )
    assert final.chart_links(html, "SPOTIFY") == {
        "BR": "https://kworb.net/spotify/country/br_daily.html"
    }


def test_import_reuses_text_reference_and_rejects_name_only_and_corruption(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    body = store / "text.txt"
    body.write_bytes(b"complete original transcription")
    result = dict(text_path=str(body), text_sha256=hashlib.sha256(body.read_bytes()).hexdigest())
    with sqlite3.connect(store / "acquisition.sqlite") as source:
        source.execute("CREATE TABLE tasks(identity TEXT,payload TEXT,result TEXT)")
        for key, artist in [
            ("recording:1", "Artist"),
            ("different:id", "Artist"),
            ("recording:2", "Other"),
        ]:
            source.execute(
                "INSERT INTO tasks VALUES (?,?,?)",
                (key, json.dumps(dict(title="Song", artist=artist)), json.dumps(result)),
            )
    with final.catalog(tmp_path / "final") as db:
        for key in ("recording:1", "recording:2"):
            final.add_song(db, key, dict(title="Song", artist="Artist"))
        assert final.import_store(db, store, tmp_path) == 1
        adopted = json.loads(
            db.execute("SELECT result FROM songs WHERE id='recording:1'").fetchone()[0]
        )
        assert adopted["text_path"] == str(body)
        assert db.execute("SELECT result FROM songs WHERE id='recording:2'").fetchone()[0] is None
        db.execute("UPDATE songs SET result=NULL")
        body.write_bytes(b"corrupt")
        assert final.import_store(db, store, tmp_path) == 0
    assert not (tmp_path / "final/texts").exists()


def test_catalog_excludes_simultaneous_writer(tmp_path):
    with final.catalog(tmp_path), pytest.raises(RuntimeError, match="another final pipeline"):  # noqa: SIM117
        with final.catalog(tmp_path):
            pytest.fail("second owner acquired exclusive lock")


def test_vertex_without_evidence_exports_draft_only(tmp_path):
    with final.catalog(tmp_path / "final") as db:
        report = final.prepare_vertex(db, tmp_path / "final", tmp_path)
        assert report["max_songs"] == 150_000
        assert report["paid_calls"] == report["uploads"] == report["prepared_songs"] == 0
        assert not report["ready"]
        assert not (tmp_path / report["output"] / "requests.jsonl").exists()


def test_limit_above_hard_cap_rejected_before_io():
    with pytest.raises(SystemExit) as error:
        final.main(["lyrics", "--limit", "150001"])
    assert error.value.code == 2


def mock_vertex_inputs(tmp_path, monkeypatch):
    from chart_observatory import research_flow as flow
    from chart_observatory.lyrics import classification_gate, research_vertex_payload

    audit = tmp_path / "audit"
    audit.mkdir()
    editions = [str(uuid4()) for _ in range(3)]
    state = {e: "fingerprint" for e in editions}
    requests = [
        dict(
            edition_id=e, request_id="request-" + e, text_sha256=final.digest(b"full approved text")
        )
        for e in editions
    ]
    source = tmp_path / "prepared.jsonl"
    source.write_text("\n".join(json.dumps(r) for r in requests), encoding="utf-8")
    (audit / "preparatory-table.csv").write_text(
        "request_id,document_id,prepared\n"
        + "".join(f"{r['request_id']},{r['edition_id']},True\n" for r in requests),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        flow, "require_research_stage", lambda *a, **kw: dict(canonical_state=state)
    )
    monkeypatch.setattr(
        flow,
        "read_canonical_documents",
        lambda p, ids: {str(e): SimpleNamespace(text="full approved text") for e in ids},
    )
    monkeypatch.setattr(flow, "canonical_fingerprint", lambda d: "fingerprint")
    monkeypatch.setattr(flow, "require_vertex_rights", lambda *a: None)
    monkeypatch.setattr(
        classification_gate.ClassificationGate,
        "load",
        lambda: SimpleNamespace(assess=lambda d: SimpleNamespace(eligible=True)),
    )
    monkeypatch.setattr(
        research_vertex_payload,
        "vertex_payload",
        lambda r: dict(
            request=dict(contents=[dict(text="full approved text")]), dispatch_target={}
        ),
    )
    return audit, source, requests


def test_preparation_cap_is_cumulative_and_idempotent(tmp_path, monkeypatch):
    audit, source, requests = mock_vertex_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(final, "MAX_SONGS", 2)
    root = tmp_path / "catalog"
    with final.catalog(root) as db:
        for _ in range(2):
            report = final.prepare_vertex(db, root, tmp_path, audit=audit, prepared=source)
            assert report["prepared_songs"] == 2
            assert db.execute("SELECT count(*) FROM prepared").fetchone()[0] == 2
        source.write_text(json.dumps(requests[2]), encoding="utf-8")
        report = final.prepare_vertex(db, root, tmp_path, audit=audit, prepared=source)
        assert report["prepared_songs"] == 0
        assert not report["ready"]


def test_preparation_rejects_changed_text_without_publishing_batch(tmp_path, monkeypatch):
    audit, source, requests = mock_vertex_inputs(tmp_path, monkeypatch)
    requests[1]["text_sha256"] = "wrong-hash"
    source.write_text("\n".join(json.dumps(r) for r in requests), encoding="utf-8")
    root = tmp_path / "catalog"
    with final.catalog(root) as db:
        with pytest.raises(ValueError, match="canonical text"):
            final.prepare_vertex(db, root, tmp_path, audit=audit, prepared=source)
        assert db.execute("SELECT count(*) FROM prepared").fetchone()[0] == 0
        assert not list(root.glob("vertex/*/requests.jsonl"))


def test_staging_is_referenced_without_copy_and_mutation_is_rejected(tmp_path):
    path = tmp_path / "staging.sqlite"
    sha = final.digest(b"entire preserved transcription")
    source_result = json.dumps(dict(source="LRCLIB", text_sha256=sha))
    payload = dict(title="Song", artist="Artist")
    with sqlite3.connect(path) as source:
        source.executescript("""
            CREATE TABLE quota_lyric_staging_runs(id TEXT);
            CREATE TABLE quota_lyric_staging_blobs(sha256 TEXT,body TEXT);
            CREATE TABLE quota_lyric_staging_candidates(
                candidate_id TEXT,payload TEXT,text_sha256 TEXT,
                run_id TEXT,source_result TEXT,audit TEXT);
        """)
        source.execute("INSERT INTO quota_lyric_staging_runs VALUES ('frozen')")
        source.execute(
            "INSERT INTO quota_lyric_staging_blobs VALUES (?,?)",
            (sha, "entire preserved transcription"),
        )
        source.execute(
            "INSERT INTO quota_lyric_staging_candidates VALUES (?,?,?,?,?,?)",
            ("recording", json.dumps(payload), sha, "frozen", source_result, "{}"),
        )
    root = tmp_path / "catalog"
    with final.catalog(root) as db:
        final.add_song(db, "recording", payload)
        assert final.import_staging(db, path, "frozen", tmp_path) == 1
        result = json.loads(db.execute("SELECT result FROM songs").fetchone()[0])
        assert "source" not in result
        assert final.read_result(result, tmp_path)[1] == "entire preserved transcription"
        assert not (root / "texts").exists()
        with sqlite3.connect(path) as source:
            source.execute("UPDATE quota_lyric_staging_blobs SET body='changed'")
        with pytest.raises(ValueError, match="missing or changed"):
            final.read_result(result, tmp_path)
