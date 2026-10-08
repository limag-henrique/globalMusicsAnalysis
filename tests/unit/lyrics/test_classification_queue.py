from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.lyrics_batch import (
    LyricClassificationBatchItem,
    LyricClassificationBatchRun,
)
from chart_observatory.lyrics.classification_queue import (
    ClassificationSignature,
    local_classification_status,
    select_remaining_candidates,
)
from chart_observatory.lyrics.repository import (
    ClassificationSnapshotInput,
    LyricDocumentInput,
    append_classification_snapshot,
    ingest_lyric_document,
)


def test_selection_excludes_handled_and_active_batch_signatures() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    signature = ClassificationSignature("gemini-3.8-flash", "taxonomy", "prompt")
    with Session(engine) as session:
        handled = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="s",
                source_version="1",
                rights_status="AUTHORIZED",
                text="handled lyric text long enough",
            ),
        )
        active = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="s",
                source_version="1",
                rights_status="AUTHORIZED",
                text="active lyric text long enough",
            ),
        )
        remaining = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="s",
                source_version="1",
                rights_status="AUTHORIZED",
                text="remaining lyric text long enough",
            ),
        )
        append_classification_snapshot(
            session,
            ClassificationSnapshotInput(
                lyric_document_id=handled.id,
                canonical_track_id=handled.canonical_track_id,
                lyrics_hash=handled.content_sha256,
                model_id=signature.model_id,
                taxonomy_version=signature.taxonomy_version,
                prompt_version=signature.prompt_version,
                classification_status="classified",
            ),
        )
        run = LyricClassificationBatchRun(
            kind="main",
            state="prepared",
            model_id=signature.model_id,
            taxonomy_version=signature.taxonomy_version,
            prompt_version=signature.prompt_version,
            thinking_level="LOW",
            project_id="p",
            location="global",
            bucket_name="b",
        )
        session.add(run)
        session.flush()
        session.add(
            LyricClassificationBatchItem(
                opaque_key=uuid4(),
                batch_run_id=run.id,
                line_number=1,
                lyric_document_id=active.id,
                canonical_track_id=active.canonical_track_id,
                lyrics_hash=active.content_sha256,
                model_id=signature.model_id,
                taxonomy_version=signature.taxonomy_version,
                prompt_version=signature.prompt_version,
                state="reserved",
            )
        )
        session.commit()

        candidates = select_remaining_candidates(session, signature, limit=None)

        assert [candidate.lyric_document_id for candidate in candidates] == [remaining.id]


def test_local_status_distinguishes_instrumental_short_and_provider_text() -> None:
    from chart_observatory.lyrics.classification_queue import ClassificationCandidate

    base = dict(
        lyric_document_id=uuid4(),
        canonical_track_id=uuid4(),
        lyrics_hash="a" * 64,
        language=None,
    )
    assert (
        local_classification_status(ClassificationCandidate(**base, text="", instrumental=True))
        == "instrumental"
    )
    assert (
        local_classification_status(
            ClassificationCandidate(**base, text="short", instrumental=False)
        )
        == "insufficient_text"
    )
    assert (
        local_classification_status(
            ClassificationCandidate(**base, text="long enough lyric text here", instrumental=False)
        )
        is None
    )
