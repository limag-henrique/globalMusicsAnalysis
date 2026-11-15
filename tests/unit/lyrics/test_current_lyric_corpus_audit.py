import hashlib
import json

from scripts.audit_current_lyric_corpus import review_queue_record, sha256_file


def test_review_queue_record_is_importable_and_contains_no_lyrics():
    record = review_queue_record(
        "run-123",
        "SPOTIFY:track-1",
        "a" * 64,
        "GENIUS",
        {"quality_state": "acquired_unverified", "flags": ["short_text", "short_text"]},
        {
            "lyrics": "must never be copied",
            "chart_bindings": [
                {"country_code": "BR", "year": 2024, "position": 1, "extra": "omit"},
                {"country_code": "BR", "year": 2025, "position": 4},
            ],
        },
    )

    assert record == {
        "run_id": "run-123",
        "candidate_id": "SPOTIFY:track-1",
        "text_sha256": "a" * 64,
        "provider": "GENIUS",
        "flags": ["short_text"],
        "quality_state": "acquired_unverified",
        "memberships": [
            {"country_code": "BR", "year": 2024, "position": 1},
            {"country_code": "BR", "year": 2025, "position": 4},
        ],
        "decision": "pending_human_review",
        "lyric_text_included": False,
    }
    assert "lyrics" not in json.dumps(record).lower()


def test_sha256_file_streams_exact_bytes(tmp_path):
    path = tmp_path / "review-queue.jsonl"
    path.write_bytes(b'{"candidate_id":"x"}\n')

    assert sha256_file(path) == hashlib.sha256(path.read_bytes()).hexdigest()
