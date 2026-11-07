"""Actual restored PostgreSQL schema; synthetic text, offline adapters, guarded endpoint."""

import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import google.auth
import httpx
import pytest
import requests
from google import genai
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from chart_observatory.db.models.corpus import LyricClassificationSnapshot, LyricDocument
from chart_observatory.lyrics import classification_service, review_evidence
from chart_observatory.lyrics.batch_contract import BatchRunState
from chart_observatory.lyrics.batch_repository import BatchRepository
from chart_observatory.lyrics.batch_service import BatchClassificationService
from chart_observatory.lyrics.batch_storage import StoredObject
from chart_observatory.lyrics.classification_gate import (
    ADJUDICATION_KEY,
    GATE_VERSION,
    ClassificationEligibilityError,
    ClassificationGate,
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
from chart_observatory.tracks.repository import TrackRepository

pytestmark = pytest.mark.integration
MARKER = "classification-gate-isolated-copy-v1"


@pytest.fixture(scope="module")
def engine():
    url = os.environ.get("CHART_OBSERVATORY_TEST_DATABASE_URL")
    root = os.environ.get("CHART_OBSERVATORY_GATE_CLONE_ROOT")
    run_id = os.environ.get("CHART_OBSERVATORY_GATE_CLONE_RUN_ID")
    if not url or not root or not run_id:
        pytest.skip("requires the guarded offline PostgreSQL clone harness")
    parsed = make_url(url)
    assert parsed.host == "127.0.0.1" and parsed.port == 55439
    assert parsed.database == f"gate_integration_{run_id}"
    clone_root = Path(root).resolve()
    assert clone_root.is_relative_to(
        (Path(os.environ["LOCALAPPDATA"]) / "ChartObservatory/gate-validation").resolve()
    )
    identity = json.loads((clone_root / "identity.json").read_text())
    assert identity["marker"] == MARKER and identity["run_id"] == run_id
    engine = create_engine(url, pool_size=4, max_overflow=2)
    with engine.connect() as conn:
        assert Path(conn.scalar(text("SHOW data_directory"))).resolve() == clone_root / "cluster"
        assert conn.scalar(
            text(
                "SELECT shobj_description(oid, 'pg_database') "
                "FROM pg_database WHERE datname=current_database()"
            )
        ) == (f"{MARKER}:{run_id}")
        assert conn.scalar(text("SHOW server_version_num")).startswith("16")
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    def denied(*_args, **_kwargs):
        raise AssertionError("Network/ADC/real AI clients are forbidden in this integration suite")

    monkeypatch.setattr(httpx.Client, "send", denied)
    monkeypatch.setattr(requests.sessions.Session, "request", denied)
    monkeypatch.setattr(google.auth, "default", denied)
    monkeypatch.setattr(genai, "Client", denied)
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def session(engine):
    # Application commits release savepoints; the outer transaction rolls back
    # synthetic data, including immutable snapshots, after every test.
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session
        transaction.rollback()


def approve(doc):
    doc.metadata_json = {
        **doc.metadata_json,
        ADJUDICATION_KEY: {
            "gate_version": GATE_VERSION,
            "adjudication_id": f"postgres-fixture-{doc.id}",
            "document_id": str(doc.id),
            "recording_id": str(doc.canonical_track_id),
            "lyrics_hash": doc.content_sha256,
            "source": doc.source,
            "status": "approved",
            "identity_verified": True,
            "integrity_verified": True,
            "method": "human_audio_verification",
            "evidence_url": "https://example.org/test-only",
            "evidence_sha256": "e" * 64,
            "verified_at": "2026-11-01T10:00:00Z",
            "adjudicated_at": "2026-11-01T11:00:00Z",
            "adjudicator": "Synthetic PG reviewer",
        },
    }
    return doc


def seed(session, *, approved=False, lyric="Letra sintética completa: início, meio e final. 音楽"):
    track = TrackRepository(session).create_track("Synthetic gate integration recording")
    doc = ingest_lyric_document(
        session,
        LyricDocumentInput(
            canonical_track_id=track.id,
            source="PG_GATE_TEST",
            source_version="1",
            rights_status="AUTHORIZED",
            language_code="pt",
            text=lyric,
        ),
    )
    if approved:
        approve(doc)
    session.commit()
    return doc


def revoke(doc):
    doc.metadata_json = {
        **doc.metadata_json,
        ADJUDICATION_KEY: {
            **doc.metadata_json[ADJUDICATION_KEY],
            "integrity_verified": False,
        },
    }


class FakeClassifier:
    def __init__(self):
        self.generations = self.estimates = 0

    def classify(self, *_args):
        self.generations += 1
        return GeminiClassificationResponse(
            outcome=GeminiOutcomeStatus.BLOCKED, error="Synthetic offline outcome"
        )

    def estimate_input_tokens(self, *_args):
        self.estimates += 1
        return 20


def online(session, fake, monkeypatch):
    # Current v3 online dispatch is intentionally disabled by its budget policy.
    # Exercise the allowed v2 branch with fake adapters, never change production config.
    monkeypatch.setattr(classification_service, "PROMPT_VERSION", "lyrics-classification-prompt-v2")
    return LyricsClassificationService(
        session,
        fake,
        SimpleNamespace(
            gemini_model="postgres-fake-model",
            gemini_output_token_allowance=100,
            gemini_input_usd_per_million_tokens=Decimal(1),
            gemini_output_usd_per_million_tokens=Decimal(2),
            gemini_thought_usd_per_million_tokens=Decimal(2),
        ),
    )


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.uploads = self.verifications = 0

    def preflight(self, _agent):
        pass

    def upload(self, path, name):
        body = path.read_bytes()
        self.objects[name] = body
        self.uploads += 1
        return StoredObject(
            f"gs://offline-test/{name}", name, 1, hashlib.sha256(body).hexdigest(), len(body)
        )

    def verify(self, stored):
        assert hashlib.sha256(self.objects[stored.name]).hexdigest() == stored.sha256
        self.verifications += 1

    def delete(self, stored):
        self.objects.pop(stored.name, None)


class FakeVertex:
    def __init__(self):
        self.submissions = 0

    def submit(self, run):
        self.submissions += 1
        return SimpleNamespace(name=f"offline-job-{run.id}", state=BatchRunState.SUBMITTED)


class OfflineBudget:
    """No real ledger is read or attested by these tests of the independent QA gate."""

    def __call__(self, *_args, **_kwargs):
        return Decimal(0)

    def reconcile(self, _session):
        return self

    def preview(self, *_args):
        pass


def batch(session, tmp_path):
    counter, storage, vertex = FakeClassifier(), FakeStorage(), FakeVertex()
    service = BatchClassificationService(
        session,
        SimpleNamespace(
            gemini_model="gemini-3.8-flash",
            google_cloud_project="offline-test",
            google_cloud_location="global",
            gemini_thinking_level="LOW",
            gemini_batch_bucket="offline-test",
            gemini_batch_input_usd_per_million_tokens=Decimal("0.375"),
            gemini_batch_output_usd_per_million_tokens=Decimal("1.875"),
        ),
        storage,
        vertex,
        token_counter=counter,
        adc_check=lambda: None,
        project_number_resolver=lambda _: "123",
        temporary_root=tmp_path,
        cost_guard=OfflineBudget(),
        include_identity_holds=True,
    )
    service._revision_guard = OfflineBudget()
    return service, counter, storage, vertex


def test_restored_database_has_real_foreign_keys_and_immutability_triggers(session):
    assert (
        session.scalar(
            text(
                "SELECT count(*) FROM pg_constraint WHERE contype='f' "
                "AND conrelid='lyric_documents'::regclass"
            )
        )
        > 0
    )
    assert (
        session.scalar(
            text(
                "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal "
                "AND tgrelid='lyric_classification_snapshots'::regclass"
            )
        )
        > 0
    )
    with pytest.raises(DBAPIError), session.begin_nested():
        ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="PG_GATE_TEST",
                source_version="1",
                rights_status="AUTHORIZED",
                text="Invalid missing recording",
            ),
        )


