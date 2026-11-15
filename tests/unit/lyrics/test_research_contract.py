import csv
import hashlib
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from chart_observatory.lyrics.research_contract import (
    CONTRACT_VERSION,
    build_profile,
    complete_reserved_result,
    contract,
    prepare_blind_packets,
    prepare_request,
    rubric_draft,
    segments,
    table_row,
    validate_result,
    validate_rubric,
    verify_request,
    write_contract_bundle,
)
from chart_observatory.lyrics.review_protocol import TOPICS
from chart_observatory.lyrics.revision_protocol import (
    ClassificationKey,
    RevisionRegistry,
    canonical_json,
    normalize_text,
)


def profile(**changes):
    return build_profile(
        **{
            "model_id": "test-model",
            "resolved_model_version": "test-model-fixed-001",
            "generation_configuration": {"temperature": 0, "max_output_tokens": 8192},
            **changes,
        }
    )


def request(**changes):
    return prepare_request(
        **{
            "edition_id": "edition-1",
            "text": "Uma linha.\r\nRefrão.\r\nRefrão.\r\n",
            "language": "pt",
            "profile": profile(),
            **changes,
        }
    )


def result(prepared, *, status="classified"):
    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": prepared["request_id"],
        "status": status,
        "topics": {
            topic: {
                "score": 2,
                "evidence_segments": ["L000001"],
                "justification": "Referência sintética no primeiro segmento.",
            }
            for topic in TOPICS
        }
        if status == "classified"
        else {},
        "auxiliary": {},
    }


def test_rubric_defines_all_topics_levels_and_synthetic_counterexamples():
    draft = validate_rubric(rubric_draft())
    assert len(draft["topics"]) == 26
    assert not contract()["scientific_acceptance"]
    for topic in draft["topics"].values():
        assert set(topic["levels"]) == {"0", "1", "2", "3"}
        assert all(level["example_kind"] == "synthetic" for level in topic["levels"].values())
        assert topic["counterexample"]["expected_score"] == 0


def test_rubric_missing_topic_or_empty_level_is_rejected():
    draft = rubric_draft()
    draft["topics"].pop(next(iter(TOPICS)))
    with pytest.raises(ValueError, match="26"):
        validate_rubric(draft)
    draft = rubric_draft()
    draft["topics"][next(iter(TOPICS))]["levels"]["2"]["example"] = " "
    with pytest.raises(ValueError, match="example"):
        validate_rubric(draft)


def accepted_rubric():
    rubric = rubric_draft()
    rubric["status"] = "accepted"
    rubric["acceptance"] = {
        "actor": "scientific-reviewer-fixture",
        "at": datetime.now(UTC).isoformat(),
        "rubric_sha256": hashlib.sha256(canonical_json(rubric).encode()).hexdigest(),
    }
    return rubric


def test_draft_cannot_pass_scientific_acceptance():
    with pytest.raises(ValueError, match="acceptance"):
        validate_rubric(rubric_draft(), require_accepted=True)


def test_explicit_scientific_acceptance_is_bound_to_exact_content_and_request():
    rubric = accepted_rubric()
    validate_rubric(rubric, require_accepted=True)
    prepared = request(rubric=rubric, profile=profile(rubric=rubric))
    assert prepared["rubric_sha256"] == hashlib.sha256(canonical_json(rubric).encode()).hexdigest()
    rubric["topics"][next(iter(TOPICS))]["definition"] = "Changed after acceptance"
    with pytest.raises(ValueError, match="actual rubric"):
        validate_rubric(rubric, require_accepted=True)


def test_scientific_acceptance_rejects_naive_or_future_timestamp():
    for timestamp in ("2026-01-01T00:00:00", "2999-01-01T00:00:00+00:00"):
        rubric = accepted_rubric()
        rubric["acceptance"]["at"] = timestamp
        with pytest.raises(ValueError, match="aware time"):
            validate_rubric(rubric, require_accepted=True)


@pytest.mark.parametrize("text", ["", "\n", "a\r\na\r\n", "A😀\rB\n\n", "x\u2028x"])
def test_segmentation_is_lossless_with_unicode_newlines_and_repetition(text):
    parts = segments(text)
    assert "".join(part["text"] for part in parts) == text
    for part in parts:
        assert text[part["start"] : part["end"]] == part["text"]


