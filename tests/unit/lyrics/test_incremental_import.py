import importlib
from pathlib import Path

import pytest


@pytest.fixture
def incremental(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    return importlib.import_module("import_lyrics_incremental")


def test_partial_appended_line_is_not_consumed(incremental, tmp_path):
    source = tmp_path / "lyrics.jsonl"
    source.write_bytes(b'{"song": 1}\n{"song":')
    content, offset = incremental.read_complete_batch(source, 0)
    assert content == b'{"song": 1}\n'
    with source.open("ab") as handle:
        handle.write(b" 2}\n")
    content, end = incremental.read_complete_batch(source, offset)
    assert content == b'{"song": 2}\n'
    assert end == source.stat().st_size


def test_checkpoint_retries_transient_windows_file_lock(incremental, tmp_path, monkeypatch):
    path = tmp_path / "checkpoint.json"
    replace = Path.replace
    attempts = []

    def locked_twice(self, target):
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError("temporary file lock")
        return replace(self, target)

    monkeypatch.setattr(Path, "replace", locked_twice)
    monkeypatch.setattr(incremental.time, "sleep", lambda _: None)
    incremental.write_state(path, {"offset": 20})
    assert '"offset": 20' in path.read_text(encoding="utf-8")
    assert len(attempts) == 3


def test_failed_database_write_does_not_advance_checkpoint(incremental, tmp_path, monkeypatch):
    from contextlib import nullcontext

    source = tmp_path / "lyrics.jsonl"
    source.write_bytes(b"{}\n")
    checkpoint = tmp_path / "checkpoint.json"
    monkeypatch.setattr(incremental, "Session", lambda _: nullcontext(None))

    def fail(*_args):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(incremental, "import_legacy_api_lyrics", fail)
    with pytest.raises(RuntimeError):
        incremental.import_next(None, source, checkpoint)
    assert not checkpoint.exists()
    assert not checkpoint.with_suffix(".batch.jsonl").exists()
    assert source.read_bytes() == b"{}\n"
