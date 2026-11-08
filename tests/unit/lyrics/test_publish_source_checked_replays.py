import hashlib
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from chart_observatory.lyrics.recovery_web import CachedRecoveryHTTP


@pytest.mark.parametrize("case", ["valid", "corrupt_response", "existing_text"])
def test_publication_requires_reproducible_source_and_current_binding(tmp_path, monkeypatch, case):
    scripts = Path(__file__).resolve().parents[3] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "source_checked_publisher_test", scripts / "publish_source_checked_replays.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    body = "\n".join(f"Original fixture verse number {i}" for i in range(25))
    row = dict(id=12, trackName="Song", artistName="Artist", plainLyrics=body)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[row]))
    ) as client:
        http = CachedRecoveryHTTP(tmp_path / "cache", client)
        http.get("https://lrclib.net/api/search?q=fixture")
        trace = list(http.trace)
    payload = dict(recording_id="SPOTIFY:fixture", title="Song", artist="Artist")
    result = dict(
        text=body,
        source="LRCLIB",
        generated_by_ai=False,
        http_evidence=trace,
        source_metadata=dict(id=12, observed_title="Song", observed_artist="Artist"),
    )
    proposal = dict(payload=payload, result=result, replay_kind="missing_text")
    proposals = tmp_path / "proposals"
    proposals.mkdir()
    (proposals / "positive.json").write_text(json.dumps(proposal), encoding="utf-8")
    (proposals / "negative.outcome.json").write_text('{"outcome":"not_found"}')
    old = {}
    if case == "corrupt_response":
        path = Path(trace[0]["cache_path"])
        record = json.loads(path.read_text(encoding="utf-8"))
        record["body"] = "[]"
        path.write_text(json.dumps(record), encoding="utf-8")
    if case == "existing_text":
        old = dict(text_sha256=hashlib.sha256(b"existing").hexdigest(), text_path="existing.txt")
    destination = tmp_path / "published"
    current = {"SPOTIFY:fixture": (payload, old)}
    counts, checks = module.publish(proposals, current, destination, tmp_path)
    assert all(not r["approval"] for r in checks)
    assert current["SPOTIFY:fixture"][1] == old
    if case == "valid":
        assert counts["published"] == 1
        published = list(destination.glob("*.json"))
        assert (
            len(published) == 1 and json.loads(published[0].read_text())["result"]["text"] == body
        )
        again, _ = module.publish(proposals, current, destination, tmp_path)
        assert again["already_published"] == 1
    else:
        assert counts["held_for_review"] == 1
        assert not list(destination.glob("*.json"))
