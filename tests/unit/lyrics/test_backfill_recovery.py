import json
import threading
import time

import polars as pl

import chart_observatory.lyrics.lyrics_backfill as backfill
from chart_observatory.lyrics.lyrics_backfill import (
    _load_completed,
    _normalize_song_key,
    is_valid_lyrics_record,
)


def test_only_valid_found_records_are_completed(tmp_path):
    output = tmp_path / "lyrics.jsonl"
    output.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "song_id": "found",
                        "title": "A",
                        "artist": "B",
                        "lyrics_status": "FOUND",
                        "lyrics_source": "GENIUS",
                        "original_lyrics": "line one\nline two",
                    }
                ),
                json.dumps(
                    {
                        "song_id": "missing",
                        "title": "C",
                        "artist": "D",
                        "lyrics_status": "MISSING",
                    }
                ),
                json.dumps(
                    {
                        "song_id": "error",
                        "title": "E",
                        "artist": "F",
                        "lyrics_status": "PROVIDER_ERROR",
                    }
                ),
                "not-json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ids, keys = _load_completed(output)

    assert ids == {"found"}
    assert keys == {_normalize_song_key("A", "B")}


def test_valid_record_rejects_missing_empty_and_unknown_source():
    valid = {
        "song_id": "found",
        "lyrics_status": "FOUND",
        "lyrics_source": "LETRAS",
        "original_lyrics": "lyrics",
    }

    assert is_valid_lyrics_record(valid)
    assert not is_valid_lyrics_record({**valid, "lyrics_source": "UNKNOWN"})
    assert not is_valid_lyrics_record({**valid, "lyrics_status": "MISSING"})
    assert not is_valid_lyrics_record({**valid, "original_lyrics": "   "})


def test_valid_record_accepts_google_manual_source():
    record = {
        "song_id": "manual-google",
        "lyrics_status": "FOUND",
        "lyrics_source": "GOOGLE_MANUAL",
        "original_lyrics": "line one\nline two",
    }

    assert is_valid_lyrics_record(record)


def test_missing_song_result_is_not_insertable():
    assert is_valid_lyrics_record({"lyrics_status": "MISSING"}) is False


def test_resume_separates_interrupted_line_from_new_records(tmp_path):
    output = tmp_path / "lyrics.jsonl"
    interrupted = b'{"song_id":"partial","original_lyrics":"interrupted'
    output.write_bytes(interrupted)
    backfill._ensure_append_boundary(output)
    next_record = {
        "song_id": "new",
        "title": "New",
        "artist": "Artist",
        "lyrics_status": "FOUND",
        "lyrics_source": "GENIUS",
        "original_lyrics": "Complete original lyric",
    }
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(next_record) + "\n")
    ids, _keys = backfill._load_completed(output)
    assert ids == {"new"}
    assert output.read_bytes().startswith(interrupted + b"\n")


def test_recovery_reads_baseline_without_writing_it(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.jsonl"
    content = (
        json.dumps(
            {
                "song_id": "done",
                "title": "Song",
                "artist": "Artist",
                "lyrics_status": "FOUND",
                "lyrics_source": "GENIUS",
                "original_lyrics": "Existing original text",
            }
        )
        + "\n"
    )
    baseline.write_text(content, encoding="utf-8")
    output = tmp_path / "new" / "recovery.jsonl"

    def pending(**kwargs):
        assert "done" in kwargs["completed_ids"]
        return []

    monkeypatch.setattr(backfill, "_load_tracks", pending)
    backfill.run_full_automation(output_path=output, skip_gemini=True, completed_paths=(baseline,))
    assert baseline.read_text(encoding="utf-8") == content
    assert not output.exists()


def test_suspended_source_does_not_block_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill, "load_suspended_sources", lambda: frozenset({"LETRAS"}))
    output = tmp_path / "lyrics.jsonl"
    output.write_text(
        json.dumps(
            {
                "song_id": "retry",
                "title": "Song",
                "artist": "Artist",
                "lyrics_status": "FOUND",
                "lyrics_source": "LETRAS",
                "original_lyrics": "old text",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert backfill._load_completed(output) == (set(), set())


def test_suspended_provider_is_skipped_and_fallback_used(monkeypatch):
    monkeypatch.setattr(backfill, "load_suspended_sources", lambda: frozenset({"LETRAS"}))
    calls = []

    class Provider:
        def __init__(self, name, result):
            self.name, self.result = name, result

        def fetch(self, *_args):
            calls.append(self.name)
            return self.result

    engine = backfill.LyricsEngine(skip_gemini=True)
    clients = {
        "GENIUS": Provider("GENIUS", None),
        "LETRAS": Provider("LETRAS", "bad"),
        "LRCLIB": Provider("LRCLIB", ("verified text", {"id": 1})),
        "LYRICS_OVH": Provider("LYRICS_OVH", None),
    }
    monkeypatch.setattr(engine, "_get_clients", lambda: clients)
    result = engine.find_lyrics("Song", "Artist")
    assert result == ("verified text", "LRCLIB", {"id": 1})
    assert calls == ["GENIUS", "LRCLIB"]


def test_automation_writes_only_found_records_and_bounds_active_workers(tmp_path, monkeypatch):
    catalog = tmp_path / "track_master.parquet"
    output = tmp_path / "lyrics.jsonl"
    pl.DataFrame(
        {
            "canonical_track_id": ["found-id", "missing-id", "found-id-2"],
            "title": ["Found", "Missing", "Found two"],
            "artist_names": [["Artist"], ["Artist"], ["Artist"]],
        }
    ).write_parquet(catalog)

    class FakeEngine:
        active = 0
        max_active = 0
        lock = threading.Lock()

        def __init__(self, **_kwargs):
            pass

        def find_lyrics(self, title, _artist):
            with self.lock:
                type(self).active += 1
                type(self).max_active = max(type(self).max_active, type(self).active)
            time.sleep(0.01)
            with self.lock:
                type(self).active -= 1
            if title == "Missing":
                return None, None, {}
            return "line one\nline two", "GENIUS", {}

        def annotate(self, **_kwargs):
            return None

    monkeypatch.setattr(backfill, "LyricsEngine", FakeEngine)

    backfill.run_full_automation(
        tracks_path=catalog,
        output_path=output,
        workers=2,
        include_all=False,
        skip_gemini=True,
    )

    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert {record["song_id"] for record in records} == {"found-id", "found-id-2"}
    assert all(record["lyrics_status"] == "FOUND" for record in records)
    assert FakeEngine.max_active <= 2
