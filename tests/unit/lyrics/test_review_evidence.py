import json

import pytest

from chart_observatory.lyrics.review_evidence import import_comparison_export, review_blocks


def export():
    return {
        "exportVersion": "research-comparison-export-v1",
        "campaignFingerprint": "campaign",
        "evaluations": [{
            "recording": {"id": "recording", "documentId": "document", "lyricsHash": "a" * 64},
            "review": {"id": "review", "documentId": "document", "recordingId": "recording",
                       "lyricsHash": "a" * 64, "identityVerdict": "confirmed",
                       "justification": "Primeira estrofe ausente.", "aiExposed": True},
            "comparison": {"provenance": {"source": "GENIUS"}},
        }],
    }


def test_import_preserves_evidence_without_promoting_scores(tmp_path):
    path = tmp_path / "reviews.json"
    path.write_text(json.dumps(export()), encoding="utf-8")
    evidence = import_comparison_export(path)
    assert evidence[0]["ai_exposed"] is True
    assert evidence[0]["decision"] == "reported_text_defect"
    assert "scores" not in evidence[0]
    assert review_blocks(evidence, "document", "a" * 64)
    assert not review_blocks(evidence, "document", "b" * 64)


def test_import_rejects_cross_document_review(tmp_path):
    payload = export()
    payload["evaluations"][0]["review"]["documentId"] = "other"
    path = tmp_path / "reviews.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="binding"):
        import_comparison_export(path)


def test_confirmed_review_without_text_complaint_is_not_excluded(tmp_path):
    payload = export()
    payload["evaluations"][0]["review"]["justification"] = "Texto correto e íntegro."
    path = tmp_path / "reviews.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    evidence = import_comparison_export(path)
    assert not review_blocks(evidence, "document", "a" * 64)
