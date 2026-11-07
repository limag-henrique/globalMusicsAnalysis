"""Explicit adjudication fixtures for synthetic lyrics; never approve research data."""

import pytest

from chart_observatory.lyrics.classification_gate import ADJUDICATION_KEY, GATE_VERSION


@pytest.fixture
def adjudicate_lyric():
    def approve(document):
        document.metadata_json = {
            **(document.metadata_json or {}),
            ADJUDICATION_KEY: {
                "gate_version": GATE_VERSION,
                "adjudication_id": f"synthetic-fixture-{document.id}",
                "document_id": str(document.id),
                "recording_id": str(document.canonical_track_id),
                "lyrics_hash": document.content_sha256,
                "source": document.source,
                "status": "approved",
                "identity_verified": True,
                "integrity_verified": True,
                "method": "human_audio_verification",
                "evidence_url": "https://example.org/synthetic-test-evidence",
                "evidence_sha256": "e" * 64,
                "verified_at": "2026-11-01T10:00:00+00:00",
                "adjudicated_at": "2026-11-01T11:00:00+00:00",
                "adjudicator": "Synthetic fixture reviewer",
            },
        }
        return document

    return approve


@pytest.fixture
def approved_fixture_ingest(request, monkeypatch, adjudicate_lyric):
    """Opt-in legacy behavior tests use actual approvals instead of bypassing the gate."""
    original = request.module.ingest_lyric_document

    def ingest(*args, **kwargs):
        return adjudicate_lyric(original(*args, **kwargs))

    monkeypatch.setattr(request.module, "ingest_lyric_document", ingest)
