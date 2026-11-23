"""Bounded retry fairness and concurrency safeguards for supplemental recovery."""
import importlib.util
import sqlite3
from pathlib import Path

spec = importlib.util.spec_from_file_location("supplemental_acquisition", Path(__file__).resolve().parents[2] / "scripts/acquire_and_validate_supplemental_lyrics.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_bounded_retry_does_not_starve_tail():
    conn = sqlite3.connect(":memory:")
    module.init_db(conn)
    queue = [{"song_id": str(i)} for i in range(6)]
    visited = []
    for _ in range(3):
        selected = module.fair_retry_order(conn, queue)[:2]
        visited.extend(item["song_id"] for item in selected)
        for item in selected:
            conn.execute("INSERT INTO supplemental_lyric_ledger(song_id,reason,recorded_at_utc) VALUES (?,?,?)", (item["song_id"], "blocked", "2026-11-19T00:00:00Z"))
    assert visited == ["0", "1", "2", "3", "4", "5"]


def test_retry_ledger_preserves_previous_hash_and_shared_http(tmp_path, monkeypatch):
    root = tmp_path / "run"
    root.mkdir()
    db = sqlite3.connect(root / "supplemental-lyrics.sqlite")
    module.init_db(db)
    db.execute("INSERT INTO supplemental_lyrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("x", "new_requires_acquisition", None, "old-hash", None, None, "unavailable", "access_failed_rate_limited", None, None, None, None, None, "[]", "{}", "{}", "2026-01-01"))
    db.commit()
    db.close()
    queue = tmp_path / "queue.jsonl"
    queue.write_text('{"song_id":"x","state":"new_requires_acquisition","title":"Title","artist_credit":"Artist"}\n', encoding="utf-8")
    with queue.open("a", encoding="utf-8") as stream:
        for sid in ("y", "z"):
            stream.write('{"song_id":"' + sid + '","state":"new_requires_acquisition","title":"Title","artist_credit":"Artist"}\n')
    seen = []
    def recover(title, artist, http, **kwargs):
        seen.append(http)
        return {"status":"not_found_or_unverified", "source_errors":["provider:429"]}
    monkeypatch.setattr(module, "recover_with_fallback", recover)
    module.main(["--root", str(root), "--queue", str(queue), "--retry-rate-limited", "--cache-only", "--workers", "4"])
    db = sqlite3.connect(root / "supplemental-lyrics.sqlite")
    assert db.execute("SELECT previous_sha256,new_sha256 FROM supplemental_lyric_ledger WHERE song_id='x'").fetchone() == ("old-hash", None)
    assert len(seen) == 3
    assert len({id(http) for http in seen}) == 1

    assert db.execute("SELECT text_sha256 FROM supplemental_lyrics WHERE song_id='x'").fetchone()[0] == "old-hash"


def test_shared_http_paces_workers_and_isolates_traces(tmp_path):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    import httpx

    starts = []
    guard = threading.Lock()
    def serve(request):
        with guard:
            starts.append(time.monotonic())
        time.sleep(0.01)
        return httpx.Response(200, text=str(request.url), request=request)
    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        http = module.PacedHTTP(tmp_path, client, interval=0.025)
        def acquire(i):
            http.start_trace()
            http.get(f"https://provider.example/{i}")
            return [event["url"] for event in http.trace]
        began = time.monotonic()
        with ThreadPoolExecutor(max_workers=4) as workers:
            traces = list(workers.map(acquire, range(4)))
        elapsed = time.monotonic() - began
    assert traces == [[f"https://provider.example/{i}"] for i in range(4)]
    assert len(starts) == 4
    assert elapsed >= 3 * 0.025
