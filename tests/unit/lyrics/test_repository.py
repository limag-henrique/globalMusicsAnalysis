from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.corpus import LyricDocument, SemanticAnnotation
from chart_observatory.lyrics.annotations import SemanticAnnotationInput
from chart_observatory.lyrics.repository import (
    LyricDocumentInput,
    annotate_document,
    ingest_lyric_document,
)


def test_authorized_lyric_document_and_annotation_are_idempotent() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    track_id = uuid4()
    with Session(engine) as session:
        document = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=track_id,
                source="AUTHORIZED_RESEARCH_CORPUS",
                source_version="v1",
                rights_status="RESEARCH_AUTHORIZED",
                text="short licensed excerpt",
            ),
        )
        annotation = SemanticAnnotationInput(
            "sexual_explicitness", 0.75, 0.9, "LLM_REVIEW", "model-v1", "RESEARCHER"
        )
        annotate_document(session, document.id, [annotation])
        annotate_document(session, document.id, [annotation])
        session.commit()
        assert session.query(LyricDocument).count() == 1
        assert session.query(SemanticAnnotation).count() == 1


def test_unlicensed_document_is_rejected() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session, pytest.raises(ValueError, match="not authorized"):
        ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="SCRAPED_SITE",
                source_version="latest",
                rights_status="UNKNOWN",
            ),
        )
