import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.lyrics.classification_queue import (
    ClassificationSignature,
    iter_remaining_candidates,
    select_remaining_candidates,
)
from chart_observatory.lyrics.identity_quarantine import (
    EXCLUDED_DECISIONS,
    excluded_document_ids,
    load_quarantine_entries,
    load_quarantined_source_signatures,
    load_suspended_sources,
    scientifically_eligible_document_ids,
)
from chart_observatory.lyrics.repository import LyricDocumentInput, ingest_lyric_document


def test_exploratory_source_override_preserves_default_scientific_quarantine(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        doc = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="LETRAS",
                source_version="1",
                rights_status="RESEARCH_AUTHORIZED",
                text="supplied lyric text long enough",
            ),
        )
        unauthorized = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="LETRAS",
                source_version="1",
                rights_status="AUTHORIZED",
                text="unauthorized lyric text long enough",
            ),
        )
        unauthorized.rights_status = "UNKNOWN"
        session.flush()
        manifest = tmp_path / "policy.json"
        _write_manifest(
            manifest,
            [_entry(doc.id, "confirmed_mismatch")],
            suspended_sources=[
                {
                    "source": "LETRAS",
                    "status": "suspended_pending_validation",
                    "reason": "Identity remains unverified",
                    "effective_on": "2026-09-27",
                    "expected_document_count": 1,
                    "allow_active_batch_reconciliation": True,
                }
            ],
        )
        signature = ClassificationSignature("gemini-3.8-flash", "taxonomy", "prompt")
        assert not list(
            iter_remaining_candidates(session, signature, quarantine_manifest_path=manifest)
        )
        candidates = list(
            iter_remaining_candidates(
                session, signature, quarantine_manifest_path=manifest, include_identity_holds=True
            )
        )
        assert [item.lyric_document_id for item in candidates] == [doc.id]
        assert unauthorized.id not in {item.lyric_document_id for item in candidates}
        assert load_suspended_sources(manifest) == frozenset({"LETRAS"})
        assert not scientifically_eligible_document_ids([doc.id], load_quarantine_entries(manifest))


def _entry(document_id: UUID, decision: str) -> dict[str, object]:
    return {
        "lyric_document_id": str(document_id),
        "canonical_track_id": str(uuid4()),
        "title": "Track title",
        "artist": "Artist",
        "source": "LETRAS",
        "lyrics_hash": "a" * 64,
        "decision": decision,
        "reason": "Reviewed identity evidence",
        "evidence": ["exact content hash shared by unrelated track identities"],
        "reviewed_on": "2026-09-27",
        "review_method": "local_identity_audit_v1",
        "preserved_snapshot_ids": [],
        "corrected_document_id": None,
        "replacement_snapshot_id": None,
    }


def _write_manifest(
    path,
    entries: list[dict[str, object]],
    *,
    suspended_sources: list[dict[str, object]] | None = None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "suspended_sources": suspended_sources or [],
                "entries": entries,
            }
        ),
        encoding="utf-8",
    )


def test_only_material_exclusion_decisions_enter_the_quarantine(tmp_path) -> None:
    excluded = [uuid4() for _ in EXCLUDED_DECISIONS]
    retained = [uuid4(), uuid4()]
    decisions = sorted(EXCLUDED_DECISIONS)
    entries = [
        _entry(document_id, decision)
        for document_id, decision in zip(excluded, decisions, strict=True)
    ]
    entries.extend([_entry(retained[0], "needs_review"), _entry(retained[1], "related_version")])
    manifest = tmp_path / "quarantine.json"
    _write_manifest(manifest, entries)

    parsed = load_quarantine_entries(manifest)

    assert excluded_document_ids(parsed) == frozenset(excluded)
    assert scientifically_eligible_document_ids(excluded + retained, parsed) == tuple(retained)
    excluded_ids = excluded_document_ids(parsed)
    assert all(
        entry.lyric_document_id in excluded_ids
        for entry in parsed
        if entry.decision in EXCLUDED_DECISIONS
    )


def test_invalid_identity_evidence_fails_closed(tmp_path) -> None:
    manifest = tmp_path / "quarantine.json"
    invalid = _entry(uuid4(), "unknown_decision")
    _write_manifest(manifest, [invalid])

    with pytest.raises(ValueError, match="unsupported quarantine decision"):
        load_quarantine_entries(manifest)


def test_invalid_hash_fails_closed(tmp_path) -> None:
    manifest = tmp_path / "quarantine.json"
    invalid = _entry(uuid4(), "confirmed_mismatch")
    invalid["lyrics_hash"] = "not-a-sha256"
    _write_manifest(manifest, [invalid])

    with pytest.raises(ValueError, match="invalid lyrics hash"):
        load_quarantine_entries(manifest)


