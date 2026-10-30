import pytest
from pydantic import BaseModel

from chart_observatory.lyrics.classification import LyricsClassification
from chart_observatory.lyrics.review_protocol import (
    TOPICS,
    blind_forms,
    compare_scores,
    split_verified,
    validate_assessment,
)


def test_draft_retains_exactly_the_existing_26_intensity_dimensions():
    def paths(model, prefix=""):
        for name, field in model.model_fields.items():
            path = f"{prefix}.{name}" if prefix else name
            annotation = field.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                yield from paths(annotation, path)
            elif annotation is int:
                yield path

    assert set(TOPICS) == set(paths(LyricsClassification))
    assert len(TOPICS) == 26


def test_equivalent_texts_never_cross_development_and_validation():
    rows = [
        dict(
            text_identity_id=f"edition-{i}",
            equivalence_group=f"group-{i // 2}",
            identity_confirmed=True,
            integrity_validated=True,
            text=f"Text of equivalence group {i // 2}",
            language="pt",
            source="source",
            period="2025",
            risk="low",
            ai_exposed=False,
            historical_review=False,
            text_language_role="original",
        )
        for i in range(12)
    ]
    rows.append({**rows[0], "equivalence_group": "unverified", "integrity_validated": False})
    result = split_verified(rows, pilot_size=3, validation_size=4)
    assert len(result["pilot"]) == 3
    assert result["validation_deficit"] == 1
    assert not (
        {r["equivalence_group"] for r in result["pilot"]}
        & {r["equivalence_group"] for r in result["validation"]}
    )
    assert all(r["equivalence_group"] != "unverified" for r in result["validation"])


def test_blind_forms_hide_country_rank_sources_models_and_previous_labels():
    row = dict(
        text_identity_id="edition",
        equivalence_group="same",
        text="Original text",
        title="Title",
        artist="Artist",
        country="BR",
        rank=1,
        source="GENIUS",
        model_id="test",
        previous_scores={"materialism": 3},
    )
    first, mapping = blind_forms([row], "A", "private-test-seed")
    second, _ = blind_forms([row], "B", "private-test-seed")
    assert first[0]["review_id"] != second[0]["review_id"]
    assert not set(first[0]) & {"country", "rank", "source", "model_id", "previous_scores"}
    assert first[0]["text"] == "Original text"
    assert first[0]["scores"] == dict.fromkeys(TOPICS)
    assert mapping[0]["text_identity_id"] == "edition"


def test_instrumental_and_ambiguity_do_not_turn_into_26_zeros():
    for status in ("instrumental", "ambiguous", "insufficient_text"):
        validate_assessment({"classification_status": status, "scores": dict.fromkeys(TOPICS)})
        with pytest.raises(ValueError):
            validate_assessment(
                {"classification_status": status, "scores": dict.fromkeys(TOPICS, 0)}
            )


def test_ordinal_and_presence_metrics_use_only_scored_pairs():
    topic = next(iter(TOPICS))
    report = compare_scores(
        [{topic: v} for v in [0, 1, 2, 3, None]], [{topic: v} for v in [0, 2, 1, 3, 0]]
    )[topic]
    assert report["support"] == 4
    assert report["unscored_pairs"] == 1
    assert report["quadratic_weighted_kappa"] == pytest.approx(0.8)
    assert report["confusion_at_2"] == dict(tp=1, fp=1, fn=1, tn=1)
    assert report["precision"] == report["sensitivity"] == 0.5
    assert report["support_warning"] is True


def test_identical_text_under_different_entity_ids_cannot_leak_across_splits():
    rows = [
        dict(
            text_identity_id=f"edition-{i}",
            equivalence_group=f"group-{i}",
            identity_confirmed=True,
            integrity_validated=True,
            text="Identical input",
            ai_exposed=False,
            historical_review=False,
            text_language_role="original",
        )
        for i in range(4)
    ]
    result = split_verified(rows, pilot_size=2, validation_size=2)
    assert len(result["pilot"]) + len(result["validation"]) == 1
