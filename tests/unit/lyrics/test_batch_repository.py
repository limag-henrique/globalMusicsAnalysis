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
from chart_observatory.lyrics.batch_contract import (
    BatchPreparationRequest,
    BatchRunKind,
    BatchRunState,
    InvalidBatchTransition,
    validate_run_transition,
)
from chart_observatory.lyrics.batch_repository import BatchRepository
from chart_observatory.lyrics.classification import UsageTelemetry
from chart_observatory.lyrics.classification_queue import ClassificationSignature
from chart_observatory.lyrics.repository import (
    ClassificationSnapshotInput,
    LyricDocumentInput,
    append_classification_snapshot,
    ingest_lyric_document,
)


def test_prepare_run_reserves_candidates_with_random_opaque_keys() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for index in range(3):
            ingest_lyric_document(
                session,
                LyricDocumentInput(
                    canonical_track_id=uuid4(),
                    source=f"s-{index}",
                    source_version="1",
                    rights_status="AUTHORIZED",
                    text=f"provider lyric text number {index}",
                ),
            )
        request = BatchPreparationRequest(
            kind=BatchRunKind.PILOT,
            signature=ClassificationSignature("gemini-3.8-flash", "taxonomy", "prompt"),
            project_id="project",
            location="global",
            bucket_name="private",
            limit=3,
        )

        run = BatchRepository(session).prepare_run(request)
        items = BatchRepository(session).items(run.id)

        assert len(items) == 3
        assert len({item.opaque_key for item in items}) == 3
        assert all(
            item.opaque_key not in {item.lyric_document_id, item.canonical_track_id}
            for item in items
        )


def test_invalid_state_transition_is_rejected() -> None:
    with pytest.raises(InvalidBatchTransition):
        validate_run_transition(BatchRunState.PREPARED, BatchRunState.SUCCEEDED)


def test_request_hashes_are_recorded_in_bounded_bulk_updates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for number in range(2):
            ingest_lyric_document(
                session,
                LyricDocumentInput(
                    canonical_track_id=uuid4(),
                    source=str(number),
                    source_version="1",
                    rights_status="AUTHORIZED",
                    text=f"provider lyric text number {number}",
                ),
            )
        repository = BatchRepository(session)
        run = repository.prepare_run(
            BatchPreparationRequest(
                kind=BatchRunKind.PILOT,
                signature=ClassificationSignature("gemini-3.8-flash", "taxonomy", "prompt"),
                project_id="project",
                location="global",
                bucket_name="private",
                limit=2,
            )
        )
        items = repository.items(run.id)

        repository.record_request_hashes(
            run.id, ((item.opaque_key, str(index) * 64) for index, item in enumerate(items, 1))
        )
        session.commit()
        session.expire_all()

        assert [item.request_sha256 for item in repository.items(run.id)] == ["1" * 64, "2" * 64]


def test_run_is_split_atomically_by_artifact_keys() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for number in range(3):
            ingest_lyric_document(
                session,
                LyricDocumentInput(
                    canonical_track_id=uuid4(),
                    source=str(number),
                    source_version="1",
                    rights_status="AUTHORIZED",
                    text=f"provider lyric text number {number}",
                ),
            )
        repository = BatchRepository(session)
        run = repository.prepare_run(
            BatchPreparationRequest(
                kind=BatchRunKind.MAIN,
                signature=ClassificationSignature("gemini-3.8-flash", "taxonomy", "prompt"),
                project_id="project",
                location="global",
                bucket_name="private",
                limit=3,
            )
        )
        keys = [item.opaque_key for item in repository.items(run.id)]

        runs = repository.shard_run(run.id, [keys[:2], keys[2:]])

        assert [item.request_count for item in runs] == [2, 1]
        assert [item.opaque_key for item in repository.items(runs[0].id)] == keys[:2]
        assert [item.opaque_key for item in repository.items(runs[1].id)] == keys[2:]


def test_prepare_persists_local_outcomes_without_exporting_them() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        local = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="local",
                source_version="1",
                rights_status="AUTHORIZED",
                text="short",
            ),
        )
        ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="provider",
                source_version="1",
                rights_status="AUTHORIZED",
                text="provider lyric text long enough",
            ),
        )
        request = BatchPreparationRequest(
            kind=BatchRunKind.CANARY,
            signature=ClassificationSignature("gemini-3.8-flash", "taxonomy", "prompt"),
            project_id="project",
            location="global",
            bucket_name="private",
            limit=2,
        )

        run = BatchRepository(session).prepare_run(request)

        local_snapshot = session.scalar(
            select(LyricClassificationSnapshot).where(
                LyricClassificationSnapshot.lyric_document_id == local.id
            )
        )
        assert local_snapshot is not None
        assert local_snapshot.classification_status == "insufficient_text"
        assert run.request_count == 1
        assert len(BatchRepository(session).items(run.id)) == 1