@pytest.mark.parametrize("mode", ["online", "force", "estimate", "force_estimate", "remaining"])
@pytest.mark.parametrize("defect", ["missing", "pending", "wrong_hash", "revoked", "suspended"])
def test_all_online_modes_refuse_invalid_evidence(session, monkeypatch, mode, defect):
    doc = seed(session, approved=defect != "missing")
    if defect == "suspended":
        doc.source = "LETRAS"
        approve(doc)
    elif defect == "pending":
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
    elif defect == "revoked":
        revoke(doc)
    elif defect == "wrong_hash":
        doc.text += " Changed final verse."
        doc.content_sha256 = hashlib.sha256(doc.text.encode()).hexdigest()
    session.commit()
    original = (doc.text, doc.content_sha256, dict(doc.metadata_json))
    fake = FakeClassifier()
    service = online(session, fake, monkeypatch)
    request = ClassificationRequest(
        force=mode in {"force", "force_estimate"},
        estimate_cost=mode in {"estimate", "force_estimate"},
        only_unclassified=mode == "remaining",
    )
    assert service.count_initial_pass_remaining() == 0
    assert service.run(request).selected == 0
    assert (fake.generations, fake.estimates) == (0, 0)
    assert session.scalar(select(func.count()).select_from(LyricClassificationSnapshot)) == 0
    session.refresh(doc)
    assert (doc.text, doc.content_sha256, doc.metadata_json) == original


