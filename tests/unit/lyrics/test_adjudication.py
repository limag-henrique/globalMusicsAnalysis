from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.corpus import LyricClassificationSnapshot
from chart_observatory.lyrics.adjudication import record_adjudication
from chart_observatory.lyrics.classification_gate import (
    ADJUDICATION_KEY,
    ClassificationAdjudication,
    ClassificationEligibilityError,
    ClassificationGate,
)
from chart_observatory.lyrics.repository import LyricDocumentInput, ingest_lyric_document


@pytest.fixture
def prepared(adjudicate_lyric):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        doc = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="TEST",
                source_version="1",
                rights_status="AUTHORIZED",
                text="An intentionally synthetic full lyric.",
            ),
        )
        adjudicate_lyric(doc)
        approval = ClassificationAdjudication.model_validate(doc.metadata_json[ADJUDICATION_KEY])
        doc.metadata_json = {"existing_provenance": "must remain"}
        session.commit()
        yield session, doc, approval
    engine.dispose()


def decide(session, doc, approval, **kwargs):
    return record_adjudication(
        session,
        doc.id,
        expected_hash=doc.content_sha256,
        expected_previous_id=None,
        decision_id=approval.adjudication_id,
        actor=approval.adjudicator,
        decision="approved",
        reason="Synthetic verified evidence",
        approval=approval,
        **kwargs,
    )


def test_approval_rejection_and_stale_update_preserve_history(prepared):
    session, doc, approval = prepared
    original_text = doc.text
    decide(session, doc, approval)
    session.commit()
    assert ClassificationGate.load().assess(doc).eligible
    record_adjudication(
        session,
        doc.id,
        expected_hash=doc.content_sha256,
        expected_previous_id=approval.adjudication_id,
        decision_id="revoke-1",
        actor="Independent reviewer",
        decision="quarantined",
        reason="Conflicting evidence",
    )
    session.commit()
    assert not ClassificationGate.load().assess(doc).eligible
    assert len(doc.metadata_json["adjudication_history"]) == 2
    assert doc.metadata_json["adjudication_history"][1]["previous_approval"] == approval.model_dump(
        mode="json"
    )
    assert doc.metadata_json["existing_provenance"] == "must remain"
    assert doc.text == original_text
    with pytest.raises(ClassificationEligibilityError, match="stale_decision"):
        decide(session, doc, approval)
    assert session.scalar(select(LyricClassificationSnapshot)) is None


def test_failed_approval_rolls_back_metadata(prepared):
    session, doc, approval = prepared
    original = dict(doc.metadata_json)
    bad = approval.model_copy(update={"recording_id": uuid4()})
    with pytest.raises(ClassificationEligibilityError, match="binding_mismatch"):
        decide(session, doc, bad)
    session.refresh(doc)
    assert doc.metadata_json == original


def test_outer_rollback_preserves_original_decisions(prepared):
    session, doc, approval = prepared
    # SQLite releases an outermost SAVEPOINT immediately; explicitly begin the
    # containing transaction just as PostgreSQL does on its first statement.
    session.connection().exec_driver_sql("BEGIN")
    decide(session, doc, approval)
    session.rollback()
    session.refresh(doc)
    assert ADJUDICATION_KEY not in doc.metadata_json
