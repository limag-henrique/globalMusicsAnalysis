"""Real gate, in-memory database and fake adapters: no network or paid calls."""

import hashlib
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.corpus import LyricClassificationSnapshot, LyricDocument
from chart_observatory.lyrics import classification_service, review_evidence
from chart_observatory.lyrics.batch_contract import (
    BatchPreparationRequest,
    BatchRunKind,
    BatchRunState,
)
from chart_observatory.lyrics.batch_jsonl import build_batch_request, canonical_request_sha256
from chart_observatory.lyrics.batch_repository import BatchRepository
from chart_observatory.lyrics.batch_service import BatchClassificationService
from chart_observatory.lyrics.classification import PROMPT_VERSION, TAXONOMY_VERSION
from chart_observatory.lyrics.classification_gate import (
    ADJUDICATION_KEY,
    ClassificationEligibilityError,
    ClassificationGate,
)
from chart_observatory.lyrics.classification_queue import (
    ClassificationSignature,
    iter_remaining_candidates,
)
from chart_observatory.lyrics.classification_service import (
    ClassificationRequest,
    LyricsClassificationService,
)
from chart_observatory.lyrics.gemini_pipeline import (
    GeminiClassificationResponse,
    GeminiOutcomeStatus,
)
from chart_observatory.lyrics.repository import (
    ClassificationSnapshotInput,
    LyricDocumentInput,
    append_classification_snapshot,
    ingest_lyric_document,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def document(session):
    return ingest_lyric_document(
        session,
        LyricDocumentInput(
            canonical_track_id=uuid4(),
            source="GATE_TEST",
            source_version="1",
            rights_status="AUTHORIZED",
            text="A complete synthetic lyric used only in unit tests.",
        ),
    )


def change_approval(doc, **changes):
    doc.metadata_json = {
        **doc.metadata_json,
        ADJUDICATION_KEY: {**doc.metadata_json[ADJUDICATION_KEY], **changes},
    }


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"status": "pending_adjudication"}, "adjudication_invalid"),
        ({"identity_verified": False}, "identity_unverified"),
        ({"integrity_verified": False}, "integrity_unverified"),
        ({"identity_verified": "true"}, "adjudication_invalid"),
        ({"integrity_verified": 1}, "adjudication_invalid"),
        ({"recording_id": str(uuid4())}, "adjudication_binding_mismatch"),
        ({"document_id": str(uuid4())}, "adjudication_binding_mismatch"),
        ({"lyrics_hash": "a" * 64}, "adjudication_binding_mismatch"),
        ({"source": "OTHER"}, "adjudication_binding_mismatch"),
        ({"gate_version": "old"}, "adjudication_invalid"),
        ({"adjudicator": "   "}, "adjudication_invalid"),
        ({"method": "provider_metadata_match"}, "adjudication_invalid"),
        ({"evidence_url": "http://example.org/proof"}, "adjudication_evidence_invalid"),
        ({"evidence_sha256": "not-a-hash"}, "adjudication_invalid"),
        ({"verified_at": "2026-11-01T10:00:00"}, "adjudication_invalid"),
        ({"adjudicated_at": "2026-10-31T10:00:00Z"}, "adjudication_evidence_invalid"),
    ],
)
def test_gate_requires_explicit_bound_adjudication(session, adjudicate_lyric, changes, reason):
    doc = adjudicate_lyric(document(session))
    change_approval(doc, **changes)
    decision = ClassificationGate.load().assess(doc)
    assert not decision.eligible
    assert decision.reason == reason


def test_legacy_documents_are_preserved_without_implicit_approval(session):
    doc = document(session)
    session.commit()
    original = (doc.text, doc.content_sha256, dict(doc.metadata_json))
    assert ClassificationGate.load().assess(doc).reason == "adjudication_missing"
    assert list(iter_remaining_candidates(session, ClassificationSignature("m", "t", "p"))) == []
    assert (doc.text, doc.content_sha256, doc.metadata_json) == original
    assert session.scalar(select(func.count()).select_from(LyricDocument)) == 1
    assert session.scalar(select(func.count()).select_from(LyricClassificationSnapshot)) == 0


