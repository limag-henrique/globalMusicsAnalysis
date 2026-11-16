import sqlite3

import pytest

from chart_observatory import automatic_preparation as auto


def approved():
    return dict(
        validation={
            k: dict(status="passed") for k in ["identity", "completeness", "source_text_integrity"]
        },
        native_supported=True,
        native_evidence=dict(native_proof_present=True, body_sha256="a" * 64),
        body_hash_verified=True,
        provider_supported=True,
        audit=dict(text_quality_flags=[]),
    )


def test_automatic_approval_does_not_fabricate_scientific_approval():
    result = auto.assess(approved())
    assert result["eligible"]
    assert not result["scientific_approval"]
    assert not result["audio_transcription_equivalence_proven"]


@pytest.mark.parametrize(
    "flag", ["short_text", "native_title_disagreement", "shared_provider_id_across_editions"]
)
def test_quality_flags_block_automatic_preparation(flag):
    decision = approved()
    decision["audit"]["text_quality_flags"] = [flag]
    assert not auto.assess(decision)["eligible"]


def test_cumulative_limit_and_resumption(monkeypatch):
    monkeypatch.setattr(auto, "MAX_SONGS", 2)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE prepared(id TEXT)")
    for cid in ["a", "b", "a"]:
        assert auto.register(
            db, recording_id=cid, request_id=cid, text_hash="hash", selection_hash="s"
        )
    assert not auto.register(
        db, recording_id="c", request_id="c", text_hash="hash", selection_hash="s"
    )
    with pytest.raises(ValueError, match="different"):
        auto.register(db, recording_id="a", request_id="a", text_hash="changed", selection_hash="s")


def test_materialization_rejects_changed_transcription():
    with pytest.raises(ValueError, match="changed"):
        auto.request_body(dict(text_sha256="old", request_id="id"), "changed")
