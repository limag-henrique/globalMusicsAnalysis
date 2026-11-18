import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from chart_observatory.supplemental_series import (
    compute_song_id,
    import_verified_provider_series,
    parse_title_and_artist,
)


def test_parse_and_compute_song_id_preserves_versions():
    live = parse_title_and_artist("Track A (Live)", "Artist X")
    studio = parse_title_and_artist("Track A", "Artist X")
    assert live["version_tags"] == ["Live"]
    assert studio["version_tags"] == []
    assert compute_song_id("CAVCA", live["title"], live["artist_credit"], version_tags=live["version_tags"]) != compute_song_id(
        "CAVCA", studio["title"], studio["artist_credit"], version_tags=studio["version_tags"]
    )
    assert compute_song_id("CIRCLE_CHART", "Track A", "Artist X", native_song_id="123") == "CIRCLE_CHART:123"


def test_import_verified_provider_series_excludes_review_only(tmp_path: Path):
    base = tmp_path / "provider_series"
    verified = base / "cavca-test-2021"
    verified.mkdir(parents=True)
    raw_file = verified / "source.txt"
    raw_file.write_bytes(b"ok")
    sha = hashlib.sha256(b"ok").hexdigest()
    rows = [
        {
            "series_id": "CAVCA_TEST_2021",
            "provider_code": "CAVCA",
            "chart_family": "Golden Mic",
            "publisher_country_code": "CN",
            "chart_market_code": "CN",
            "reporting_year": 2021,
            "position": 1,
            "published_rank": "1",
            "title": "Song A",
            "artist_credit": "Artist 1",
            "source_sha256": sha,
        },
        {
            "series_id": "CAVCA_TEST_2021",
            "provider_code": "CAVCA",
            "chart_family": "Golden Mic",
            "publisher_country_code": "CN",
            "chart_market_code": "CN",
            "reporting_year": 2021,
            "position": 2,
            "published_rank": "2",
            "title": "Song A (Remix)",
            "artist_credit": "Artist 1",
            "source_sha256": sha,
        },
    ]
    (verified / "rankings.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    (verified / "manifest.json").write_text(
        json.dumps(
            {
                "series_id": "CAVCA_TEST_2021",
                "source_artifacts": [{"local_path": str(raw_file), "sha256": sha}],
            }
        ),
        encoding="utf-8",
    )

    review = base / "tme-uni-cn-2023-high-score-review"
    review.mkdir(parents=True)
    (review / "candidate-rankings.jsonl").write_text("{}\n", encoding="utf-8")
    (review / "manifest.json").write_text(
        json.dumps({"series_id": "TME_2023_REVIEW"}), encoding="utf-8"
    )

    db_path = tmp_path / "supplemental.sqlite"
    summary = import_verified_provider_series(base, db_path)
    assert summary["series_count"] == 1
    assert summary["total_supplemental_positions"] == 2
    assert summary["total_normalized_identity_keys"] == 2
    assert summary["schema_version"] == "supplemental-series-denominators-v3"
    assert len(summary["review_only_series"]) == 1
    assert summary["merged_into_150k_spotify_youtube_selection"] is False

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT count(*) FROM supplemental_songs").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM supplemental_memberships").fetchone()[0] == 2
    conn.close()