def test_hash_checks_actual_bytes_and_new_text_needs_new_adjudication(session, adjudicate_lyric):
    doc = adjudicate_lyric(document(session))
    doc.text += " Added verse."
    assert ClassificationGate.load().assess(doc).reason == "text_hash_mismatch"
    doc.content_sha256 = hashlib.sha256(doc.text.encode()).hexdigest()
    assert ClassificationGate.load().assess(doc).reason == "adjudication_binding_mismatch"


@pytest.mark.parametrize("hold", ["source", "quarantine", "report", "rights"])
def test_holds_are_never_bypassed(session, adjudicate_lyric, monkeypatch, hold):
    import chart_observatory.lyrics.classification_gate as gate_module

    doc = adjudicate_lyric(document(session))
    if hold == "source":
        monkeypatch.setattr(
            gate_module, "load_suspended_sources", lambda _path: frozenset({doc.source})
        )
    elif hold == "quarantine":
        monkeypatch.setattr(gate_module, "excluded_document_ids", lambda _: frozenset({doc.id}))
    elif hold == "report":
        monkeypatch.setattr(
            review_evidence,
            "load_review_evidence",
            lambda: [
                {
                    "document_id": str(doc.id),
                    "lyrics_hash": doc.content_sha256,
                    "status": "pending_adjudication",
                    "decision": "review_recorded",
                }
            ],
        )
    else:
        doc.rights_status = "UNVERIFIED"
    assert not ClassificationGate.load().assess(doc).eligible
    assert (
        list(
            iter_remaining_candidates(
                session,
                ClassificationSignature("m", "t", "p"),
                include_identity_holds=True,
                only_unclassified=False,
            )
        )
        == []
    )


class FakeClassifier:
    def __init__(self):
        self.generations = self.estimates = 0

    def classify(self, *_args):
        self.generations += 1
        return GeminiClassificationResponse(outcome=GeminiOutcomeStatus.BLOCKED, error="test")

    def estimate_input_tokens(self, *_args):
        self.estimates += 1
        return 10


def online_service(session, classifier):
    return LyricsClassificationService(
        session,
        classifier,
        SimpleNamespace(
            gemini_model="fixed-test-model",
            gemini_output_token_allowance=100,
            gemini_input_usd_per_million_tokens=Decimal("1"),
            gemini_output_usd_per_million_tokens=Decimal("2"),
            gemini_thought_usd_per_million_tokens=Decimal("2"),
        ),
    )


@pytest.mark.parametrize(
    "run_request",
    [
        ClassificationRequest(),
        ClassificationRequest(force=True),
        ClassificationRequest(only_unclassified=True),
        ClassificationRequest(estimate_cost=True),
        ClassificationRequest(force=True, estimate_cost=True),
        ClassificationRequest(max_cost_usd=Decimal("1")),
    ],
)
def test_every_online_mode_blocks_unverified_without_provider_calls(session, run_request):
    document(session)
    fake = FakeClassifier()
    service = online_service(session, fake)
    assert service.run(run_request).selected == 0
    assert service.count_initial_pass_remaining() == 0
    assert (fake.generations, fake.estimates) == (0, 0)
    assert session.scalar(select(func.count()).select_from(LyricClassificationSnapshot)) == 0


def test_approved_online_estimate_force_and_idempotence(session, adjudicate_lyric, monkeypatch):
    monkeypatch.setattr(classification_service, "PROMPT_VERSION", "lyrics-classification-prompt-v2")
    adjudicate_lyric(document(session))
    fake = FakeClassifier()
    service = online_service(session, fake)
    assert service.count_initial_pass_remaining() == 1
    assert service.run(ClassificationRequest(estimate_cost=True)).estimated_candidates == 1
    service.run(ClassificationRequest())
    assert service.run(ClassificationRequest()).skipped_idempotent == 1
    service.run(ClassificationRequest(force=True))
    assert (fake.generations, fake.estimates) == (2, 1)
    assert service.count_initial_pass_remaining() == 0


