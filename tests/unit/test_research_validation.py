import json

import pytest

from chart_observatory.lyrics.review_protocol import TOPICS
from chart_observatory.research_validation import (
    build_split_manifest,
    evaluate_validation,
    validate_split_manifest,
)


def observations(n=80, language="pt", prefix="v"):
    return [
        dict(
            request_id=f"{prefix}-request-{i}",
            edition_id=f"{prefix}-edition-{i}",
            equivalence_group=f"{prefix}-group-{i}",
            language=language,
            split="validation",
            reviewer_a="human-1",
            reviewer_b="human-2",
            reference=dict.fromkeys(TOPICS, i % 4),
            prediction=dict.fromkeys(TOPICS, i % 4),
            human_a=dict.fromkeys(TOPICS, i % 4),
            human_b=dict.fromkeys(TOPICS, i % 4),
        )
        for i in range(n)
    ]


def test_perfect_independent_balanced_validation_passes_every_topic_and_language():
    rows = observations() + observations(language="es", prefix="es")
    result = evaluate_validation(rows)
    assert result["approved"]
    assert len(result["global"]["topics"]) == 26
    assert set(result["by_language"]) == {"pt", "es"}
    first = result["global"]["topics"][next(iter(TOPICS))]
    assert first["macro_f1"] == first["quadratic_weighted_kappa"] == 1
    assert first["human_alpha_squared_distance"] == 1
    json.dumps(result, allow_nan=False)


def test_global_success_cannot_hide_insufficient_language_support():
    result = evaluate_validation(observations(80) + observations(4, "es", "es"))
    assert result["global"]["approved"]
    assert not result["approved"]
    assert not result["by_language"]["es"]["approved"]


def test_one_failed_topic_blocks_aggregate():
    rows = observations()
    topic = next(iter(TOPICS))
    for row in rows:
        row["prediction"][topic] = 3 - row["reference"][topic]
    report = evaluate_validation(rows)
    assert not report["approved"]
    assert report["global"]["topics"][topic]["macro_f1"] == 0


def test_abstentions_are_penalized_and_never_silently_dropped():
    rows = observations()
    rows[0]["prediction"] = None
    topic = next(iter(TOPICS))
    metrics = evaluate_validation(rows)["global"]["topics"][topic]
    assert not metrics["approved"]
    assert metrics["macro_f1"] < 1
    assert metrics["missing_prediction"] == 1
    assert metrics["confusion_at_2"]["abstained_negative"] == 1
    assert metrics["ordinal_metric_pairs"] == 79
    assert metrics["prediction_coverage"] == 79 / 80


def test_missing_human_or_reference_scores_cannot_pass():
    rows = observations()
    rows[0]["reference"] = {}
    rows[1]["human_b"] = {}
    result = evaluate_validation(rows)
    assert not result["approved"]
    metrics = result["global"]["topics"][next(iter(TOPICS))]
    assert metrics["invalid_reference"] == metrics["invalid_human"] == 1


@pytest.mark.parametrize(
    "identity", ["edition_id", "equivalence_group", "recording_id", "work_id", "text_sha256"]
)
def test_leakage_is_blocked_by_every_available_identity(identity):
    rows = observations()
    development = observations(1, prefix="dev")[0]
    development["split"] = "development"
    development[identity] = "shared"
    rows[0][identity] = "shared"
    report = evaluate_validation([development, *rows])
    assert not report["approved"]
    assert report["evidence"]["leaked_request_ids"] == [rows[0]["request_id"]]


def test_explicit_development_groups_and_repeated_validation_groups_block():
    rows = observations()
    rows[1]["equivalence_group"] = rows[0]["equivalence_group"]
    result = evaluate_validation(rows, development_groups=[rows[0]["equivalence_group"]])
    assert "development_validation_identity_leakage" in result["reasons"]
    assert "repeated_validation_identity" in result["reasons"]


def test_same_human_cannot_be_both_reviewers():
    rows = observations()
    rows[0]["reviewer_b"] = rows[0]["reviewer_a"]
    result = evaluate_validation(rows)
    assert not result["approved"]
    assert "independent_reviewers_required" in result["reasons"]


def test_reviewer_spelling_case_and_whitespace_cannot_fake_independence():
    rows = observations()
    rows[0]["reviewer_a"] = "Alice"
    rows[0]["reviewer_b"] = " alice "
    result = evaluate_validation(rows)
    assert not result["approved"]
    assert "independent_reviewers_required" in result["reasons"]


def test_human_disagreement_blocks_even_when_model_matches_reference():
    rows = observations()
    for row in rows:
        row["human_b"] = {key: 3 - value for key, value in row["human_a"].items()}
    result = evaluate_validation(rows)
    assert not result["approved"]
    assert result["global"]["topics"][next(iter(TOPICS))]["macro_f1"] == 1


