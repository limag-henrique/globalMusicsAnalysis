from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.corpus import LyricClassificationSnapshot
from chart_observatory.db.models.lyrics_batch import (
    LyricClassificationBatchItem,
    LyricClassificationBatchRun,
)
from chart_observatory.lyrics import batch_service as batch_service_module
from chart_observatory.lyrics.batch_contract import BatchRunKind, BatchRunState
from chart_observatory.lyrics.batch_importer import BatchImportSummary
from chart_observatory.lyrics.batch_repository import BatchRepository
from chart_observatory.lyrics.batch_service import (
    BATCH_MAX_OUTPUT_TOKENS,
    BatchClassificationService,
    BatchRunStatus,
    CostBudgetExceeded,
    PilotNotAccepted,
    enforce_cumulative_cost_cap,
)
from chart_observatory.lyrics.batch_storage import StoredObject
from chart_observatory.lyrics.batch_vertex import VertexBatchJob
from chart_observatory.lyrics.classification import PROMPT_VERSION, TAXONOMY_VERSION
from chart_observatory.lyrics.classification_queue import (
    ClassificationSignature,
    iter_remaining_candidates,
)
from chart_observatory.lyrics.repository import LyricDocumentInput, ingest_lyric_document


def settings(**overrides):
    values = {
        "gemini_model": "gemini-3.8-flash",
        "google_cloud_project": "project",
        "google_cloud_location": "global",
        "gemini_thinking_level": "LOW",
        "gemini_batch_bucket": "private-bucket",
        "gemini_batch_input_usd_per_million_tokens": Decimal("0.375"),
        "gemini_batch_output_usd_per_million_tokens": Decimal("1.875"),
        "gemini_output_token_allowance": 4096,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _attach_batch_snapshot(
    session: Session,
    run: LyricClassificationBatchRun,
    *,
    error_code: str | None,
    estimated_cost: Decimal | None,
) -> None:
    document = ingest_lyric_document(
        session,
        LyricDocumentInput(
            canonical_track_id=uuid4(),
            source=str(run.id),
            source_version="1",
            rights_status="AUTHORIZED",
            text="private lyric text",
        ),
    )
    item = LyricClassificationBatchItem(
        opaque_key=uuid4(),
        batch_run_id=run.id,
        line_number=1,
        lyric_document_id=document.id,
        canonical_track_id=document.canonical_track_id,
        lyrics_hash=document.content_sha256,
        model_id=run.model_id,
        taxonomy_version=run.taxonomy_version,
        prompt_version=run.prompt_version,
        state="missing" if error_code == "batch_missing_output" else "imported",
        error_code=error_code,
    )
    session.add(item)
    session.flush()
    snapshot = LyricClassificationSnapshot(
        lyric_document_id=document.id,
        canonical_track_id=document.canonical_track_id,
        lyrics_hash=document.content_sha256,
        model_id=run.model_id,
        taxonomy_version=run.taxonomy_version,
        prompt_version=run.prompt_version,
        classification_status="error" if error_code else "classified",
        error=error_code,
        classified_at=datetime.now(UTC),
        estimated_cost_usd=estimated_cost,
        batch_run_id=run.id,
        batch_item_key=item.opaque_key,
        execution_mode="batch",
    )
    session.add(snapshot)
    session.flush()
    item.snapshot_id = snapshot.id


def test_resumed_import_rebuilds_known_cost_from_all_durable_snapshots(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run = LyricClassificationBatchRun(
            kind="main",
            state="failed",
            model_id="gemini-3.8-flash",
            taxonomy_version="taxonomy",
            prompt_version="prompt",
            thinking_level="LOW",
            project_id="project",
            location="global",
            bucket_name="private-bucket",
            output_uri_prefix="gs://private-bucket/runs/output/",
            request_count=1,
            imported_count=1,
            known_cost_usd=None,
        )
        session.add(run)
        session.flush()
        _attach_batch_snapshot(
            session, run, error_code=None, estimated_cost=Decimal("1.25")
        )
        session.commit()
        storage = SimpleNamespace(
            object_names=lambda _prefix: ["runs/output/predictions.jsonl"],
            iter_lines=lambda _prefix: iter(()),
        )
        monkeypatch.setattr(
            batch_service_module.BatchImporter,
            "import_available",
            lambda *_args: BatchImportSummary(known_cost_usd=Decimal("0.50")),
        )
        service = BatchClassificationService(
            session, settings(), storage, SimpleNamespace(), adc_check=lambda: None
        )

        service.import_results(run.id)

        session.refresh(run)
        assert run.known_cost_usd == Decimal("1.25")


def test_cumulative_budget_reserves_all_runs_and_never_exceeds_600() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            LyricClassificationBatchRun(
                kind="main",
                state="uploaded",
                model_id="gemini-3.8-flash",
                taxonomy_version="taxonomy",
                prompt_version="prompt",
                thinking_level="LOW",
                project_id="p",
                location="global",
                bucket_name="b",
                request_count=1,
                conservative_cost_usd=Decimal("500"),
            )
        )
        session.commit()

        enforce_cumulative_cost_cap(session, Decimal("100"), Decimal("600"))
        with pytest.raises(CostBudgetExceeded):
            enforce_cumulative_cost_cap(session, Decimal("100.01"), Decimal("600"))
        with pytest.raises(CostBudgetExceeded, match="cannot exceed"):
            enforce_cumulative_cost_cap(session, Decimal("1"), Decimal("601"))


def test_batch_output_ceiling_keeps_current_corpus_within_output_only_budget() -> None:
    output_tokens = 159_070 * BATCH_MAX_OUTPUT_TOKENS
    output_cost = Decimal(output_tokens) * Decimal("1.875") / Decimal(1_000_000)

    assert BATCH_MAX_OUTPUT_TOKENS == 1_024
    assert output_cost == Decimal("305.414400")
    assert output_cost < Decimal("600")


def test_cumulative_budget_keeps_conservative_reservation_until_actual_is_higher() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            LyricClassificationBatchRun(
                kind="main",
                state="running",
                model_id="gemini-3.8-flash",
                taxonomy_version="taxonomy",
                prompt_version="prompt",
                thinking_level="LOW",
                project_id="p",
                location="global",
                bucket_name="b",
                request_count=1,
                conservative_cost_usd=Decimal("500"),
                known_cost_usd=Decimal("1"),
            )
        )
        session.commit()

        with pytest.raises(CostBudgetExceeded):
            enforce_cumulative_cost_cap(session, Decimal("101"), Decimal("600"))


