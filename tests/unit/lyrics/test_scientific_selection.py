from types import SimpleNamespace
from uuid import uuid4

import pytest

from chart_observatory.lyrics.scientific_selection import assess_classification


def test_scientific_selection_never_promotes_unverified_identity() -> None:
    document = SimpleNamespace(
        id=uuid4(),
        canonical_track_id=uuid4(),
        content_sha256="a" * 64,
        source="GENIUS",
        rights_status="AUTHORIZED",
    )
    snapshot = SimpleNamespace(
        canonical_track_id=document.canonical_track_id,
        lyrics_hash=document.content_sha256,
        classification_status="classified",
        result_json={},
    )
    decision = assess_classification(document, snapshot, entries=(), suspended_sources=frozenset())
    assert not decision.primary_eligible
    assert "identity_unverified" in decision.reasons


def valid_result() -> dict[str, object]:
    return {
        "classification_status": "classified",
        "confidence": 0.8,
        "sexuality": dict.fromkeys(
            (
                "sexual_explicitness",
                "sexual_desire",
                "sexual_innuendo",
                "explicit_sexual_act",
                "explicit_sexual_anatomy",
            ),
            0,
        ),
        "relationships": {
            **dict.fromkeys(
                (
                    "romantic_affection",
                    "heartbreak",
                    "infidelity",
                    "transactional_sex",
                    "casual_sex",
                    "jealousy_possession",
                    "reciprocity",
                ),
                0,
            ),
            "consent": "not_applicable",
        },
        "gender_representation": {
            **dict.fromkeys(
                (
                    "objectification",
                    "misogyny",
                    "sexual_agency",
                    "status_symbolization",
                    "commodification",
                ),
                0,
            ),
            "target_gender": "unspecified",
        },
        "material_status": dict.fromkeys(
            ("money_reference", "materialism", "conspicuous_consumption", "wealth_as_status"), 0
        ),
        "antisocial": {
            key: {"intensity": 0, "stance": "neutral"}
            for key in ("drugs_alcohol", "crime", "violence", "weapons")
        },
        "territorial_identity": 0,
    }


def test_provider_error_is_not_reported_as_a_malformed_classification() -> None:
    document = SimpleNamespace(
        id=uuid4(),
        canonical_track_id=uuid4(),
        content_sha256="a" * 64,
        source="GENIUS",
        rights_status="AUTHORIZED",
    )
    snapshot = SimpleNamespace(
        canonical_track_id=document.canonical_track_id,
        lyrics_hash=document.content_sha256,
        classification_status="error",
        result_json=None,
    )
    decision = assess_classification(document, snapshot, entries=(), suspended_sources=frozenset())
    assert "not_classified" in decision.reasons
    assert "invalid_result" not in decision.reasons


@pytest.mark.parametrize(
    "condition", ["confirmed", "unverified", "stale_review", "suspended", "excluded"]
)
def test_scientific_selection_binds_review_to_exact_evidence(condition: str) -> None:
    document = SimpleNamespace(
        id=uuid4(),
        canonical_track_id=uuid4(),
        content_sha256="a" * 64,
        source="GENIUS",
        rights_status="AUTHORIZED",
    )
    snapshot = SimpleNamespace(
        canonical_track_id=document.canonical_track_id,
        lyrics_hash=document.content_sha256,
        classification_status="classified",
        result_json=valid_result(),
    )
    review = SimpleNamespace(
        lyric_document_id=document.id,
        canonical_track_id=document.canonical_track_id,
        lyrics_hash="b" * 64 if condition == "stale_review" else document.content_sha256,
        source="GENIUS",
        decision="confirmed_mismatch" if condition == "excluded" else "confirmed_match",
    )
    decision = assess_classification(
        document,
        snapshot,
        entries=() if condition == "unverified" else (review,),
        suspended_sources=frozenset({"GENIUS"}) if condition == "suspended" else frozenset(),
    )
    assert decision.primary_eligible == (condition == "confirmed")
    assert decision.exploratory_eligible == (condition in {"confirmed", "unverified"})