def test_error_retry_candidates_exclude_suspended_sources() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run = LyricClassificationBatchRun(
            kind="main",
            state="imported",
            model_id="gemini-3.8-flash",
            taxonomy_version="taxonomy",
            prompt_version="prompt",
            thinking_level="LOW",
            project_id="project",
            location="global",
            bucket_name="private",
            request_count=2,
        )
        session.add(run)
        session.flush()
        documents = [
            ingest_lyric_document(
                session,
                LyricDocumentInput(
                    canonical_track_id=uuid4(),
                    source=source,
                    source_version="1",
                    rights_status="AUTHORIZED",
                    text=f"provider lyric text for {source}",
                ),
            )
            for source in ("LETRAS", "GENIUS")
        ]
        for line_number, document in enumerate(documents, start=1):
            item = LyricClassificationBatchItem(
                opaque_key=uuid4(),
                batch_run_id=run.id,
                line_number=line_number,
                lyric_document_id=document.id,
                canonical_track_id=document.canonical_track_id,
                lyrics_hash=document.content_sha256,
                model_id=run.model_id,
                taxonomy_version=run.taxonomy_version,
                prompt_version=run.prompt_version,
                state="error",
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
                    classification_status="error",
                    error=(
                        "batch_malformed_response"
                        if document.source == "GENIUS"
                        else "batch_provider_error"
                    ),
                    execution_mode="batch",
                    batch_run_id=run.id,
                    batch_item_key=item.opaque_key,
                ),
            )
            item.snapshot_id = snapshot.id
        session.commit()

        candidates = BatchRepository(session).error_retry_candidates(
            run.id, frozenset({"batch_malformed_response"})
        )

        assert [candidate.lyric_document_id for candidate in candidates] == [documents[1].id]


@pytest.mark.parametrize("condition", ["resolved", "reserved", "revoked"])
def test_retry_excludes_resolved_reserved_or_unauthorized_documents(condition) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        document = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="GENIUS",
                source_version="1",
                rights_status="AUTHORIZED",
                text="a complete authorized lyric for retry",
            ),
        )
        request = BatchPreparationRequest(
            kind=BatchRunKind.MAIN,
            signature=ClassificationSignature("gemini-3.8-flash", "taxonomy", "prompt"),
            project_id="project",
            location="global",
            bucket_name="private",
            limit=1,
        )
        repo = BatchRepository(session)
        run = repo.prepare_run(request)
        item = repo.items(run.id)[0]
        row = append_classification_snapshot(
            session,
            ClassificationSnapshotInput(
                lyric_document_id=document.id,
                canonical_track_id=document.canonical_track_id,
                lyrics_hash=document.content_sha256,
                model_id=run.model_id,
                taxonomy_version=run.taxonomy_version,
                prompt_version=run.prompt_version,
                classification_status="error",
                error="batch_malformed_response",
            ),
        )
        item.snapshot_id = row.id
        item.state = "error"
        if condition == "resolved":
            append_classification_snapshot(
                session,
                ClassificationSnapshotInput(
                    lyric_document_id=document.id,
                    canonical_track_id=document.canonical_track_id,
                    lyrics_hash=document.content_sha256,
                    model_id=run.model_id,
                    taxonomy_version=run.taxonomy_version,
                    prompt_version=run.prompt_version,
                    classification_status="instrumental",
                ),
            )
        elif condition == "reserved":
            item.state = "reserved"
        else:
            document.rights_status = "REVOKED"
        session.commit()
        assert repo.error_retry_candidates(run.id) == []