def test_online_estimate_force_and_append_only_history(session, monkeypatch):
    seed(session, approved=True)
    fake = FakeClassifier()
    service = online(session, fake, monkeypatch)
    assert service.run(ClassificationRequest(estimate_cost=True)).estimated_candidates == 1
    assert fake.generations == 0
    service.run(ClassificationRequest())
    assert service.run(ClassificationRequest()).skipped_idempotent == 1
    service.run(ClassificationRequest(force=True))
    assert (fake.generations, fake.estimates) == (2, 1)
    snapshots = session.scalars(
        select(LyricClassificationSnapshot).order_by(LyricClassificationSnapshot.append_order)
    ).all()
    assert len(snapshots) == 2 and snapshots[1].forced_from_snapshot_id == snapshots[0].id
    assert snapshots[1].append_order > snapshots[0].append_order
    with pytest.raises(DBAPIError, match="immutable"), session.begin_nested():
        session.execute(
            text("UPDATE lyric_classification_snapshots SET error='changed' WHERE id=:id"),
            {"id": snapshots[0].id},
        )


@pytest.mark.parametrize("defect", ["missing", "revoked", "pending", "suspended"])
def test_batch_cannot_reserve_or_tokenize_unapproved_documents(
    session,
    monkeypatch,
    tmp_path,
    defect,
):
    doc = seed(session, approved=defect != "missing")
    if defect == "suspended":
        doc.source = "LETRAS"
        approve(doc)
    elif defect == "revoked":
        revoke(doc)
    elif defect == "pending":
        monkeypatch.setattr(
            review_evidence,
            "load_review_evidence",
            lambda: [
                {
                    "document_id": str(doc.id),
                    "lyrics_hash": doc.content_sha256,
                    "status": "pending_adjudication",
                    "decision": "reported_text_defect",
                }
            ],
        )
    session.commit()
    service, counter, storage, vertex = batch(session, tmp_path)
    with pytest.raises(ValueError, match="no provider-eligible"):
        service.prepare_canary(Decimal(1))
    assert (counter.estimates, storage.uploads, vertex.submissions) == (0, 0, 0)


def test_batch_approved_document_prepares_and_submits_only_to_fake_adapters(session, tmp_path):
    seed(session, approved=True)
    service, counter, storage, vertex = batch(session, tmp_path)
    prepared = service.prepare_canary(Decimal(1))
    assert len(prepared) == 1
    assert (counter.estimates, storage.uploads, vertex.submissions) == (1, 1, 0)
    service.submit(prepared[0].run_id, Decimal(1))
    assert (storage.verifications, vertex.submissions) == (1, 1)
    assert BatchRepository(session).get_run(prepared[0].run_id).state == "submitted"


