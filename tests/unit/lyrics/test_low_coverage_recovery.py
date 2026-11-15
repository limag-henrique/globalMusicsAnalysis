import hashlib
import importlib.util
from pathlib import Path

import pytest

from chart_observatory.lyrics.quota_acquisition import AcquisitionStore

SPEC = importlib.util.spec_from_file_location(
    "low_coverage", Path(__file__).resolve().parents[3] / "scripts/recover_low_coverage_lyrics.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def baseline(digest=None):
    return {
        "SPOTIFY:a": dict(
            candidate_id="SPOTIFY:a",
            payload=dict(recording_id="SPOTIFY:a", title="A", artist="B", chart_bindings=[]),
            source_result={},
            audit={},
            acquisition_status="missing",
            text_sha256=digest,
        )
    }


def test_existing_text_is_preserved_even_when_acquisition_offers_different_text(tmp_path):
    body = "Complete existing edition"
    digest = hashlib.sha256(body.encode()).hexdigest()
    source = baseline(digest)
    store = AcquisitionStore(tmp_path)
    try:
        store.enqueue("SPOTIFY:a", source["SPOTIFY:a"]["payload"])
        store.finish("SPOTIFY:a", {"status": "candidate_pending_validation", "text": "Different"})
        records, texts = module.merged_records(source, {digest: body}, store)
        assert records[0]["text_sha256"] == digest
        assert texts == {digest: body}
    finally:
        store.conn.close()


def test_different_recording_payload_cannot_fill_missing_text(tmp_path):
    source = baseline()
    store = AcquisitionStore(tmp_path)
    try:
        store.enqueue("SPOTIFY:a", {**source["SPOTIFY:a"]["payload"], "artist": "Other"})
        store.finish("SPOTIFY:a", {"status": "candidate_pending_validation", "text": "Text"})
        with pytest.raises(ValueError, match="frozen candidate"):
            module.merged_records(source, {}, store)
    finally:
        store.conn.close()


def test_corrupt_recovered_blob_rejected(tmp_path):
    source = baseline()
    store = AcquisitionStore(tmp_path)
    try:
        store.enqueue("SPOTIFY:a", source["SPOTIFY:a"]["payload"])
        store.finish("SPOTIFY:a", {"status": "candidate_pending_validation", "text": "Text"})
        next((tmp_path / "texts").iterdir()).write_text("Corrupt", encoding="utf8")
        with pytest.raises(ValueError, match="hash mismatch"):
            module.merged_records(source, {}, store)
    finally:
        store.conn.close()


def test_threshold_rounds_up_and_is_evaluated_per_cell():
    cells = {
        ("AA", 2020): {"known_positions": 101, "positions_with_text": 80},
        ("BB", 2020): {"known_positions": 100, "positions_with_text": 100},
    }
    assert module.deficient(cells) == {("AA", 2020): 1}


def test_duration_enrichment_requires_exact_native_recording_and_identity():
    source = baseline()
    proof = dict(
        status=200,
        source_url="https://open.spotify.com/embed/track/a",
        metadata=dict(uri="spotify:track:a", title="A", artist="B", duration_ms=123456),
    )
    enriched, conflicts = module.enrich_matching_proofs(
        source, {"SPOTIFY:a": proof}, "proof.json", "f" * 64
    )
    assert enriched == ["SPOTIFY:a"] and conflicts == []
    assert source["SPOTIFY:a"]["payload"]["metadata_resolution"]["duration_ms"] == 123456
    assert (
        source["SPOTIFY:a"]["payload"]["metadata_resolution"]["recording_and_text_validation"]
        is False
    )
    proof["metadata"]["uri"] = "spotify:track:wrong"
    with pytest.raises(ValueError, match="another recording"):
        module.enrich_matching_proofs(baseline(), {"SPOTIFY:a": proof}, "proof.json", "f" * 64)


def test_native_display_disagreement_is_held_without_changing_payload():
    source = baseline()
    proof = dict(
        status=200,
        source_url="https://open.spotify.com/embed/track/a",
        metadata=dict(
            uri="spotify:track:a", title="Another version", artist="B", duration_ms=123456
        ),
    )
    enriched, conflicts = module.enrich_matching_proofs(
        source, {"SPOTIFY:a": proof}, "proof.json", "f" * 64
    )
    assert enriched == [] and len(conflicts) == 1
    assert "metadata_resolution" not in source["SPOTIFY:a"]["payload"]
