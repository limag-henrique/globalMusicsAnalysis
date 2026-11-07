"""Real row locks and rollback, restricted to a dedicated remediation test database."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from chart_observatory.db.models.tracks import CanonicalTrack
from chart_observatory.lyrics.adjudication import record_adjudication
from chart_observatory.lyrics.classification_gate import (
    ADJUDICATION_KEY,
    GATE_VERSION,
    ClassificationAdjudication,
    ClassificationEligibilityError,
)
from chart_observatory.lyrics.repository import LyricDocumentInput, ingest_lyric_document

pytestmark = pytest.mark.integration


@pytest.fixture
def database():
    value = os.environ.get("CHART_OBSERVATORY_TEST_DATABASE_URL")
    if not value or not (make_url(value).database or "").startswith(
        "chart_observatory_remediation_test_"
    ):
        pytest.skip("requires isolated remediation test database; never writes production")
    engine = create_engine(value)
    with Session(engine) as session:
        track = CanonicalTrack(title="Synthetic integration test")
        session.add(track)
        session.flush()
        doc = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=track.id,
                source="INTEGRATION_TEST",
                source_version="1",
                rights_status="AUTHORIZED",
                text="This synthetic integration lyric is not copyrighted.",
            ),
        )
        session.commit()
        yield engine, doc.id, doc.content_sha256
    engine.dispose()


def review(session, identity, digest, **overrides):
    params = dict(
        expected_hash=digest,
        expected_previous_id=None,
        decision_id="first-decision",
        actor="Integration reviewer",
        decision="manual_review",
        reason="Synthetic case",
    )
    params.update(overrides)
    return record_adjudication(session, identity, **params)


def test_rollback_restores_original_metadata(database):
    engine, identity, digest = database
    with Session(engine) as session:
        doc = review(session, identity, digest)
        assert len(doc.metadata_json["adjudication_history"]) == 1
        session.rollback()
        session.refresh(doc)
        assert doc.metadata_json == {}


def test_concurrent_reviewers_are_serialized_and_stale_decision_rejected(database):
    engine, identity, digest = database
    with Session(engine) as first, Session(engine) as second:
        review(first, identity, digest)
        second.execute(text("SET LOCAL lock_timeout='100ms'"))
        with pytest.raises(DBAPIError):
            review(second, identity, digest, decision_id="second-decision")
        second.rollback()
        first.commit()
        with pytest.raises(ClassificationEligibilityError, match="stale_decision"):
            review(second, identity, digest, decision_id="second-decision")


def test_explicit_approval_survives_commit_without_touching_text(database):
    from chart_observatory.db.models.corpus import LyricDocument
    from chart_observatory.lyrics.classification_gate import ClassificationGate

    engine, identity, digest = database
    with Session(engine) as session:
        doc = session.get(LyricDocument, identity)
        original = doc.text
        approval = ClassificationAdjudication(
            gate_version=GATE_VERSION,
            adjudication_id="integration-approval",
            document_id=identity,
            recording_id=doc.canonical_track_id,
            lyrics_hash=digest,
            source=doc.source,
            status="approved",
            identity_verified=True,
            integrity_verified=True,
            method="human_audio_verification",
            evidence_url="https://example.org/synthetic",
            evidence_sha256="e" * 64,
            verified_at="2026-11-01T00:00:00Z",
            adjudicated_at="2026-11-01T01:00:00Z",
            adjudicator="Integration reviewer",
        )
        review(
            session,
            identity,
            digest,
            decision="approved",
            decision_id=approval.adjudication_id,
            approval=approval,
        )
        session.commit()
        session.refresh(doc)
        assert doc.text == original
        assert doc.metadata_json[ADJUDICATION_KEY]["lyrics_hash"] == digest
        assert ClassificationGate.load().assess(doc).eligible
