import json

import polars as pl

from chart_observatory.lyrics.lyrics_audit import analyze_lyrics_output


def test_audit_classifies_valid_pending_duplicate_and_malformed_rows(tmp_path):
    catalog = tmp_path / "track_master.parquet"
    output = tmp_path / "lyrics.jsonl"
    report = tmp_path / "audit.csv"
    pl.DataFrame(
        {
            "canonical_track_id": ["found-id", "pending-id"],
            "title": ["Found song", "Pending song"],
            "artist_names": [["Artist A"], ["Artist B"]],
        }
    ).write_parquet(catalog)
    output.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "song_id": "found-id",
                        "title": "Found song",
                        "artist": "Artist A",
                        "lyrics_status": "FOUND",
                        "lyrics_source": "GENIUS",
                        "original_lyrics": "line one\nline two",
                    }
                ),
                json.dumps(
                    {
                        "song_id": "found-id",
                        "title": "Found song",
                        "artist": "Artist A",
                        "lyrics_status": "MISSING",
                    }
                ),
                json.dumps(
                    {
                        "song_id": "pending-id",
                        "title": "Pending song",
                        "artist": "Artist B",
                        "lyrics_status": "PROVIDER_ERROR",
                    }
                ),
                "not-json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = analyze_lyrics_output(catalog, output, report, include_all=False)

    report_text = report.read_text(encoding="utf-8")
    assert summary.valid_found == 1
    assert summary.pending == 1
    assert summary.malformed_lines == 1
    assert summary.duplicate_ids == 1
    assert "FOUND_VALID" in report_text
    assert "PENDING_RETRY" in report_text


def test_audit_does_not_treat_unknown_source_as_valid(tmp_path):
    catalog = tmp_path / "track_master.parquet"
    output = tmp_path / "lyrics.jsonl"
    report = tmp_path / "audit.csv"
    pl.DataFrame(
        {
            "canonical_track_id": ["song-id"],
            "title": ["Song"],
            "artist_names": [["Artist"]],
        }
    ).write_parquet(catalog)
    output.write_text(
        json.dumps(
            {
                "song_id": "song-id",
                "title": "Song",
                "artist": "Artist",
                "lyrics_status": "FOUND",
                "lyrics_source": "UNKNOWN",
                "original_lyrics": "line one\nline two",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = analyze_lyrics_output(catalog, output, report, include_all=False)

    assert summary.valid_found == 0
    assert summary.pending == 1