def test_evidence_revoked_between_estimate_and_generation_stops_dispatch(
    session,
    adjudicate_lyric,
    monkeypatch,
):
    monkeypatch.setattr(classification_service, "PROMPT_VERSION", "lyrics-classification-prompt-v2")
    doc = adjudicate_lyric(document(session))
    fake = FakeClassifier()
    service = online_service(session, fake)
    original_estimate = service._estimate

    def estimate_then_revoke(*args):
        original_estimate(*args)
        change_approval(doc, integrity_verified=False)
        session.commit()

    monkeypatch.setattr(service, "_estimate", estimate_then_revoke)
    with pytest.raises(ClassificationEligibilityError, match="integrity_unverified"):
        service.run(ClassificationRequest(max_cost_usd=Decimal("1")))
    assert fake.generations == 0


def batch_request():
    return BatchPreparationRequest(
        kind=BatchRunKind.CANARY,
        signature=ClassificationSignature("gemini-3.8-flash", TAXONOMY_VERSION, PROMPT_VERSION),
        project_id="test",
        bucket_name="test",
        location="global",
        limit=10,
        include_identity_holds=True,
    )


def batch_service(session, tmp_path, storage=None, vertex=None):
    return BatchClassificationService(
        session,
        SimpleNamespace(),
        storage or SimpleNamespace(),
        vertex or SimpleNamespace(),
        temporary_root=tmp_path,
        cost_guard=lambda *_args, **_kwargs: Decimal(0),
    )


def test_batch_reservation_blocks_legacy_and_preserves_documents(session):
    doc = document(session)
    session.commit()
    with pytest.raises(ValueError, match="no provider-eligible"):
        BatchRepository(session).prepare_run(batch_request())
    assert session.get(LyricDocument, doc.id).text == doc.text


@pytest.mark.parametrize("change", ["revoke", "text", "binding", "missing_approval"])
def test_batch_export_rechecks_adjudication(session, adjudicate_lyric, tmp_path, change):
    doc = adjudicate_lyric(document(session))
    run = BatchRepository(session).prepare_run(batch_request())
    if change == "revoke":
        change_approval(doc, integrity_verified=False)
    elif change == "text":
        doc.text += " corrupt bytes"
    elif change == "binding":
        BatchRepository(session).items(run.id)[0].lyrics_hash = "b" * 64
    else:
        doc.metadata_json = {}
    session.commit()
    with pytest.raises(ClassificationEligibilityError):
        list(batch_service(session, tmp_path)._iter_export_items(run.id))


@pytest.mark.parametrize("change", ["revoke", "language", "request_hash", "count", "prompt"])
def test_uploaded_batch_is_revalidated_before_storage_or_vertex(
    session,
    adjudicate_lyric,
    tmp_path,
    change,
):
    doc = adjudicate_lyric(document(session))
    run = BatchRepository(session).prepare_run(batch_request())
    calls = []
    storage = SimpleNamespace(verify=lambda _: calls.append("verify"))
    vertex = SimpleNamespace(submit=lambda _: calls.append("submit"))
    service = batch_service(session, tmp_path, storage, vertex)
    # Existing revision budget protection is kept; this unit tests the independent QA boundary.
    service._revision_guard = lambda *_args, **_kwargs: None
    for export in service._iter_export_items(run.id):
        export.item.request_sha256 = canonical_request_sha256(
            build_batch_request(export.item, export.candidate, export.config)
        )
    run.state = "uploaded"
    run.conservative_cost_usd = Decimal("0.01")
    if change == "revoke":
        change_approval(doc, identity_verified=False)
    elif change == "language":
        doc.language_code = "changed"
    elif change == "request_hash":
        BatchRepository(session).items(run.id)[0].request_sha256 = "f" * 64
    elif change == "prompt":
        run.prompt_version = "stale-prompt"
    else:
        run.request_count += 1
    session.commit()
    with pytest.raises(ClassificationEligibilityError):
        service.submit(run.id, Decimal("1"))
    assert calls == []
    assert run.state == "uploaded"
    assert run.provider_job_name is None


