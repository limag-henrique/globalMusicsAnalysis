import hashlib

import pytest

from scripts.audit_lyric_db_local_mismatches import exact_replay_record, memberships


def test_exact_replay_requires_byte_hash_and_valid_response_hash():
    body = "line one\nrefrain\nrefrain"
    text_hash = hashlib.sha256(body.encode()).hexdigest()
    evidence_hash = "b" * 64
    payload = {
        "lyrics": "must not be used as a field",
        "chart_bindings": [
            {"country_code": "BR", "year": 2024, "position": 1, "ignored": "x"}
        ],
    }

    record = exact_replay_record(
        "SPOTIFY:track", text_hash, evidence_hash, "https://example.test/song", body, payload
    )

    assert record["body"] == body
    assert hashlib.sha256(record["body"].encode()).hexdigest() == record["text_sha256"]
    assert record["evidence_response_sha256"] == evidence_hash
    assert record["memberships"] == [{"country_code": "BR", "year": 2024, "position": 1}]
    assert record["identity_review"] == "pending"
    assert record["completeness_review"] == "pending"
    assert record["rights_review"] == "pending"
    assert record["canonical"] is False
    assert record["classification_ready"] is False
    assert "lyrics" not in record

    with pytest.raises(ValueError, match="text hash"):
        exact_replay_record("x", "0" * 64, evidence_hash, "url", body, payload)
    with pytest.raises(ValueError, match="evidence response hash"):
        exact_replay_record("x", text_hash, "invalid", "url", body, payload)


def test_memberships_keep_country_year_and_optional_position_only():
    assert memberships(
        {
            "chart_bindings": [
                {"country_code": "US", "year": 2022, "position": 9, "x": 1},
                {"country_code": "US", "year": 2023},
            ]
        }
    ) == [
        {"country_code": "US", "year": 2022, "position": 9},
        {"country_code": "US", "year": 2023},
    ]
