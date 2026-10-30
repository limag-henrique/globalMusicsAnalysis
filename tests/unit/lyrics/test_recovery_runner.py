import errno
import importlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    return importlib.import_module("recover_reviewed_lyrics")


def test_interrupted_last_ledger_line_is_preserved_before_resume(runner, tmp_path):
    path = tmp_path / "acquisition.jsonl"
    raw = b'{"status":"not_found"}\n{"status":'
    path.write_bytes(raw)
    assert runner.read_recovery_ledger(path) == [{"status": "not_found"}]
    assert path.read_bytes() == b'{"status":"not_found"}\n'
    assert next(tmp_path.glob("*.interrupted-*")).read_bytes() == raw


def test_corruption_inside_ledger_fails_without_changing_it(runner, tmp_path):
    path = tmp_path / "acquisition.jsonl"
    raw = b'{"status":"not_found"}\nbroken\n'
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        runner.read_recovery_ledger(path)
    assert path.read_bytes() == raw


def test_storage_failure_does_not_consume_entire_target_iterator(runner):
    consumed = []

    def rows():
        for number in range(100):
            consumed.append(number)
            yield number

    def fail(_):
        raise OSError(errno.ENOSPC, "disk full")

    with ThreadPoolExecutor(max_workers=2) as pool, pytest.raises(OSError):
        list(runner.bounded_results(pool, fail, rows(), 2))
    assert len(consumed) == 2


def test_same_title_artist_does_not_merge_distinct_recording_identities(runner):
    rows = [{"document_id": str(i), "track_id": str(i), "title": "Song",
             "artist": "Artist", "lyrics_hash": "a" * 64} for i in range(2)]
    assert len(runner.select_recovery_targets(rows, set(), 10)) == 2


def test_deduplication_preserves_all_original_document_bindings(runner):
    rows = [{"document_id": str(i), "track_id": "one-recording", "title": "Song",
             "artist": "Artist", "lyrics_hash": "a" * 64} for i in range(2)]
    selected = runner.select_recovery_targets(rows, set(), 10)
    assert len(selected) == 1
    assert {b["document_id"] for b in selected[0]["original_bindings"]} == {"0", "1"}