def test_approved_uploaded_batch_can_submit_with_fake_adapters(
    session,
    adjudicate_lyric,
    tmp_path,
):
    adjudicate_lyric(document(session))
    run = BatchRepository(session).prepare_run(batch_request())
    calls = []

    def submit(_run):
        calls.append("submit")
        return SimpleNamespace(name="fake-job", state=BatchRunState.SUBMITTED)

    service = batch_service(
        session,
        tmp_path,
        SimpleNamespace(verify=lambda _: calls.append("verify")),
        SimpleNamespace(submit=submit),
    )
    service._revision_guard = lambda *_args, **_kwargs: None
    for export in service._iter_export_items(run.id):
        export.item.request_sha256 = canonical_request_sha256(
            build_batch_request(export.item, export.candidate, export.config)
        )
    run.state = "uploaded"
    run.conservative_cost_usd = Decimal("0.01")
    run.source_uri = "gs://test/input.jsonl"
    run.source_generation = 1
    run.source_sha256 = "a" * 64
    run.source_byte_count = 100
    session.commit()
    assert service.submit(run.id, Decimal("1")).name == "fake-job"
    assert calls == ["verify", "submit"]
    assert run.state == "submitted"


def test_retry_rechecks_adjudication_even_with_identity_override(session, adjudicate_lyric):
    doc = adjudicate_lyric(document(session))
    repository = BatchRepository(session)
    run = repository.prepare_run(batch_request())
    item = repository.items(run.id)[0]
    snapshot = append_classification_snapshot(
        session,
        ClassificationSnapshotInput(
            lyric_document_id=doc.id,
            canonical_track_id=doc.canonical_track_id,
            lyrics_hash=doc.content_sha256,
            model_id=run.model_id,
            taxonomy_version=run.taxonomy_version,
            prompt_version=run.prompt_version,
            classification_status="error",
            error="synthetic_provider_error",
            execution_mode="batch",
            batch_run_id=run.id,
            batch_item_key=item.opaque_key,
        ),
    )
    item.snapshot_id = snapshot.id
    item.state = "error"
    run.state = "imported"
    session.commit()
    assert len(repository.error_retry_candidates(run.id, include_identity_holds=True)) == 1
    change_approval(doc, integrity_verified=False)
    session.commit()
    assert repository.error_retry_candidates(run.id, include_identity_holds=True) == []
    with pytest.raises(ValueError, match="no error snapshots"):
        repository.prepare_retry_run(run.id, batch_request())


def test_missing_policy_fails_closed_before_token_count_or_generation(session, monkeypatch):
    document(session)

    def missing():
        raise FileNotFoundError("synthetic missing review policy")

    monkeypatch.setattr(review_evidence, "load_review_evidence", missing)
    fake = FakeClassifier()
    with pytest.raises(FileNotFoundError):
        online_service(session, fake).run(ClassificationRequest(force=True, estimate_cost=True))
    assert (fake.generations, fake.estimates) == (0, 0)


def test_legacy_backfill_cannot_dispatch_unbound_lyrics():
    from chart_observatory.lyrics.lyrics_backfill import LyricsEngine, run_full_automation

    with pytest.raises(ClassificationEligibilityError, match="unbound_legacy_annotation"):
        LyricsEngine(skip_gemini=True).annotate("id", "title", "artist", "raw lyric")
    with pytest.raises(ClassificationEligibilityError, match="skip-gemini"):
        run_full_automation(skip_gemini=False)
