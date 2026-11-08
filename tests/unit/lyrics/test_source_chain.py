import hashlib
import json

import httpx
import pytest

from chart_observatory.lyrics.recovery_web import CachedRecoveryHTTP
from chart_observatory.lyrics.source_chain import verify_source_chain


def evidence(tmp_path, *, provider_title="Song", body="First verse\nRefrain\nRefrain\nLast verse"):
    row = dict(id=1, trackName=provider_title, artistName="Artist", plainLyrics=body)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=[row]))
    ) as client:
        http = CachedRecoveryHTTP(tmp_path / "cache", client)
        http.get("https://lrclib.net/api/search?q=test")
        trace = list(http.trace)
    result = dict(
        source="LRCLIB",
        source_metadata=dict(id=1, observed_title="Song", observed_artist="Artist"),
        http_evidence=trace,
    )
    return result, body


def test_chain_reproduces_full_unicode_text_and_repetitions_without_certifying_audio(tmp_path):
    result, body = evidence(tmp_path, body="日本語のテスト\nيا ليل\nRefrain\nRefrain\nEnding")
    check = verify_source_chain(
        dict(title="Song", artist="Artist"),
        result,
        body,
        hashlib.sha256(body.encode()).hexdigest(),
        tmp_path,
    )
    assert check["status"] == "source_chain_matched"
    assert not check["identity_validated"] and not check["completeness_validated"]
    assert not check["classification_ready"]


def test_same_song_title_is_not_enough_when_provider_identity_differs(tmp_path):
    result, body = evidence(tmp_path, provider_title="Song (Live)")
    check = verify_source_chain(
        dict(title="Song", artist="Artist"),
        result,
        body,
        hashlib.sha256(body.encode()).hexdigest(),
        tmp_path,
    )
    assert check["status"] == "raw_evidence_unresolved"
    assert "provider_identity_mismatch" in check["errors"]


@pytest.mark.parametrize(
    "stored",
    [
        "First verse\nRefrain\nLast verse",
        "Refrain\nRefrain\nLast verse",
        "First verse\nRefrain\nRefrain",
    ],
)
def test_truncated_beginning_middle_or_ending_is_detected(tmp_path, stored):
    result, _ = evidence(tmp_path)
    check = verify_source_chain(
        dict(title="Song", artist="Artist"),
        result,
        stored,
        hashlib.sha256(stored.encode()).hexdigest(),
        tmp_path,
    )
    assert check["status"] == "source_text_difference"


def test_changed_raw_response_is_not_accepted(tmp_path):
    result, body = evidence(tmp_path)
    path = tmp_path / "cache" / next((tmp_path / "cache").glob("*.json")).name
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["body"] = "[]"
    path.write_text(json.dumps(saved), encoding="utf-8")
    check = verify_source_chain(
        dict(title="Song", artist="Artist"),
        result,
        body,
        hashlib.sha256(body.encode()).hexdigest(),
        tmp_path,
    )
    assert check["status"] == "raw_evidence_unresolved"
    assert "raw_response_hash_mismatch" in check["errors"]