def test_excluded_source_signatures_are_derived_without_rejecting_review_items(tmp_path) -> None:
    excluded_id = uuid4()
    review_id = uuid4()
    manifest = tmp_path / "quarantine.json"
    _write_manifest(
        manifest,
        [_entry(excluded_id, "insufficient_text"), _entry(review_id, "needs_review")],
    )

    signatures = load_quarantined_source_signatures(manifest)

    assert signatures == frozenset({("LETRAS", "a" * 64)})


def test_source_suspension_requires_explicit_auditable_policy(tmp_path) -> None:
    manifest = tmp_path / "quarantine.json"
    _write_manifest(
        manifest,
        [],
        suspended_sources=[
            {
                "source": "letras",
                "status": "suspended_pending_validation",
                "reason": "Identity audit found an unacceptable mismatch rate.",
                "effective_on": "2026-09-27",
                "expected_document_count": 26540,
                "allow_active_batch_reconciliation": True,
            }
        ],
    )

    assert load_suspended_sources(manifest) == frozenset({"LETRAS"})


def test_malformed_source_suspension_fails_closed(tmp_path) -> None:
    manifest = tmp_path / "quarantine.json"
    _write_manifest(
        manifest,
        [],
        suspended_sources=[
            {
                "source": "LETRAS",
                "status": "enabled",
                "reason": "Invalid policy must not silently reactivate a source.",
                "effective_on": "2026-09-27",
                "expected_document_count": 26540,
                "allow_active_batch_reconciliation": True,
            }
        ],
    )

    with pytest.raises(ValueError, match="unsupported source suspension status"):
        load_suspended_sources(manifest)


def test_checked_in_quarantine_manifest_preserves_paid_snapshots() -> None:
    entries = load_quarantine_entries()

    assert len(entries) == 752
    assert sum(entry.decision == "confirmed_mismatch" for entry in entries) == 1
    assert sum(entry.decision == "suspected_mismatch" for entry in entries) == 8
    assert sum(entry.decision == "insufficient_text" for entry in entries) == 739
    assert sum(entry.decision == "contaminated_text" for entry in entries) == 4
    assert all(entry.corrected_document_id is None for entry in entries)
    preserved = {
        entry.lyric_document_id: entry.preserved_snapshot_ids
        for entry in entries
        if entry.preserved_snapshot_ids
    }
    assert preserved == {
        UUID("179e80ba-a52b-5775-9258-6425f8ecbb6d"): (
            UUID("171beb7a-ab2d-4fda-9ad9-b8cfaef824fa"),
        ),
        UUID("00221f0f-124c-50d4-9557-d49d26882977"): (
            UUID("622d1d50-cc7a-4b31-bf8a-706056ef3a47"),
        ),
    }
    assert (
        "LETRAS",
        "96675f6ca0cc5c8b3593b890f04f41314a60dd5dca6594df34d4f0b42fd32b35",
    ) in load_quarantined_source_signatures()
    assert load_suspended_sources() == frozenset({"LETRAS"})


def test_candidate_selection_skips_quarantined_documents_but_keeps_other_sources(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    quarantined_id = uuid4()
    manifest = tmp_path / "quarantine.json"
    entry = _entry(quarantined_id, "confirmed_mismatch")
    _write_manifest(manifest, [entry])
    with Session(engine) as session:
        quarantined = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="LETRAS",
                source_version="1",
                rights_status="AUTHORIZED",
                text="valid length text for candidate classification",
            ),
        )
        quarantined.id = quarantined_id
        kept = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="GENIUS",
                source_version="1",
                rights_status="AUTHORIZED",
                text="another valid length text for candidate classification",
            ),
        )
        session.flush()

        candidates = select_remaining_candidates(
            session,
            ClassificationSignature("model", "taxonomy", "prompt"),
            limit=None,
            quarantine_manifest_path=manifest,
        )

    assert [candidate.lyric_document_id for candidate in candidates] == [kept.id]


def test_candidate_selection_skips_every_document_from_a_suspended_source(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    manifest = tmp_path / "quarantine.json"
    _write_manifest(
        manifest,
        [],
        suspended_sources=[
            {
                "source": "LETRAS",
                "status": "suspended_pending_validation",
                "reason": "Pending independent lyric identity validation.",
                "effective_on": "2026-09-27",
                "expected_document_count": 26540,
                "allow_active_batch_reconciliation": True,
            }
        ],
    )
    with Session(engine) as session:
        suspended = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="LETRAS",
                source_version="1",
                rights_status="AUTHORIZED",
                text="valid suspended lyric text for candidate classification",
            ),
        )
        kept = ingest_lyric_document(
            session,
            LyricDocumentInput(
                canonical_track_id=uuid4(),
                source="GENIUS",
                source_version="1",
                rights_status="AUTHORIZED",
                text="valid retained lyric text for candidate classification",
            ),
        )
        session.flush()

        candidates = select_remaining_candidates(
            session,
            ClassificationSignature("model", "taxonomy", "prompt"),
            limit=None,
            quarantine_manifest_path=manifest,
        )

    assert suspended.id not in {candidate.lyric_document_id for candidate in candidates}
    assert [candidate.lyric_document_id for candidate in candidates] == [kept.id]
