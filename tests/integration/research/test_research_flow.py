"""Research audit reads and revocation against an explicitly isolated PostgreSQL."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from chart_observatory import research_flow as flow
from chart_observatory.db.models.corpus import LyricDocument
from chart_observatory.db.models.tracks import CanonicalTrack
from chart_observatory.lyrics.classification_gate import ClassificationGate
from chart_observatory.lyrics.repository import LyricDocumentInput, ingest_lyric_document

pytestmark = pytest.mark.integration
MARKER = "research-flow-isolated-postgres-v1"


@pytest.fixture(scope="module")
def isolated_engine():
    value = os.environ.get("CHART_OBSERVATORY_TEST_DATABASE_URL")
    data_root = os.environ.get("CHART_OBSERVATORY_RESEARCH_TEST_CLUSTER")
    if not value or not data_root:
        pytest.skip("requires an explicitly isolated research-flow PostgreSQL cluster")
    parsed = make_url(value)
    if parsed.host != "127.0.0.1" or not (parsed.database or "").startswith("research_flow_test_"):
        pytest.skip("never writes a production or unrelated test database")
    cluster = Path(data_root).resolve()
    allowed = (Path(os.environ["LOCALAPPDATA"]) / "ChartObservatory/research-flow-tests").resolve()
    assert cluster.is_relative_to(allowed)
    engine = create_engine(value)
    with engine.connect() as conn:
        assert Path(conn.scalar(text("SHOW data_directory"))).resolve() == cluster
        assert (
            conn.scalar(
                text(
                    "SELECT shobj_description(oid,'pg_database') FROM pg_database "
                    "WHERE datname=current_database()"
                )
            )
            == MARKER
        )
    # The isolated cluster starts empty. Create only the tables under test.
    CanonicalTrack.__table__.create(engine, checkfirst=True)
    LyricDocument.__table__.create(engine, checkfirst=True)
    yield engine
    engine.dispose()


@pytest.fixture
def canonical(isolated_engine, monkeypatch):
    from chart_observatory.config import Settings

    url = isolated_engine.url.render_as_string(hide_password=False)
    monkeypatch.setattr(Settings, "load", lambda root: SimpleNamespace(database_url=url))
    gate = ClassificationGate(frozenset(), frozenset(), frozenset())
    monkeypatch.setattr(flow.ClassificationGate, "load", lambda: gate)
    with Session(isolated_engine, expire_on_commit=False) as session:
        track = CanonicalTrack(title="Synthetic isolated research integration")
        session.add(track)
        session.flush()
        document = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=track.id,
                source="RESEARCH_FLOW_TEST",
                source_version="1",
                rights_status="AUTHORIZED",
                language_code="pt",
                text="Texto sintético integral para integração local.\nRefrão.\nRefrão.\n",
            ),
        )
        document.metadata_json = {
            "research_candidate_ids": ["SPOTIFY:isolated-research-test"],
            "classification_adjudication": {
                "gate_version": "lyrics-classification-gate-v1",
                "adjudication_id": f"integration-{document.id}",
                "document_id": str(document.id),
                "recording_id": str(track.id),
                "lyrics_hash": document.content_sha256,
                "source": document.source,
                "status": "approved",
                "identity_verified": True,
                "integrity_verified": True,
                "method": "human_audio_verification",
                "evidence_url": "https://example.org/synthetic-integration",
                "evidence_sha256": "a" * 64,
                "verified_at": "2026-11-01T00:00:00Z",
                "adjudicated_at": "2026-11-02T00:00:00Z",
                "adjudicator": "Synthetic reviewer",
            },
        }
        session.commit()
        yield document


def test_current_canonical_reader_is_read_only_and_returns_exact_state(
    isolated_engine, canonical, tmp_path, monkeypatch
):
    from chart_observatory.config import Settings

    read_engine = create_engine(isolated_engine.url)
    statements = []
    read_only_states = []

    @event.listens_for(read_engine, "before_cursor_execute")
    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
        if statement.lstrip().startswith("SELECT lyric_documents"):
            with connection.connection.cursor() as check:
                check.execute("SHOW transaction_read_only")
                read_only_states.append(check.fetchone()[0])

    import sqlalchemy

    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *args, **kwargs: read_engine)
    monkeypatch.setattr(
        Settings,
        "load",
        lambda root: SimpleNamespace(
            database_url=isolated_engine.url.render_as_string(hide_password=False)
        ),
    )
    loaded = flow.read_canonical_documents(tmp_path, [canonical.id])
    document = loaded[str(canonical.id)]
    assert document.text == canonical.text
    assert document.content_sha256 == canonical.content_sha256
    assert flow.canonical_fingerprint(document) == flow.canonical_fingerprint(canonical)
    assert read_only_states == ["on"]
    assert not any(
        s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER"))
        for s in statements
    )


def test_stage_rechecks_committed_revocation_in_another_session(
    isolated_engine, canonical, tmp_path
):
    output = tmp_path / "synthetic-audit"
    output.mkdir()
    report = {
        "gates": [{"gate": "G2", "state": "aprovado"}],
        "canonical_state": {str(canonical.id): flow.canonical_fingerprint(canonical)},
    }
    flow.write_json(output / "report.json", report)
    flow.write_json(
        output / "manifest.json",
        {
            "artifacts": {"report.json": flow.file_hash(output / "report.json")},
            "input_hashes": {},
        },
    )
    assert flow.require_research_stage(output, "G2", project=tmp_path) == report
    with Session(isolated_engine) as session:
        current = session.scalar(select(LyricDocument).where(LyricDocument.id == canonical.id))
        current.metadata_json = {"research_candidate_ids": ["SPOTIFY:isolated-research-test"]}
        session.commit()
    with pytest.raises(ValueError, match="revoked or document changed"):
        flow.require_research_stage(output, "G2", project=tmp_path)


def test_current_reader_never_reuses_a_historical_approval(isolated_engine, canonical, tmp_path):
    before = flow.read_canonical_documents(tmp_path, [canonical.id])[str(canonical.id)]
    assert ClassificationGate.load().assess(before).eligible
    with Session(isolated_engine) as session:
        document = session.get(LyricDocument, canonical.id)
        document.rights_status = "UNVERIFIED"
        session.commit()
    after = flow.read_canonical_documents(tmp_path, [canonical.id])[str(canonical.id)]
    assert flow.canonical_fingerprint(before) != flow.canonical_fingerprint(after)
    assert not ClassificationGate.load().assess(after).eligible