def test_completed_run_releases_unused_reservation_when_cost_is_known() -> None:
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
            project_id="p",
            location="global",
            bucket_name="b",
            request_count=1,
            imported_count=1,
            summary_written=True,
            conservative_cost_usd=Decimal("500"),
            known_cost_usd=Decimal("1"),
        )
        session.add(run)
        session.flush()
        _attach_batch_snapshot(
            session, run, error_code=None, estimated_cost=Decimal("1")
        )
        session.commit()

        total = enforce_cumulative_cost_cap(session, Decimal("101"), Decimal("600"))

    assert total == Decimal("102")


def test_provider_succeeded_and_fully_reconciled_run_releases_unused_reservation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        run = LyricClassificationBatchRun(
            kind="error_retry",
            state="succeeded",
            model_id="gemini-3.8-flash",
            taxonomy_version="taxonomy",
            prompt_version="prompt",
            thinking_level="LOW",
            project_id="p",
            location="global",
            bucket_name="b",
            request_count=1,
            imported_count=1,
            summary_written=True,
            conservative_cost_usd=Decimal("500"),
            known_cost_usd=Decimal("1"),
        )
        session.add(run)
        session.flush()
        _attach_batch_snapshot(session, run, error_code=None, estimated_cost=Decimal("1"))
        session.commit()

        total = enforce_cumulative_cost_cap(session, Decimal("101"), Decimal("600"))

    assert total == Decimal("102")