def test_empty_or_constant_reference_does_not_claim_perfect_agreement():
    assert not evaluate_validation([])["approved"]
    rows = observations()
    for row in rows:
        for field in ("reference", "prediction", "human_a", "human_b"):
            row[field] = dict.fromkeys(TOPICS, 0)
    metrics = evaluate_validation(rows)["global"]["topics"][next(iter(TOPICS))]
    assert metrics["quadratic_weighted_kappa"] is None
    assert metrics["human_alpha_squared_distance"] is None
    assert not metrics["approved"]


@pytest.mark.parametrize("value", [True, -1, 4, 1.0, "1", None])
def test_invalid_prediction_values_are_not_silently_coerced(value):
    rows = observations()
    rows[0]["prediction"][next(iter(TOPICS))] = value
    result = evaluate_validation(rows)
    assert not result["approved"]


def test_duplicate_request_ids_are_rejected_before_metric_computation():
    rows = observations()
    rows[1]["request_id"] = rows[0]["request_id"]
    with pytest.raises(ValueError, match="duplicate request_id"):
        evaluate_validation(rows)


def test_alignment_is_identity_bound_and_input_order_independent():
    rows = observations()
    assert evaluate_validation(rows) == evaluate_validation(list(reversed(rows)))


def test_minimum_support_cannot_disable_evidence_requirements():
    with pytest.raises(ValueError, match="positive integer"):
        evaluate_validation(observations(), minimum_support=0)


def test_ordinal_metrics_match_hand_computed_nonperfect_pairs():
    rows = observations(4)
    predictions = [0, 2, 1, 3]
    for row, prediction in zip(rows, predictions, strict=True):
        row["prediction"] = dict.fromkeys(TOPICS, prediction)
        row["human_b"] = dict.fromkeys(TOPICS, prediction)
    metrics = evaluate_validation(rows, minimum_support=1)["global"]["topics"][next(iter(TOPICS))]
    # D_o=.5; independent marginals D_e=2.5; pooled without-replacement D_e=20/7.
    assert metrics["quadratic_weighted_kappa"] == pytest.approx(0.8)
    assert metrics["human_alpha_squared_distance"] == pytest.approx(0.825)
    assert metrics["macro_f1"] == pytest.approx(0.5)


def _split_row(edition, group, text, split):
    return {
        "text_identity_id": edition,
        "equivalence_group": group,
        "text": text,
        "language": "pt",
        "recording_id": f"recording-{edition}",
        "work_id": f"work-{edition}",
        "split": split,
    }


def _frozen_split():
    development = [_split_row("dev-1", "group-dev", "Development text", "development")]
    validation = [_split_row("val-1", "group-val", "Validation text", "validation")]
    manifest = build_split_manifest(
        development,
        validation,
        development_target=80,
        validation_target=240,
        seed="test-seed-v1",
    )
    return manifest, development[0], validation[0]


def _request_for_split(assignment):
    import hashlib

    from chart_observatory.lyrics.revision_protocol import normalize_text

    text = assignment["text"]
    return {
        "edition_id": assignment["text_identity_id"],
        "request_id": assignment["text_identity_id"] + "-request",
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "language": "pt",
        "reuse_descriptor": {"normalized_hash": normalize_text(text).normalized_hash},
        "segments": [{"text": text}],
    }


def _validation_row_for_split(assignment):
    import hashlib

    return {
        "edition_id": assignment["text_identity_id"],
        "request_id": assignment["text_identity_id"] + "-request",
        "text_sha256": hashlib.sha256(assignment["text"].encode()).hexdigest(),
        "language": "pt",
        "equivalence_group": assignment["equivalence_group"],
        "split": "validation",
    }


def test_frozen_split_manifest_binds_exact_validation_items_and_group_disjointness():
    manifest, development, validation = _frozen_split()
    result = validate_split_manifest(
        manifest,
        [_validation_row_for_split(validation)],
        [_request_for_split(development), _request_for_split(validation)],
        expected_contract_version="research-26-topics-v1",
    )
    assert result["development_items"] == result["validation_items"] == 1
    assert result["assignments_sha256"] == manifest["assignments_sha256"]


def test_frozen_split_rejects_cross_partition_group_overlap_even_with_rehashed_manifest():
    import hashlib

    from chart_observatory.lyrics.revision_protocol import canonical_json

    manifest, development, validation = _frozen_split()
    manifest["assignments"][1]["equivalence_group"] = manifest["assignments"][0][
        "equivalence_group"
    ]
    manifest["assignments_sha256"] = hashlib.sha256(
        canonical_json(manifest["assignments"]).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="identity overlap"):
        validate_split_manifest(
            manifest,
            [_validation_row_for_split(validation)],
            [_request_for_split(development), _request_for_split(validation)],
            expected_contract_version="research-26-topics-v1",
        )


def test_frozen_split_rejects_partial_validation_coverage():
    manifest, development, validation = _frozen_split()
    with pytest.raises(ValueError, match="exact frozen validation split"):
        validate_split_manifest(
            manifest,
            [],
            [_request_for_split(development), _request_for_split(validation)],
            expected_contract_version="research-26-topics-v1",
        )