@pytest.mark.parametrize("defect", ["revoked", "changed_text", "changed_language", "pending"])
def test_uploaded_batch_revalidates_committed_evidence_before_submission(
    session,
    monkeypatch,
    tmp_path,
    defect,
):
    doc = seed(session, approved=True)
    service, _counter, storage, vertex = batch(session, tmp_path)
    prepared = service.prepare_canary(Decimal(1))[0]
    if defect == "revoked":
        revoke(doc)
    elif defect == "changed_text":
        doc.text += " corrupt suffix"
    elif defect == "changed_language":
        doc.language_code = "ja"
    else:
        monkeypatch.setattr(
            review_evidence,
            "load_review_evidence",
            lambda: [
                {
                    "document_id": str(doc.id),
                    "lyrics_hash": doc.content_sha256,
                    "status": "pending_adjudication",
                    "decision": "reported_text_defect",
                }
            ],
        )
    session.commit()
    with pytest.raises(ClassificationEligibilityError):
        service.submit(prepared.run_id, Decimal(1))
    assert (storage.verifications, vertex.submissions) == (0, 0)
    assert BatchRepository(session).get_run(prepared.run_id).state == "uploaded"


def test_revocation_from_another_connection_is_seen_before_generation(engine, monkeypatch):
    with Session(engine, expire_on_commit=False) as first:
        doc = seed(first, approved=True)
        fake = FakeClassifier()
        service = online(first, fake, monkeypatch)
        candidates = service._select_candidates(ClassificationRequest())
        with Session(engine) as reviewer:
            current = reviewer.get(LyricDocument, doc.id)
            revoke(current)
            reviewer.commit()
        with pytest.raises(ClassificationEligibilityError, match="integrity_unverified"):
            service._classify(
                candidates,
                ClassificationRequest(),
                classification_service.ClassificationRunSummary(),
            )
        assert fake.generations == 0
        # This isolated test leaves only a synthetic, revoked document in its test DB.


def test_copied_research_database_remains_read_only_and_its_sample_is_not_modified(engine):
    source_db = os.environ["CHART_OBSERVATORY_GATE_SOURCE_DATABASE"]
    source_url = engine.url.set(database=source_db, query={})
    source_engine = create_engine(source_url)
    try:
        with Session(source_engine) as reader:
            assert reader.scalar(text("SHOW transaction_read_only")) == "on"
            docs = reader.scalars(select(LyricDocument).order_by(LyricDocument.id).limit(10)).all()
            assert docs
            before = [(d.id, d.content_sha256, d.text, d.metadata_json) for d in docs]
            for doc in docs:
                ClassificationGate.load().assess(doc)
            reader.expire_all()
            assert [(d.id, d.content_sha256, d.text, d.metadata_json) for d in docs] == before
            with pytest.raises(DBAPIError):
                reader.execute(text("UPDATE lyric_documents SET source=source WHERE false"))
    finally:
        source_engine.dispose()


def test_force_and_estimate_cannot_reuse_a_revoked_approval_with_existing_history(
    session,
    monkeypatch,
):
    doc = seed(session, approved=True)
    fake = FakeClassifier()
    service = online(session, fake, monkeypatch)
    service.run(ClassificationRequest())
    original = session.scalars(select(LyricClassificationSnapshot)).one()
    revoke(doc)
    session.commit()
    assert service.run(ClassificationRequest(force=True)).selected == 0
    assert service.run(ClassificationRequest(force=True, estimate_cost=True)).selected == 0
    assert (fake.generations, fake.estimates) == (1, 0)
    assert session.scalars(select(LyricClassificationSnapshot)).one().id == original.id


def test_retry_reservation_rechecks_current_adjudication(session, tmp_path):
    doc = seed(session, approved=True)
    service, _counter, _storage, vertex = batch(session, tmp_path)
    prepared = service.prepare_canary(Decimal(1))[0]
    repository = BatchRepository(session)
    run = repository.get_run(prepared.run_id)
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
            error="offline_provider_error",
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
    revoke(doc)
    session.commit()
    assert repository.error_retry_candidates(run.id, include_identity_holds=True) == []
    assert vertex.submissions == 0
    assert session.get(LyricClassificationSnapshot, snapshot.id).error == "offline_provider_error"