def test_retry_run_limit_caps_selected_candidates_after_source_and_error_filters() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run = LyricClassificationBatchRun(
            kind="main",
            state="imported",
            model_id="gemini-3.8-flash",
            taxonomy_version="taxonomy",
            prompt_version="prompt",
            thinking_level="LOW",
            project_id="project",
            location="global",
            bucket_name="private",
            request_count=3,
        )
        session.add(run)
        session.flush()
        documents = [
            ingest_lyric_document(
                session,
                LyricDocumentInput(
                    canonical_track_id=uuid4(),
                    source=source,
                    source_version="1",
                    rights_status="AUTHORIZED",
                    text=f"provider lyric text {index}",
                ),
            )
            for index, source in enumerate(("GENIUS", "GENIUS", "LETRAS"))
        ]
        for line, document in enumerate(documents, start=1):
            item = LyricClassificationBatchItem(
                opaque_key=uuid4(),
                batch_run_id=run.id,
                line_number=line,
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
                    classification_status="error",
                    error="batch_malformed_response",
                    usage=(
                        UsageTelemetry(
                            input_tokens=2,
                            output_tokens=2,
                            thought_tokens=0,
                            total_tokens=4,
                        )
                        if line == 2
                        else None
                    ),
                    execution_mode="batch",
                    batch_run_id=run.id,
                    batch_item_key=item.opaque_key,
                ),
            )
            item.snapshot_id = snapshot.id
        session.commit()
        request = BatchPreparationRequest(
            kind=BatchRunKind.ERROR_RETRY,
            signature=ClassificationSignature("gemini-3.8-flash", "taxonomy", "prompt"),
            project_id="project",
            location="global",
            bucket_name="private",
        )

        retry = BatchRepository(session).prepare_retry_run(
            run.id,
            request,
            frozenset({"batch_malformed_response"}),
            limit=1,
            require_missing_usage=True,
        )

        assert retry.request_count == 1
        assert len(BatchRepository(session).items(retry.id)) == 1


def test_error_retry_candidates_skip_snapshots_already_attempted_by_a_job() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        original = LyricClassificationBatchRun(
            kind="main",
            state="imported",
            model_id="gemini-3.8-flash",
            taxonomy_version="taxonomy",
            prompt_version="prompt",
            thinking_level="LOW",
            project_id="project",
            location="global",
            bucket_name="private",
            request_count=2,
        )
        session.add(original)
        session.flush()
        documents = [
            ingest_lyric_document(
                session,
                LyricDocumentInput(
                    canonical_track_id=uuid4(),
                    source="GENIUS",
                    source_version="1",
                    rights_status="AUTHORIZED",
                    text=f"lyric text for retry test {index}",
                ),
            )
            for index in range(2)
        ]
        source_snapshots = []
        for line, document in enumerate(documents, start=1):
            item = LyricClassificationBatchItem(
                opaque_key=uuid4(),
                batch_run_id=original.id,
                line_number=line,
                lyric_document_id=document.id,
                canonical_track_id=document.canonical_track_id,
                lyrics_hash=document.content_sha256,
                model_id=original.model_id,
                taxonomy_version=original.taxonomy_version,
                prompt_version=original.prompt_version,
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
                    model_id=original.model_id,
                    taxonomy_version=original.taxonomy_version,
                    prompt_version=original.prompt_version,
                    classification_status="error",
                    error="batch_malformed_response",
                    execution_mode="batch",
                    batch_run_id=original.id,
                    batch_item_key=item.opaque_key,
                ),
            )
            item.snapshot_id = snapshot.id
            source_snapshots.append(snapshot)

        retry = LyricClassificationBatchRun(
            kind="error_retry",
            state="cleaned",
            model_id=original.model_id,
            taxonomy_version=original.taxonomy_version,
            prompt_version=original.prompt_version,
            thinking_level="LOW",
            project_id="project",
            location="global",
            bucket_name="private",
            request_count=1,
            imported_count=1,
            summary_written=True,
        )
        session.add(retry)
        session.flush()
        retry_item = LyricClassificationBatchItem(
            opaque_key=uuid4(),
            batch_run_id=retry.id,
            line_number=1,
            lyric_document_id=documents[0].id,
            canonical_track_id=documents[0].canonical_track_id,
            lyrics_hash=documents[0].content_sha256,
            model_id=retry.model_id,
            taxonomy_version=retry.taxonomy_version,
            prompt_version=retry.prompt_version,
            retry_of_snapshot_id=source_snapshots[0].id,
            state="imported",
        )
        session.add(retry_item)
        session.flush()
        retry_snapshot = append_classification_snapshot(
            session,
            ClassificationSnapshotInput(
                lyric_document_id=documents[0].id,
                canonical_track_id=documents[0].canonical_track_id,
                lyrics_hash=documents[0].content_sha256,
                model_id=retry.model_id,
                taxonomy_version=retry.taxonomy_version,
                prompt_version=retry.prompt_version,
                classification_status="classified",
                execution_mode="batch",
                batch_run_id=retry.id,
                batch_item_key=retry_item.opaque_key,
                forced_from_snapshot_id=source_snapshots[0].id,
            ),
        )
        retry_item.snapshot_id = retry_snapshot.id
        session.commit()

        candidates = BatchRepository(session).error_retry_candidates(
            original.id, frozenset({"batch_malformed_response"})
        )

        assert [candidate.lyric_document_id for candidate in candidates] == [documents[1].id]
