import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "variant_review",
    Path(__file__).resolve().parents[3] / "scripts/prepare_lyric_variant_review.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def cached(tmp_path, *, digest=None):
    body = json.dumps(
        [
            dict(
                id=1, trackName="Song", artistName="Artist", plainLyrics="First verse", duration=200
            ),
            dict(
                id=2,
                trackName="Song",
                artistName="Artist",
                plainLyrics="Different verse",
                duration=200,
            ),
            dict(
                id=3,
                trackName="Song (Live)",
                artistName="Artist",
                plainLyrics="Live verse",
                duration=200,
            ),
            dict(
                id=4,
                trackName="Song",
                artistName="Another artist",
                plainLyrics="Cover verse",
                duration=200,
            ),
        ]
    )
    path = tmp_path / "response.json"
    path.write_text(
        json.dumps(
            dict(
                url="https://lrclib.net/api/search",
                body=body,
                body_sha256=digest or hashlib.sha256(body.encode()).hexdigest(),
                retrieved_at="2026-11-15T00:00:00+00:00",
            )
        ),
        encoding="utf8",
    )
    return path


def test_review_preserves_distinct_editions_without_admitting_covers_or_live(tmp_path):
    texts = {}
    values = module.read_variants(
        dict(cache_path=str(cached(tmp_path))), dict(title="Song", artist="Artist"), texts
    )
    assert {value["provider_record_id"] for value in values} == {1, 2}
    assert len(texts) == 2
    assert all("approved" not in value for value in values)


def test_review_rejects_corrupted_original_response(tmp_path):
    with pytest.raises(ValueError, match="checksum"):
        module.read_variants(
            dict(cache_path=str(cached(tmp_path, digest="0" * 64))),
            dict(title="Song", artist="Artist"),
            {},
        )
