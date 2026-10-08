import json
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.corpus import LyricClassificationSnapshot
from chart_observatory.db.models.lyrics_batch import (
    LyricClassificationBatchItem,
    LyricClassificationBatchRun,
)
from chart_observatory.lyrics.batch_quality import (
    build_pilot_quality_report,
    weighted_cohens_kappa,
)
from chart_observatory.lyrics.repository import (
    ClassificationSnapshotInput,
    LyricDocumentInput,
    append_classification_snapshot,
    ingest_lyric_document,
)


def test_weighted_kappa_is_one_for_identical_ordinal_codes() -> None:
    assert weighted_cohens_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == 1.0
    assert weighted_cohens_kappa([2, 2], [2, 2]) == 1.0


def test_pilot_report_contains_no_lyric_or_track_metadata() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run = LyricClassificationBatchRun(
            kind="pilot",
            state="imported",
            model_id="gemini-3.8-flash",
            taxonomy_version="taxonomy",
            prompt_version="prompt",
            thinking_level="LOW",
            project_id="p",
            location="global",
            bucket_name="b",
            request_count=2,
        )
        session.add(run)
        session.flush()
        for number, status in enumerate(("classified", "error"), start=1):
            document = ingest_lyric_document(
                session,
                LyricDocumentInput(
                    canonical_track_id=uuid4(),
                    source=str(number),
                    source_version="1",
                    rights_status="AUTHORIZED",
                    language_code="pt",
                    text=f"secret lyric text number {number} and Artist Name",
                ),
            )
            item = LyricClassificationBatchItem(
                opaque_key=uuid4(),
                batch_run_id=run.id,
                line_number=number,
                lyric_document_id=document.id,
                canonical_track_id=document.canonical_track_id,
                lyrics_hash=document.content_sha256,
                model_id=run.model_id,
                taxonomy_version=run.taxonomy_version,
                prompt_version=run.prompt_version,
                state="imported",
            )
            session.add(item)
            session.flush()
            snapshot = append_classification_snapshot(
                session,
                ClassificationSnapshotInput(
                    lyric_document_id=document.id,
                    canonical_track_id=document.canonical_track_id,
                    lyrics_hash=document.content_sha256,
                    model_id=run.model_id,
                    taxonomy_version=run.taxonomy_version,
                    prompt_version=run.prompt_version,
                    classification_status=status,
                    error="batch_provider_error" if status == "error" else None,
                    execution_mode="batch",
                    batch_run_id=run.id,
                    batch_item_key=item.opaque_key,
                ),
            )
            item.snapshot_id = snapshot.id
        session.commit()

        report = build_pilot_quality_report(session, [run.id])
        encoded = report.model_dump_json()

        assert report.total_items == 2
        assert str(report.validation_error_rate) == "0.5"
        assert "secret lyric" not in encoded
        assert "artist name" not in encoded.casefold()
        assert report.status_distribution == {"classified": 1, "error": 1}


def test_pilot_report_keeps_quarantined_results_out_of_scientific_metrics(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run = LyricClassificationBatchRun(
            kind="pilot",
            state="imported",
            model_id="gemini-3.8-flash",
            taxonomy_version="taxonomy",
            prompt_version="prompt",
            thinking_level="LOW",
            project_id="p",
            location="global",
            bucket_name="b",
            request_count=2,
        )
        session.add(run)
        session.flush()
        documents = []
        for number, status in enumerate(("classified", "error"), start=1):
            document = ingest_lyric_document(
                session,
                LyricDocumentInput(
                    canonical_track_id=uuid4(),
                    source="LETRAS" if number == 1 else "GENIUS",
                    source_version="1",
                    rights_status="AUTHORIZED",
                    language_code="pt",
                    text=f"long enough lyric content for test document number {number}",
                ),
            )
            documents.append(document)
            item = LyricClassificationBatchItem(
                opaque_key=uuid4(),
                batch_run_id=run.id,
                line_number=number,
                lyric_document_id=document.id,
                canonical_track_id=document.canonical_track_id,
                lyrics_hash=document.content_sha256,
                model_id=run.model_id,
                taxonomy_version=run.taxonomy_version,
                prompt_version=run.prompt_version,
                state="imported",
            )
            session.add(item)
            session.flush()
            snapshot = append_classification_snapshot(
                session,
                ClassificationSnapshotInput(
                    lyric_document_id=document.id,
                    canonical_track_id=document.canonical_track_id,
                    lyrics_hash=document.content_sha256,
                    model_id=run.model_id,
                    taxonomy_version=run.taxonomy_version,
                    prompt_version=run.prompt_version,
                    classification_status=status,
                    error="batch_provider_error" if status == "error" else None,
                    execution_mode="batch",
                    batch_run_id=run.id,
                    batch_item_key=item.opaque_key,
                ),
            )
            item.snapshot_id = snapshot.id
        session.commit()

        manifest = tmp_path / "quarantine.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "suspended_sources": [
                        {
                            "source": "LETRAS",
                            "status": "suspended_pending_validation",
                            "reason": "Pending independent lyric identity validation.",
                            "effective_on": "2026-09-27",
                            "expected_document_count": 26540,
                            "allow_active_batch_reconciliation": True,
                        }
                    ],
                    "entries": [],
                }
            ),
            encoding="utf-8",
        )

        report = build_pilot_quality_report(session, [run.id], quarantine_manifest_path=manifest)

        assert report.total_items == 1
        assert report.quarantined_items == 1
        assert report.status_distribution == {"error": 1}
        assert [item.opaque_key for item in report.blinded_items] == [
            session.query(LyricClassificationBatchItem)
            .filter_by(lyric_document_id=documents[1].id)
            .one()
            .opaque_key
        ]
        persisted_statuses = list(
            session.scalars(
                select(LyricClassificationSnapshot.classification_status).order_by(
                    LyricClassificationSnapshot.classification_status
                )
            )
        )
        assert persisted_statuses == ["classified", "error"]