@pytest.mark.parametrize(
    "change",
    [
        {"language": "en"},
        {"edition_id": "edition-clean"},
        {"text": "Versão diferente."},
        {"profile": profile(resolved_model_version="test-model-fixed-002")},
        {"profile": profile(generation_configuration={"temperature": 0.1})},
    ],
)
def test_full_request_and_reuse_signature_change_with_context(change):
    left, right = request(), request(**change)
    assert left["request_id"] != right["request_id"]
    assert left["reuse_key"] != right["reuse_key"]


@pytest.mark.parametrize("field", ["prompt_sha256", "output_schema_sha256", "protocol_version"])
def test_arbitrary_profile_cannot_claim_actual_contract(field):
    wrong = profile()
    wrong["configuration"][field] = "tampered"
    with pytest.raises(ValueError, match="actual"):
        request(profile=wrong)


def test_changed_rubric_changes_profile_and_requires_matching_actual_content():
    rubric = rubric_draft()
    topic = next(iter(TOPICS))
    rubric["topics"][topic]["levels"]["2"]["criterion"] = "Critério revisado."
    updated = request(rubric=rubric, profile=profile(rubric=rubric))
    assert updated["reuse_key"] != request()["reuse_key"]
    with pytest.raises(ValueError, match="actual"):
        request(rubric=rubric)


def test_changed_frozen_segment_and_recomputed_id_still_require_full_reconstruction():
    prepared = request()
    prepared["segments"][0]["end"] = 999
    with pytest.raises(ValueError, match="changed"):
        verify_request(prepared)


def test_preparatory_table_has_null_scores_and_presence():
    row = table_row(request())
    assert all(row[topic] is None and row[f"{topic}.present"] is None for topic in TOPICS)
    assert row["status"] == "prepared_not_submitted"
    assert "text" not in row


@pytest.mark.parametrize("bad_score", [True, 2.0, "2", -1, 4])
def test_score_schema_rejects_coercion_and_out_of_range_values(bad_score):
    prepared = request()
    raw = result(prepared)
    raw["topics"][next(iter(TOPICS))]["score"] = bad_score
    with pytest.raises(ValueError):
        validate_result(raw, prepared)


def test_positive_score_requires_existing_nonempty_segment_evidence():
    prepared = request()
    raw = result(prepared)
    first = raw["topics"][next(iter(TOPICS))]
    for invalid in ([], ["L999999"], ["L000001", "L000001"]):
        first["evidence_segments"] = invalid
        with pytest.raises(ValueError):
            validate_result(raw, prepared)


def test_results_are_joined_by_request_id_not_order_and_missing_scores_are_not_zeros():
    first, second = request(), request(edition_id="edition-2")
    with pytest.raises(ValueError, match="different"):
        validate_result(result(first), second)
    raw = result(first, status="language_unsupported")
    assert table_row(first, raw)[next(iter(TOPICS))] is None
    raw["topics"] = result(first)["topics"]
    with pytest.raises(ValueError, match="unscorable"):
        validate_result(raw, first)


def test_exported_schema_enforces_nominal_topics_and_unscorable_outcomes():
    jsonschema = pytest.importorskip("jsonschema")
    prepared = request()
    validator = jsonschema.Draft202012Validator(prepared["contract"]["response_schema"])
    valid = result(prepared)
    validator.validate(valid)
    for status in ("ambiguous", "blocked", "language_unsupported", "error"):
        validator.validate(result(prepared, status=status))

    incomplete = deepcopy(valid)
    incomplete["topics"].pop(next(iter(TOPICS)))
    unknown = deepcopy(valid)
    unknown["topics"]["invented_topic"] = next(iter(unknown["topics"].values()))
    invalid_auxiliary = deepcopy(valid)
    invalid_auxiliary["auxiliary"]["invented_marker"] = True
    abstention_with_scores = deepcopy(valid)
    abstention_with_scores["status"] = "language_unsupported"
    for invalid in (incomplete, unknown, invalid_auxiliary, abstention_with_scores):
        assert list(validator.iter_errors(invalid))
        with pytest.raises(ValueError):
            validate_result(invalid, prepared)