def test_completed_missing_output_and_unpriced_error_keep_reservations() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        missing_output_run = LyricClassificationBatchRun(
            kind="main",
            state="imported",
            model_id="gemini-3.8-flash",
            taxonomy_version="taxonomy",
            prompt_version="prompt",
            thinking_level="LOW",
            project_id="p",
            location="global",
            bucket_name="b",
            request_count=1,
            imported_count=1,
            error_count=1,
            summary_written=True,
            conservative_cost_usd=Decimal("500"),
            known_cost_usd=Decimal("1"),
        )
        session.add(missing_output_run)
        session.flush()
        _attach_batch_snapshot(
            session,
            missing_output_run,
            error_code="batch_missing_output",
            estimated_cost=None,
        )
        session.commit()

        # A missing GCS response can have expired after successful, billed generation.
        total = enforce_cumulative_cost_cap(session, Decimal("100"), Decimal("600"))
        assert total == Decimal("600")
        with pytest.raises(CostBudgetExceeded):
            enforce_cumulative_cost_cap(session, Decimal("101"), Decimal("600"))

        unknown_run = LyricClassificationBatchRun(
            kind="main",
            state="imported",
            model_id="gemini-3.8-flash",
            taxonomy_version="taxonomy",
            prompt_version="prompt",
            thinking_level="LOW",
            project_id="p",
            location="global",
            bucket_name="b",
            request_count=1,
            imported_count=1,
            error_count=1,
            summary_written=True,
            conservative_cost_usd=Decimal("500"),
            known_cost_usd=Decimal("1"),
        )
        session.add(unknown_run)
        session.flush()
        _attach_batch_snapshot(
            session,
            unknown_run,
            error_code="batch_missing_usage",
            estimated_cost=None,
        )
        session.commit()

        with pytest.raises(CostBudgetExceeded):
            enforce_cumulative_cost_cap(session, Decimal("100"), Decimal("600"))



def test_main_is_blocked_until_pilot_acceptance_is_durable() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = BatchClassificationService(
            session, settings(), SimpleNamespace(), SimpleNamespace(), adc_check=lambda: None
        )

        with pytest.raises(PilotNotAccepted):
            service.prepare_main(Decimal("100"))


def test_cleaned_imported_canary_remains_eligible_for_pilot() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        canary = LyricClassificationBatchRun(
            kind=BatchRunKind.CANARY.value,
            state=BatchRunState.CLEANED.value,
            model_id="gemini-3.8-flash",
            taxonomy_version=TAXONOMY_VERSION,
            prompt_version=PROMPT_VERSION,
            thinking_level="LOW",
            project_id="project",
            location="global",
            bucket_name="private-bucket",
            request_count=1,
        )
        session.add(canary)
        session.commit()
        service = BatchClassificationService(
            session, settings(), SimpleNamespace(), SimpleNamespace(), adc_check=lambda: None
        )

        assert service._latest_imported_run(BatchRunKind.CANARY) == canary


def test_preflight_rejects_wrong_model_before_external_checks() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = BatchClassificationService(
            session,
            settings(gemini_model="gemini-2.5-flash"),
            SimpleNamespace(),
            SimpleNamespace(),
            adc_check=lambda: None,
        )

        with pytest.raises(ValueError, match="gemini-3.8-flash"):
            service.preflight()


def test_preflight_checks_exact_vertex_service_agent_binding() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    checked = []
    storage = SimpleNamespace(preflight=lambda agent: checked.append(agent))
    with Session(engine) as session:
        service = BatchClassificationService(
            session,
            settings(),
            storage,
            SimpleNamespace(),
            adc_check=lambda: None,
            project_number_resolver=lambda _project: "123456",
        )

        report = service.preflight()

    assert report.migration_ready is True
    assert checked == ["service-123456@gcp-sa-aiplatform.iam.gserviceaccount.com"]


class FakeBatchStorage:
    def __init__(self, fail_upload_number: int | None = None) -> None:
        self.fail_upload_number = fail_upload_number
        self.uploaded: list[StoredObject] = []
        self.deleted: list[StoredObject] = []

    def preflight(self, _agent: str) -> None:
        return None

    def upload(self, path: Path, object_name: str) -> StoredObject:
        if self.fail_upload_number == len(self.uploaded) + 1:
            raise RuntimeError("simulated upload failure")
        stored = StoredObject(
            uri=f"gs://private-bucket/{object_name}",
            name=object_name,
            generation=len(self.uploaded) + 1,
            sha256="a" * 64,
            byte_count=path.stat().st_size,
        )
        self.uploaded.append(stored)
        path.unlink()
        return stored

    def delete(self, stored: StoredObject) -> None:
        self.deleted.append(stored)


