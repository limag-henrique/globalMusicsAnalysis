import json
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.corpus import LyricClassificationSnapshot
from chart_observatory.db.models.lyrics_batch import (
    LyricClassificationBatchItem,
    LyricClassificationBatchRun,
)
from chart_observatory.lyrics.batch_importer import BatchImporter, BatchIntegrityError
from chart_observatory.lyrics.batch_jsonl import canonical_request_sha256
from chart_observatory.lyrics.classification import CostRateCard, LyricsClassification
from chart_observatory.lyrics.repository import LyricDocumentInput, ingest_lyric_document


def result_payload(status: str = "classified") -> dict[str, object]:
    return {
        "classification_status": status,
        "confidence": 0.9,
        "sexuality": {
            name: 0
            for name in (
                "sexual_explicitness",
                "sexual_desire",
                "sexual_innuendo",
                "explicit_sexual_act",
                "explicit_sexual_anatomy",
            )
        },
        "relationships": {
            **{
                name: 0
                for name in (
                    "romantic_affection",
                    "heartbreak",
                    "infidelity",
                    "transactional_sex",
                    "casual_sex",
                    "jealousy_possession",
                    "reciprocity",
                )
            },
            "consent": "not_applicable",
        },
        "gender_representation": {
            **{
                name: 0
                for name in (
                    "objectification",
                    "misogyny",
                    "sexual_agency",
                    "status_symbolization",
                    "commodification",
                )
            },
            "target_gender": "not_applicable",
            "representation_roles": [],
        },
        "material_status": {
            name: 0
            for name in (
                "money_reference",
                "materialism",
                "conspicuous_consumption",
                "wealth_as_status",
            )
        },
        "antisocial": {
            name: {"intensity": 0, "stance": "neutral"}
            for name in ("drugs_alcohol", "crime", "violence", "weapons")
        },
        "territorial_identity": 0,
        "romantic_summary": None,
    }


def setup_run(session: Session, count: int = 2):
    run = LyricClassificationBatchRun(
        kind="pilot",
        state="succeeded",
        model_id="gemini-3.8-flash",
        taxonomy_version="lyrics-classification-v1",
        prompt_version="lyrics-classification-prompt-v2",
        thinking_level="LOW",
        project_id="p",
        location="global",
        bucket_name="b",
        request_count=count,
    )
    session.add(run)
    session.flush()
    items = []
    for number in range(count):
        document = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source=str(number),
                source_version="1",
                rights_status="AUTHORIZED",
                text=f"private lyric text number {number}",
            ),
        )
        request = {
            "contents": [{"role": "user", "parts": [{"text": document.text}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        envelope = {"key": "unused", "request": request}
        item = LyricClassificationBatchItem(
            opaque_key=uuid4(),
            batch_run_id=run.id,
            line_number=number + 1,
            lyric_document_id=document.id,
            canonical_track_id=document.canonical_track_id,
            lyrics_hash=document.content_sha256,
            model_id=run.model_id,
            taxonomy_version=run.taxonomy_version,
            prompt_version=run.prompt_version,
            request_sha256=canonical_request_sha256(envelope),
            state="submitted",
        )
        session.add(item)
        items.append((item, request))
    session.commit()
    return run, items


def response_line(item, request, *, payload=None, status=None) -> bytes:
    row = {"key": str(item.opaque_key), "request": request}
    if status is not None:
        row["status"] = status
    if not status:
        row["response"] = {
            "candidates": [
                {
                    "content": {"parts": [{"text": json.dumps(payload or result_payload())}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 80,
                "thoughtsTokenCount": 20,
                "totalTokenCount": 200,
            },
            "modelVersion": "gemini-3.8-flash@001",
        }
    return json.dumps(row).encode() + b"\n"


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def importer(session: Session) -> BatchImporter:
    return BatchImporter(
        session,
        CostRateCard(
            input_usd_per_million_tokens=Decimal("0.375"),
            output_usd_per_million_tokens=Decimal("1.875"),
            thought_usd_per_million_tokens=Decimal("1.875"),
        ),
    )


def test_import_validates_pydantic_and_appends_batch_snapshot(session: Session) -> None:
    run, items = setup_run(session, 1)

    summary = importer(session).import_available(run.id, [response_line(*items[0])])
    row = session.scalar(select(LyricClassificationSnapshot))

    assert row is not None
    assert LyricsClassification.model_validate(row.result_json)
    assert row.batch_run_id == run.id
    assert row.batch_item_key == items[0][0].opaque_key
    assert row.provider_model_version == "gemini-3.8-flash@001"
    assert summary.classified == 1


def test_import_treats_empty_provider_status_as_success(session: Session) -> None:
    run, items = setup_run(session, 1)

    summary = importer(session).import_available(
        run.id,
        [response_line(*items[0], status="")],
    )

    assert summary.classified == 1
    assert summary.errors == 0


@pytest.mark.parametrize("classification_status", ["insufficient_text", "instrumental"])
def test_import_accepts_valid_local_terminal_classification_statuses(
    session: Session, classification_status: str
) -> None:
    run, items = setup_run(session, 1)

    summary = importer(session).import_available(
        run.id,
        [response_line(*items[0], payload=result_payload(classification_status))],
    )
    snapshot = session.scalar(select(LyricClassificationSnapshot))

    assert snapshot is not None
    assert snapshot.classification_status == classification_status
    assert summary.errors == 0
    assert getattr(summary, classification_status) == 1


def test_item_error_is_persisted_and_next_line_continues(session: Session) -> None:
    run, items = setup_run(session, 2)
    lines = [
        response_line(*items[0], status={"code": 8, "message": "quota"}),
        response_line(*items[1]),
    ]

    summary = importer(session).import_available(run.id, lines)
    rows = list(
        session.scalars(
            select(LyricClassificationSnapshot).order_by(LyricClassificationSnapshot.append_order)
        )
    )

    assert [row.classification_status for row in rows] == ["error", "classified"]
    assert rows[0].result_json is None
    assert summary.errors == 1
    assert summary.classified == 1


def test_fingerprint_mismatch_persists_error_then_stops(session: Session) -> None:
    run, items = setup_run(session, 2)
    bad_request = {**items[0][1], "generationConfig": {"responseMimeType": "text/plain"}}

    with pytest.raises(BatchIntegrityError, match="fingerprint"):
        importer(session).import_available(
            run.id,
            [response_line(items[0][0], bad_request), response_line(*items[1])],
        )

    rows = list(session.scalars(select(LyricClassificationSnapshot)))
    assert len(rows) == 1
    assert rows[0].error == "batch_request_fingerprint_mismatch"
    assert run.state == "failed"
    assert run.job_error_code == "batch_request_fingerprint_mismatch"


def test_malformed_output_fails_run_without_retrying_rows(session: Session) -> None:
    run, _ = setup_run(session, 1)

    with pytest.raises(BatchIntegrityError, match="malformed output"):
        importer(session).import_available(run.id, [b"not-json\n"])

    session.refresh(run)
    assert run.state == "failed"
    assert run.job_error_code == "batch_malformed_output_line"


def test_finalize_is_idempotent_after_complete_import(session: Session) -> None:
    run, items = setup_run(session, 1)
    value = importer(session)
    value.import_available(run.id, [response_line(*items[0])])
    run.state = "imported"
    session.commit()

    summary = value.finalize_missing(run.id)

    assert summary.processed == 0
    assert len(list(session.scalars(select(LyricClassificationSnapshot)))) == 1