def test_registry_accepts_only_validated_exact_key_and_preserves_original_contract(tmp_path):
    prepared = request()
    key = ClassificationKey(**prepared["reuse_descriptor"])
    norm = normalize_text("".join(part["text"] for part in prepared["segments"]))
    registry = RevisionRegistry(tmp_path / "registry.sqlite")
    registry.register_edition(
        "edition-1",
        norm.normalized_hash,
        norm.version,
        identity_confirmed=True,
        integrity_validated=True,
        evidence={"test": "fixture"},
    )
    owner = registry.reserve(key)
    raw = result(prepared)
    complete_reserved_result(registry, key, owner, raw, prepared, method="human_adjudication")
    assert registry.result(key)["result"]["research_result"] == raw
    assert registry.reserve(key) is None


def test_error_outcome_is_persistable_without_scores_or_presence(tmp_path):
    prepared = request()
    key = ClassificationKey(**prepared["reuse_descriptor"])
    norm = normalize_text("".join(part["text"] for part in prepared["segments"]))
    registry = RevisionRegistry(tmp_path / "registry.sqlite")
    registry.register_edition(
        "edition-1",
        norm.normalized_hash,
        norm.version,
        identity_confirmed=True,
        integrity_validated=True,
        evidence={"test": "fixture"},
    )
    owner = registry.reserve(key)
    raw = result(prepared, status="error")

    accepted = complete_reserved_result(registry, key, owner, raw, prepared, method="provider")
    row = table_row(prepared, raw)

    assert accepted.status == "error"
    assert row["status"] == "error"
    assert all(row[topic] is None and row[f"{topic}.present"] is None for topic in TOPICS)
    assert registry.result(key)["result"]["research_result"] == raw


def test_blind_packets_keep_equivalent_texts_together_and_report_deficits():
    rows = []
    for index in range(3):
        text = f"Texto {index if index < 2 else 0}."
        norm = normalize_text(text)
        rows.append(
            {
                "text_identity_id": f"edition-{index}",
                "text": text,
                "identity_confirmed": True,
                "integrity_validated": True,
                "equivalence_group": f"group-{index}",
                "instrumental": False,
                "ai_exposed": False,
                "historical_review": False,
                "text_language_role": "original",
                "language": "pt",
                "normalized_hash": norm.normalized_hash,
                "original_hash": norm.original_hash,
                "country": "BR",
                "source": "private-source",
                "position": 1,
            }
        )
    packets = prepare_blind_packets(
        rows,
        reviewers=("reviewer-a", "reviewer-b"),
        secret="x" * 32,
        pilot_size=1,
        validation_size=2,
    )
    assert packets["validation_deficit"] == 1
    split_manifest = packets["split_manifest"]
    assert split_manifest["schema_version"] == "research-blind-split-v1"
    assert split_manifest["counts"] == {"development": 1, "validation": 1}
    assert len(split_manifest["assignments_sha256"]) == 64
    assert all("text" not in assignment for assignment in split_manifest["assignments"])
    for reviewer in packets["packets"].values():
        for subset in reviewer.values():
            for form in subset["forms"]:
                assert not {"country", "source", "position"} & form.keys()
                assert all(score is None for score in form["scores"].values())


def test_contract_bundle_is_immutable_and_never_claims_acceptance(tmp_path):
    output = tmp_path / "bundle"
    manifest = write_contract_bundle(output)
    assert manifest["paid_calls"] == manifest["uploads"] == 0
    assert not manifest["scientific_acceptance"]
    with (output / "topic-dictionary.csv").open(encoding="utf-8", newline="") as handle:
        dictionary = list(csv.DictReader(handle))
    assert len(dictionary) == 26
    assert {row["id"] for row in dictionary} == set(TOPICS)
    with (output / "preparatory-table-template.csv").open(encoding="utf-8", newline="") as handle:
        template = csv.DictReader(handle)
        assert template.fieldnames == list(table_row(request()))
        assert list(template) == []
    for name, digest in manifest["artifacts"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    assert (output / "prompt-draft.txt").read_text(encoding="utf-8") == (
        contract()["prompt"] + canonical_json(contract()["rubric"])
    )
    with pytest.raises(FileExistsError):
        write_contract_bundle(output)