class FixedTokenCounter:
    def estimate_input_tokens(self, _lyrics: str, _language: str | None = None) -> int:
        return 100


def _service_with_two_lyrics(
    session: Session, tmp_path: Path, storage: FakeBatchStorage
) -> BatchClassificationService:
    for number in range(2):
        ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source=str(number),
                source_version="1",
                rights_status="AUTHORIZED",
                text=f"provider lyric text number {number} with enough words for classification",
            ),
        )
    session.commit()
    assert (
        len(
            list(
                iter_remaining_candidates(
                    session,
                    ClassificationSignature("gemini-3.8-flash", TAXONOMY_VERSION, PROMPT_VERSION),
                )
            )
        )
        == 2
    )
    return BatchClassificationService(
        session,
        settings(),
        storage,
        SimpleNamespace(),
        token_counter=FixedTokenCounter(),
        adc_check=lambda: None,
        project_number_resolver=lambda _project: "123456",
        temporary_root=tmp_path,
    )


def _force_one_request_per_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    original = batch_service_module.write_batch_jsonl

    def split_writer(run_id: UUID, items, directory: Path):
        return original(run_id, items, directory, max_requests=1)

    monkeypatch.setattr(batch_service_module, "write_batch_jsonl", split_writer)


def test_prepare_creates_one_independent_run_per_jsonl_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _force_one_request_per_artifact(monkeypatch)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    storage = FakeBatchStorage()
    with Session(engine) as session:
        service = _service_with_two_lyrics(session, tmp_path, storage)

        prepared = service._prepare(BatchRunKind.PILOT, 2, Decimal("10"))

        assert [item.request_count for item in prepared] == [1, 1]
        assert len({item.run_id for item in prepared}) == 2
        assert len(storage.uploaded) == 2
        assert all(len(BatchRepository(session).items(item.run_id)) == 1 for item in prepared)


def test_prepare_deletes_already_uploaded_shards_when_a_later_upload_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _force_one_request_per_artifact(monkeypatch)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    storage = FakeBatchStorage(fail_upload_number=2)
    with Session(engine) as session:
        service = _service_with_two_lyrics(session, tmp_path, storage)

        with pytest.raises(RuntimeError, match="simulated upload failure"):
            service._prepare(BatchRunKind.PILOT, 2, Decimal("10"))

        runs = list(session.scalars(select(LyricClassificationBatchRun)))
        assert storage.deleted == storage.uploaded
        assert {run.state for run in runs} == {"failed"}


def test_status_reports_completed_count_and_percent(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    run = LyricClassificationBatchRun(
        kind="main",
        state="submitted",
        model_id="gemini-3.8-flash",
        taxonomy_version="taxonomy",
        prompt_version="prompt",
        thinking_level="LOW",
        project_id="project",
        location="global",
        bucket_name="private-bucket",
        request_count=4,
        provider_job_name="projects/p/locations/global/batchPredictionJobs/1",
    )
    job = VertexBatchJob(
        name=run.provider_job_name,
        display_name="lyrics-batch-test",
        state=BatchRunState.RUNNING,
        source_uri="gs://private/input.jsonl",
        output_prefix="gs://private/output/",
        successful_count=2,
        failed_count=1,
        provider_error=None,
    )
    with Session(engine) as session:
        session.add(run)
        session.commit()
        service = BatchClassificationService(
            session,
            settings(),
            SimpleNamespace(),
            SimpleNamespace(get=lambda _name: job),
            adc_check=lambda: None,
            temporary_root=tmp_path,
        )

        status = service.status(run.id)

    assert isinstance(status, BatchRunStatus)
    assert status.completed_count == 3
    assert status.request_count == 4
    assert status.progress_percent == Decimal("75")
