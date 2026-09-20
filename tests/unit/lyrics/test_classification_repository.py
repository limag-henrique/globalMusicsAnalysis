from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.corpus import LyricClassificationSnapshot, LyricDocument
from chart_observatory.lyrics.classification import (
    CostRateCard,
    LyricsClassification,
    UsageTelemetry,
)
from chart_observatory.lyrics.repository import (
    ClassificationSnapshotInput,
    LyricDocumentInput,
    append_classification_snapshot,
    find_matching_snapshot,
    ingest_lyric_document,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


@pytest.fixture
def lyric_document(session: Session) -> LyricDocument:
    return ingest_lyric_document(
        session,
        LyricDocumentInput(
            canonical_track_id=uuid4(),
            source="AUTHORIZED_RESEARCH_CORPUS",
            source_version="v1",
            rights_status="RESEARCH_AUTHORIZED",
            text="authorized lyric text",
        ),
    )


def classification() -> LyricsClassification:
    return LyricsClassification.model_validate(
        {
            "classification_status": "classified",
            "confidence": 0.8,
            "sexuality": {
                "sexual_explicitness": 1,
                "sexual_desire": 2,
                "sexual_innuendo": 1,
                "explicit_sexual_act": 0,
                "explicit_sexual_anatomy": 0,
            },
            "relationships": {
                "romantic_affection": 2,
                "heartbreak": 1,
                "infidelity": 0,
                "transactional_sex": 0,
                "casual_sex": 0,
                "jealousy_possession": 0,
                "reciprocity": 2,
                "consent": "explicit_mutual",
            },
            "gender_representation": {
                "objectification": 0,
                "misogyny": 0,
                "sexual_agency": 2,
                "status_symbolization": 0,
                "commodification": 0,
                "target_gender": "women",
                "representation_roles": ["subject"],
            },
            "material_status": {
                "money_reference": 0,
                "materialism": 0,
                "conspicuous_consumption": 0,
                "wealth_as_status": 0,
            },
            "antisocial": {
                "drugs_alcohol": {"intensity": 0, "stance": "neutral"},
                "crime": {"intensity": 0, "stance": "neutral"},
                "violence": {"intensity": 0, "stance": "neutral"},
                "weapons": {"intensity": 0, "stance": "neutral"},
            },
            "territorial_identity": 1,
            "romantic_summary": "An affectionate reciprocal relationship.",
        }
    )


def snapshot_input(
    document: LyricDocument,
    *,
    result: LyricsClassification | None = None,
    status: str = "classified",
    usage: UsageTelemetry | None = None,
    forced_from_snapshot_id: UUID | None = None,
) -> ClassificationSnapshotInput:
    return ClassificationSnapshotInput(
        lyric_document_id=document.id,
        canonical_track_id=document.canonical_track_id,
        lyrics_hash=document.content_sha256,
        model_id="gemini-fixed-model",
        taxonomy_version="lyrics-classification-v1",
        prompt_version="lyrics-classification-prompt-v1",
        classification_status=status,
        result=result,
        error="provider unavailable" if status == "error" else None,
        classified_at=datetime(2026, 9, 19, tzinfo=UTC),
        usage=usage,
        rate_card=CostRateCard(
            input_usd_per_million_tokens=Decimal("1"),
            output_usd_per_million_tokens=Decimal("2"),
            thought_usd_per_million_tokens=Decimal("3"),
        ),
        forced_from_snapshot_id=forced_from_snapshot_id,
    )


def test_matching_signature_returns_latest_snapshot(
    session: Session, lyric_document: LyricDocument
) -> None:
    """Catches a lookup that misses the reproducibility signature or does not select latest."""
    first = append_classification_snapshot(
        session, snapshot_input(lyric_document, result=classification())
    )

    match = find_matching_snapshot(session, snapshot_input(lyric_document))

    assert match is not None
    assert match.id == first.id


def test_forced_snapshot_appends_immutable_history(
    session: Session, lyric_document: LyricDocument
) -> None:
    """Catches a forced run that updates the original snapshot instead of preserving history."""
    first = append_classification_snapshot(
        session, snapshot_input(lyric_document, result=classification())
    )
    forced = append_classification_snapshot(
        session,
        snapshot_input(
            lyric_document, result=classification(), forced_from_snapshot_id=first.id
        ),
    )

    assert forced.id != first.id
    assert forced.forced_from_snapshot_id == first.id
    assert session.scalars(select(LyricClassificationSnapshot)).all() == [first, forced]


def test_matching_signature_returns_last_forced_snapshot_when_created_at_ties(
    session: Session, lyric_document: LyricDocument
) -> None:
    """Catches UUID ordering that mistakes an older forced row for the latest append."""
    first = append_classification_snapshot(
        session, snapshot_input(lyric_document, result=classification())
    )
    forced = append_classification_snapshot(
        session,
        snapshot_input(
            lyric_document, result=classification(), forced_from_snapshot_id=first.id
        ),
    )
    latest = append_classification_snapshot(
        session,
        snapshot_input(
            lyric_document, result=classification(), forced_from_snapshot_id=forced.id
        ),
    )

    match = find_matching_snapshot(session, snapshot_input(lyric_document))

    assert first.created_at == forced.created_at == latest.created_at
    assert match is not None
    assert match.id == latest.id


def test_matching_signature_uses_append_order_for_tied_terminal_forced_branches(
    session: Session, lyric_document: LyricDocument
) -> None:
    """Catches a latest lookup that orders concurrent forced branches by UUID or chain shape."""
    first = append_classification_snapshot(
        session, snapshot_input(lyric_document, result=classification())
    )
    earlier_branch = append_classification_snapshot(
        session,
        snapshot_input(
            lyric_document, result=classification(), forced_from_snapshot_id=first.id
        ),
    )
    later_branch = append_classification_snapshot(
        session,
        snapshot_input(
            lyric_document, result=classification(), forced_from_snapshot_id=first.id
        ),
    )

    assert first.append_order < earlier_branch.append_order < later_branch.append_order

    match = find_matching_snapshot(session, snapshot_input(lyric_document))

    assert first.created_at == earlier_branch.created_at == later_branch.created_at
    assert match is not None
    assert match.id == later_branch.id


def test_snapshot_rejects_direct_updates(session: Session, lyric_document: LyricDocument) -> None:
    """Catches an ORM update that rewrites an immutable automatic outcome."""
    row = append_classification_snapshot(
        session, snapshot_input(lyric_document, result=classification())
    )
    session.commit()

    row.confidence = 0.1

    with pytest.raises(InvalidRequestError, match="immutable lyric classification snapshot"):
        session.flush()


def test_snapshot_rejects_track_that_does_not_match_document(
    session: Session, lyric_document: LyricDocument
) -> None:
    """Catches snapshots whose explicit track FK disagrees with the source lyric document."""
    invalid = ClassificationSnapshotInput(
        **{
            **snapshot_input(lyric_document, result=classification()).__dict__,
            "canonical_track_id": uuid4(),
        }
    )

    with pytest.raises(ValueError, match="canonical_track_id"):
        append_classification_snapshot(session, invalid)


def test_error_snapshot_has_no_invented_result_json(
    session: Session, lyric_document: LyricDocument
) -> None:
    """Catches error outcomes that are persisted as fabricated zero-score classifications."""
    row = append_classification_snapshot(session, snapshot_input(lyric_document, status="error"))

    assert row.result_json is None
    assert row.error == "provider unavailable"


def test_snapshot_stores_complete_pydantic_result_as_json(
    session: Session, lyric_document: LyricDocument
) -> None:
    """Catches loss of nested taxonomy fields while persisting a validated classification."""
    result = classification()
    row = append_classification_snapshot(session, snapshot_input(lyric_document, result=result))

    assert row.result_json == result.model_dump(mode="json")
    assert row.confidence == 0.8


def test_partial_usage_keeps_missing_usage_and_cost_null(
    session: Session, lyric_document: LyricDocument
) -> None:
    """Catches partial provider usage being promoted to a fictitious complete cost."""
    row = append_classification_snapshot(
        session,
        snapshot_input(
            lyric_document,
            result=classification(),
            usage=UsageTelemetry(input_tokens=42),
        ),
    )

    assert row.input_tokens == 42
    assert row.output_tokens is None
    assert row.thought_tokens is None
    assert row.total_tokens is None
    assert row.estimated_cost_usd is None
