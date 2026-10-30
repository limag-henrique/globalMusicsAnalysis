import importlib
import json
from pathlib import Path


def test_report_counts_document_bindings_once_and_does_not_consume_partial_tail(
    monkeypatch, tmp_path,
):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    report = importlib.import_module("report_lyrics_recovery")
    targets = tmp_path / "targets.jsonl"
    targets.write_text("\n".join(json.dumps({
        "document_id": str(i), "track_id": "recording" if i < 2 else "other",
        "lyrics_hash": "a" * 64,
    }) for i in range(3)), encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    first = {"status": "candidate_pending_validation", "variants": [{}, {}],
             "cross_source_text_agreement": True,
             "original_bindings": [{"document_id": str(i), "lyrics_hash": "a" * 64}
                                   for i in range(2)]}
    second = {"status": "not_found", "original_document_id": "2",
              "original_lyrics_hash": "a" * 64}
    raw = (json.dumps(first) + "\n" + json.dumps(first) + "\n"
           + json.dumps(second) + "\n" + '{"status":').encode()
    ledger.write_bytes(raw)
    result = report.summarize(targets, ledger)
    assert result["processed_documents"] == 3
    assert result["observed_recording_signatures"] == 2
    assert result["candidate_variants_by_recording"] == 2
    assert result["word_sequence_agreements"] == 1
    assert result["incomplete_tail_observed"] is True
    assert result["collection_complete"] is False
    assert ledger.read_bytes() == raw
