import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "responses,expected_calls,expected_waits,min_delay",
    [
        ([{"status": 504, "resolved_progress": 10}] * 3 + [None], 4, 3, 60),
        ([{"status": 504, "resolved_progress": 0}] * 3, 3, 2, 60),
        ([{"status": 403, "resolved_progress": 10}], 1, 0, 0),
        ([{"status": 429, "resolved_progress": 10}] * 3, 3, 2, 900),
    ],
)
def test_native_retry_distinguishes_progress_access_denial_and_rate_limit(
    tmp_path, monkeypatch, responses, expected_calls, expected_waits, min_delay
):
    root = Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "native_metadata_retry_worker", root / "scripts/collect_native_spotify_metadata.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.STATE = tmp_path
    responses = iter(responses)
    calls = []
    waits = []

    def collect(base, deadline):
        calls.append(base)
        return next(responses)

    monkeypatch.setattr(module, "collect", collect)
    monkeypatch.setattr(
        module, "wait_until", lambda deadline: waits.append(deadline - module.time.time())
    )
    module.run(tmp_path)
    assert len(calls) == expected_calls and len(waits) == expected_waits
    assert all(delay >= min_delay - 1 for delay in waits)


@pytest.mark.parametrize("status", [200, 404])
def test_duration_refresh_is_scoped_and_preserves_old_proof_on_failure(
    tmp_path, monkeypatch, status
):
    import json
    import sqlite3

    import httpx

    root = Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "native_duration_worker", root / "scripts/collect_native_spotify_metadata.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CACHE = tmp_path / "cache"
    module.STATE = tmp_path / "state"
    module.CACHE.mkdir()
    module.STATE.mkdir()
    base = tmp_path / "base"
    base.mkdir()
    (base / "combined.jsonl").write_text(
        "\n".join(json.dumps(dict(candidate_id=key)) for key in ["SPOTIFY:one", "SPOTIFY:two"]),
        encoding="utf-8",
    )
    old = dict(
        status=200,
        source_url="https://open.spotify.com/embed/track/one",
        metadata=dict(uri="spotify:track:one", title="Song", artist="Artist"),
    )
    with sqlite3.connect(module.CACHE / "native-metadata.sqlite") as db:
        db.execute("CREATE TABLE evidence(candidate_id TEXT PRIMARY KEY, proof TEXT NOT NULL)")
        db.execute("INSERT INTO evidence VALUES (?,?)", ("SPOTIFY:one", json.dumps(old)))
    calls = []
    entity = dict(
        uri="spotify:track:one",
        type="track",
        title="Song",
        duration=200506,
        artists=[dict(name="Artist")],
    )
    data = dict(props=dict(pageProps=dict(state=dict(data=dict(entity=entity)))))
    html = '<script id="__NEXT_DATA__">' + json.dumps(data) + "</script>"

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(status, text=html)

    real_client = httpx.Client
    monkeypatch.setattr(
        module.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    module.collect(base, candidate_ids={"SPOTIFY:one"}, refresh_duration=True)
    assert calls == ["https://open.spotify.com/embed/track/one"]
    with sqlite3.connect(module.CACHE / "native-metadata.sqlite") as db:
        saved = json.loads(
            db.execute(
                "SELECT proof FROM evidence WHERE candidate_id=?", ("SPOTIFY:one",)
            ).fetchone()[0]
        )
    if status == 200:
        assert saved["metadata"]["duration_ms"] == 200506
    else:
        assert saved == old
    archived = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (module.CACHE / "native-proof-batches").glob("*.json")
    ]
    assert any(batch.get("SPOTIFY:one") == old for batch in archived)
