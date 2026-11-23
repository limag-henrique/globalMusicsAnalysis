"""Resumption must not repeat paused work or lose the evidence used by a batch."""

import json
import sqlite3

from chart_observatory.recovery_batches import RetrySchedule, freeze_batch


def test_retry_survives_restart_and_changed_inputs_can_run(tmp_path):
    path = tmp_path / "state.sqlite"
    with sqlite3.connect(path) as db:
        schedule = RetrySchedule(db, minimum_seconds=60)
        schedule.record("song", "input-v1", "access_failed_rate_limited", now=100)
    with sqlite3.connect(path) as db:
        schedule = RetrySchedule(db, minimum_seconds=60)
        assert not schedule.due("song", "input-v1", now=159)
        assert schedule.due("song", "input-v1", now=160)
        assert schedule.due("song", "input-v2", now=101)
        schedule.record("song", "input-v1", "access_failed_rate_limited", now=160)
        assert not schedule.due("song", "input-v1", now=279)
        schedule.record("song", "input-v1", None, now=280)
        assert schedule.due("song", "input-v1", now=280)


def test_frozen_batch_retains_text_and_reports_missing_sources(tmp_path):
    import hashlib

    root = tmp_path / "worker"
    root.mkdir()
    text = root / "text.txt"
    text.write_text("verse one\nverse two", encoding="utf-8")
    expected = hashlib.sha256(text.read_bytes()).hexdigest()
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE supplemental_lyric_ledger(id INTEGER, song_id TEXT)")
    db.execute("INSERT INTO supplemental_lyric_ledger VALUES (1,'song')")
    db.execute("""CREATE TABLE supplemental_lyrics(song_id TEXT,text_path TEXT,
        text_sha256 TEXT,result_json TEXT,validation_json TEXT)""")
    result = {"http_evidence": [{"cache_path": str(root / "missing.json"), "status": 200}]}
    db.execute("INSERT INTO supplemental_lyrics VALUES (?,?,?,?,?)",
               ("song", str(text), expected, json.dumps(result), '{}'))
    manifest = freeze_batch(db, root, 1, 1, project=tmp_path)
    text.write_text("overwritten live text", encoding="utf-8")
    payload = json.loads(manifest.read_text())
    saved = manifest.parent / "texts" / f"{expected}.txt"
    assert saved.read_text(encoding="utf-8") == "verse one\nverse two"
    assert payload["ledger_range"] == [1, 1]
    assert payload["candidate_count"] == 1
    assert payload["source_replay_complete"] is False
    assert payload["scientific_approval"] is False
    assert payload["missing_evidence"][0]["song_id"] == "song"


def test_acquisition_cli_defers_a_failed_retry_after_restart(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "scheduled_acquisition", Path(__file__).parents[2] /
        "scripts/acquire_and_validate_supplemental_lyrics.py",
    )
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    queue = tmp_path / "queue.jsonl"
    queue.write_text(json.dumps(dict(song_id="song", title="Song", artist_credit="Artist",
                                    state="new_requires_acquisition")) + "\n")
    calls = []

    def recover(*args, **kwargs):
        calls.append(True)
        return dict(status="not_found_or_unverified", source_errors=["source:429"])

    monkeypatch.setattr(worker, "recover_with_fallback", recover)
    arguments = ["--root", str(tmp_path / "worker"), "--queue", str(queue),
                 "--cache-only", "--retry-rate-limited"]
    worker.main(arguments)
    worker.main(arguments)
    report = json.loads((tmp_path / "worker/acquisition-report.json").read_text())
    assert len(calls) == 1
    assert report["attempts_this_invocation"] == 0
    assert report["deferred_retries"] == 1
    assert report["unresolved_total"] == 1
