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


def test_missing_song_result_is_not_insertable():
    assert is_valid_lyrics_record({"lyrics_status": "MISSING"}) is False


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
