"""G4 metrics computed from independent, identity-bound observations.

No aggregate metric supplied by a caller is trusted. Abstentions are reported and
penalize both class recalls; incomplete ordinal pairs cannot homologate a model.
The agreement coefficient uses the fixed 0--3 scale with squared distance (the
interval form of Krippendorff's alpha), rather than nominal agreement.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable, Mapping

from chart_observatory.lyrics.review_protocol import PRESENCE_THRESHOLD, TOPICS
from chart_observatory.lyrics.revision_protocol import canonical_json, normalize_text

VALIDATION_VERSION = "research-validation-g4-v3"
SPLIT_MANIFEST_VERSION = "research-blind-split-v1"
SPLIT_ALGORITHM = "split_verified-v1"
THRESHOLD = 0.8
IDENTITY_FIELDS = ("edition_id", "equivalence_group", "recording_id", "work_id", "text_sha256")


def _score(scores, topic):
    value = scores.get(topic) if isinstance(scores, Mapping) else None
    return value if type(value) is int and 0 <= value <= 3 else None


def _kappa(pairs):
    if not pairs:
        return None
    n = len(pairs)
    left = Counter(a for a, _ in pairs)
    right = Counter(b for _, b in pairs)
    observed = sum((a - b) ** 2 for a, b in pairs) / n
    expected = sum(left[a] * right[b] * (a - b) ** 2 for a in range(4) for b in range(4)) / n**2
    return 1 - observed / expected if expected else None


def _alpha(pairs):
    if not pairs:
        return None
    # Two independent raters for every item; ordered coincidence pairs.
    pooled = Counter(value for pair in pairs for value in pair)
    observations = 2 * len(pairs)
    observed = sum((a - b) ** 2 for a, b in pairs) / len(pairs)
    expected = sum(pooled[a] * pooled[b] * (a - b) ** 2 for a in range(4) for b in range(4)) / (
        observations * (observations - 1)
    )
    return 1 - observed / expected if expected else None


def _topic_metrics(rows, topic, minimum_support):
    scored, human = [], []
    confusion = {
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "tn": 0,
        "abstained_positive": 0,
        "abstained_negative": 0,
    }
    positives = negatives = invalid_reference = invalid_human = missing_prediction = 0
    for row in rows:
        ref = _score(row.get("reference"), topic)
        pred = _score(row.get("prediction"), topic)
        a, b = _score(row.get("human_a"), topic), _score(row.get("human_b"), topic)
        if a is None or b is None:
            invalid_human += 1
        else:
            human.append((a, b))
        if ref is None:
            invalid_reference += 1
            continue
        present = ref >= PRESENCE_THRESHOLD
        positives += present
        negatives += not present
        if pred is None:
            missing_prediction += 1
            confusion["abstained_positive" if present else "abstained_negative"] += 1
            continue
        scored.append((ref, pred))
        predicted = pred >= PRESENCE_THRESHOLD
        key = ("tp" if predicted else "fn") if present else ("fp" if predicted else "tn")
        confusion[key] += 1

    # Abstentions incur a false negative for the actual class, never a true negative.
    positive_denominator = (
        2 * confusion["tp"] + confusion["fp"] + confusion["fn"] + confusion["abstained_positive"]
    )
    negative_denominator = (
        2 * confusion["tn"] + confusion["fp"] + confusion["fn"] + confusion["abstained_negative"]
    )
    positive_f1 = 2 * confusion["tp"] / positive_denominator if positive_denominator else None
    negative_f1 = 2 * confusion["tn"] / negative_denominator if negative_denominator else None
    macro_f1 = (
        (positive_f1 + negative_f1) / 2
        if positive_f1 is not None and negative_f1 is not None
        else None
    )
    kappa, alpha = _kappa(scored), _alpha(human)
    reasons = []
    if positives < minimum_support or negatives < minimum_support:
        reasons.append("insufficient_class_support")
    if invalid_reference:
        reasons.append("reference_missing_or_invalid")
    if invalid_human:
        reasons.append("human_scores_missing_or_invalid")
    if missing_prediction:
        reasons.append("prediction_missing_or_invalid")
    for name, value in (("macro_f1", macro_f1), ("weighted_kappa", kappa), ("human_alpha", alpha)):
        if value is None or value < THRESHOLD:
            reasons.append(f"{name}_below_threshold_or_undefined")
    return {
        "approved": not reasons,
        "reasons": reasons,
        "items": len(rows),
        "reference_positive": positives,
        "reference_negative": negatives,
        "invalid_reference": invalid_reference,
        "invalid_human": invalid_human,
        "missing_prediction": missing_prediction,
        "prediction_coverage": len(scored) / len(rows) if rows else None,
        "macro_f1": macro_f1,
        "positive_f1": positive_f1,
        "negative_f1": negative_f1,
        "quadratic_weighted_kappa": kappa,
        "human_alpha_squared_distance": alpha,
        "ordinal_metric_pairs": len(scored),
        "human_metric_pairs": len(human),
        "confusion_at_2": confusion,
    }


def _stratum(rows, minimum_support):
    topics = {topic: _topic_metrics(rows, topic, minimum_support) for topic in TOPICS}
    return {
        "approved": bool(rows) and all(value["approved"] for value in topics.values()),
        "items": len(rows),
        "topics": topics,
    }


def _identity_tags(row):
    return {(field, row[field]) for field in IDENTITY_FIELDS if row.get(field)}


def build_split_manifest(
    development: Iterable[dict],
    validation: Iterable[dict],
    *,
    development_target: int,
    validation_target: int,
    seed: str,
) -> dict:
    """Create a private, hashable record of the exact blind split assignments."""
    if (
        type(development_target) is not int
        or development_target < 1
        or type(validation_target) is not int
        or validation_target < 1
        or not isinstance(seed, str)
        or not seed.strip()
    ):
        raise ValueError("positive split targets and an explicit seed are required")

    assignments = []
    for split_name, split_rows in (
        ("development", development),
        ("validation", validation),
    ):
        for row in split_rows:
            edition_id = row.get("text_identity_id")
            text = row.get("text")
            group = row.get("equivalence_group")
            language = row.get("language")
            if not all(
                isinstance(value, str) and value.strip()
                for value in (edition_id, text, group, language)
            ):
                raise ValueError("split assignment needs edition, text, group and language")
            assignments.append(
                {
                    "edition_id": edition_id,
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "normalized_text_sha256": normalize_text(text).normalized_hash,
                    "equivalence_group": group,
                    "recording_id": (
                        str(row["recording_id"]).strip()
                        if row.get("recording_id") is not None
                        else None
                    ),
                    "work_id": (
                        str(row["work_id"]).strip() if row.get("work_id") is not None else None
                    ),
                    "language": language,
                    "split": split_name,
                }
            )
    assignments.sort(key=lambda item: (item["split"], item["edition_id"]))
    counts = {
        "development": sum(item["split"] == "development" for item in assignments),
        "validation": sum(item["split"] == "validation" for item in assignments),
    }
    manifest = {
        "schema_version": SPLIT_MANIFEST_VERSION,
        "contract_version": "research-26-topics-v1",
        "algorithm": SPLIT_ALGORITHM,
        "seed": seed,
        "requested": {
            "development": development_target,
            "validation": validation_target,
        },
        "counts": counts,
        "deficits": {
            "development": max(0, development_target - counts["development"]),
            "validation": max(0, validation_target - counts["validation"]),
        },
        "assignments": assignments,
        "assignments_sha256": hashlib.sha256(canonical_json(assignments).encode()).hexdigest(),
    }
    return manifest


def validate_split_manifest(
    manifest: dict,
    validation_rows: Iterable[dict],
    requests: Iterable[dict],
    *,
    expected_contract_version: str,
) -> dict:
    """Verify the frozen split, its cross-split identity boundary and full coverage."""
    expected_keys = {
        "schema_version",
        "contract_version",
        "algorithm",
        "seed",
        "requested",
        "counts",
        "deficits",
        "assignments",
        "assignments_sha256",
    }
    if not isinstance(manifest, Mapping) or set(manifest) != expected_keys:
        raise ValueError("frozen split manifest has an unknown or incomplete schema")
    if (
        manifest.get("schema_version") != SPLIT_MANIFEST_VERSION
        or manifest.get("contract_version") != expected_contract_version
        or manifest.get("algorithm") != SPLIT_ALGORITHM
        or not isinstance(manifest.get("seed"), str)
        or not manifest["seed"].strip()
    ):
        raise ValueError("frozen split version or algorithm mismatch")
    requested = manifest.get("requested")
    counts = manifest.get("counts")
    deficits = manifest.get("deficits")
    if any(
        not isinstance(value, Mapping) or set(value) != {"development", "validation"}
        for value in (requested, counts, deficits)
    ):
        raise ValueError("frozen split counts are incomplete")
    if any(type(requested[name]) is not int or requested[name] < 1 for name in requested):
        raise ValueError("frozen split targets must be positive integers")
    if any(type(counts[name]) is not int or counts[name] < 0 for name in counts):
        raise ValueError("frozen split counts must be nonnegative integers")
    if any(type(deficits[name]) is not int or deficits[name] < 0 for name in deficits):
        raise ValueError("frozen split deficits must be nonnegative integers")
    assignments = manifest.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        raise ValueError("frozen split assignments are required")
    expected_assignment_keys = {
        "edition_id",
        "text_sha256",
        "normalized_text_sha256",
        "equivalence_group",
        "recording_id",
        "work_id",
        "language",
        "split",
    }
    digest = hashlib.sha256(canonical_json(assignments).encode()).hexdigest()
    if manifest.get("assignments_sha256") != digest:
        raise ValueError("frozen split assignments hash mismatch")
    actual_counts = Counter()
    assignment_by_edition = {}
    tags: dict[tuple[str, str], str] = {}
    for assignment in assignments:
        if not isinstance(assignment, Mapping) or set(assignment) != expected_assignment_keys:
            raise ValueError("frozen split assignment schema is invalid")
        if assignment.get("split") not in {"development", "validation"}:
            raise ValueError("frozen split assignment has an unknown partition")
        actual_counts[assignment["split"]] += 1
        if any(
            not isinstance(assignment.get(key), str) or not assignment[key].strip()
            for key in (
                "edition_id",
                "text_sha256",
                "normalized_text_sha256",
                "equivalence_group",
                "language",
            )
        ):
            raise ValueError("frozen split assignment is missing an identity")
        for key in ("text_sha256", "normalized_text_sha256"):
            if len(assignment[key]) != 64 or any(
                c not in "0123456789abcdef" for c in assignment[key]
            ):
                raise ValueError("frozen split assignment has an invalid text digest")
        if assignment.get("recording_id") is not None and (
            not isinstance(assignment["recording_id"], str)
            or not assignment["recording_id"].strip()
        ):
            raise ValueError("frozen split recording identity is invalid")
        if assignment.get("work_id") is not None and (
            not isinstance(assignment["work_id"], str) or not assignment["work_id"].strip()
        ):
            raise ValueError("frozen split work identity is invalid")
        edition = assignment["edition_id"]
        if edition in assignment_by_edition:
            raise ValueError("duplicate edition in frozen split")
        assignment_by_edition[edition] = assignment
        for key in ("equivalence_group", "normalized_text_sha256", "recording_id", "work_id"):
            value = assignment.get(key)
            if value is None:
                continue
            tag = (key, str(value))
            previous = tags.get(tag)
            if previous is not None:
                message = (
                    "development/validation identity overlap"
                    if previous != assignment["split"]
                    else "duplicate identity in frozen split assignments"
                )
                raise ValueError(message)
            tags[tag] = assignment["split"]
    if dict(actual_counts) != dict(counts):
        raise ValueError("frozen split counts do not match assignments")
    for partition in ("development", "validation"):
        if counts[partition] < 1 or counts[partition] + deficits[partition] != requested[partition]:
            raise ValueError("frozen split target/deficit does not match assignments")

    requests_by_edition = {}
    for request in requests:
        edition = request.get("edition_id")
        prior = requests_by_edition.get(edition)
        if prior is not None and prior["request_id"] != request.get("request_id"):
            raise ValueError("multiple prepared requests bind one split edition")
        requests_by_edition[edition] = request
    for edition, assignment in assignment_by_edition.items():
        request = requests_by_edition.get(edition)
        if request is None:
            raise ValueError("split assignment is outside the current prepared request set")
        text = "".join(segment["text"] for segment in request["segments"])
        if (
            hashlib.sha256(text.encode()).hexdigest() != assignment["text_sha256"]
            or normalize_text(text).normalized_hash != assignment["normalized_text_sha256"]
            or request.get("language") != assignment["language"]
        ):
            raise ValueError("split assignment differs from the prepared edition")

    rows = list(validation_rows)
    rows_by_edition = {}
    for row in rows:
        if row.get("split") != "validation":
            raise ValueError("only frozen validation assignments may be evaluated")
        edition = row.get("edition_id")
        if edition in rows_by_edition:
            raise ValueError("duplicate edition in frozen validation observations")
        rows_by_edition[edition] = row
    validation_assignments = {
        edition: assignment
        for edition, assignment in assignment_by_edition.items()
        if assignment["split"] == "validation"
    }
    if set(rows_by_edition) != set(validation_assignments):
        raise ValueError("validation observations do not cover the exact frozen validation split")
    for edition, row in rows_by_edition.items():
        assignment = validation_assignments[edition]
        if (
            row.get("text_sha256") != assignment["text_sha256"]
            or row.get("equivalence_group") != assignment["equivalence_group"]
            or row.get("language") != assignment["language"]
        ):
            raise ValueError("validation observation differs from its frozen split assignment")
    return {
        "schema_version": SPLIT_MANIFEST_VERSION,
        "development_items": counts["development"],
        "validation_items": counts["validation"],
        "assignments_sha256": digest,
        "disjoint_identity_tags": len(tags),
    }


def evaluate_validation(
    rows: Iterable[dict],
    minimum_support: int = 30,
    *,
    development_groups: Iterable[str] = (),
) -> dict:
    """Evaluate held-out items with stable IDs; input is never joined by position.

    Required per item: request_id, edition_id, equivalence_group, language, split,
    reviewer_a, reviewer_b, reference/human_a/human_b score mappings and prediction
    (mapping or None). Optional recording_id, work_id and text_sha256 strengthen
    leakage checks. Rows labelled development contribute only identity exclusions.
    The reference must be independently adjudicated; this function validates
    declared reviewer independence but cannot authenticate a human identity.
    """
    if type(minimum_support) is not int or minimum_support < 1:
        raise ValueError("minimum_support must be a positive integer")
    rows = list(rows)
    request_ids = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("validation observations must be mappings")
        for field in ("request_id", "edition_id", "equivalence_group", "language", "split"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"explicit {field} is required")
        if row["split"] not in {"development", "validation"}:
            raise ValueError("unknown split")
        if row["request_id"] in request_ids:
            raise ValueError("duplicate request_id")
        request_ids.add(row["request_id"])
        for field in IDENTITY_FIELDS:
            if row.get(field) is not None and not isinstance(row[field], str):
                raise ValueError(f"invalid identity field: {field}")

    development = [row for row in rows if row["split"] == "development"]
    validation = [row for row in rows if row["split"] == "validation"]
    forbidden = {("equivalence_group", group) for group in development_groups}
    for row in development:
        forbidden.update(_identity_tags(row))
    reasons, leakage_ids, independence_ids, repeated_ids = [], [], [], []
    seen_editions, seen_groups = set(), set()
    for row in validation:
        if _identity_tags(row) & forbidden:
            leakage_ids.append(row["request_id"])
        if row["edition_id"] in seen_editions or row["equivalence_group"] in seen_groups:
            repeated_ids.append(row["request_id"])
        seen_editions.add(row["edition_id"])
        seen_groups.add(row["equivalence_group"])
        reviewers = (row.get("reviewer_a"), row.get("reviewer_b"))
        if any(not isinstance(value, str) or not value.strip() for value in reviewers) or (
            isinstance(reviewers[0], str)
            and isinstance(reviewers[1], str)
            and reviewers[0].strip().casefold() == reviewers[1].strip().casefold()
        ):
            independence_ids.append(row["request_id"])
    if not validation:
        reasons.append("no_independent_validation_items")
    if leakage_ids:
        reasons.append("development_validation_identity_leakage")
    if independence_ids:
        reasons.append("independent_reviewers_required")
    if repeated_ids:
        reasons.append("repeated_validation_identity")
    overall = _stratum(validation, minimum_support)
    by_language = {
        language: _stratum(
            [row for row in validation if row["language"] == language], minimum_support
        )
        for language in sorted({row["language"] for row in validation})
    }
    if not overall["approved"]:
        reasons.append("global_metrics_failed")
    if any(not value["approved"] for value in by_language.values()):
        reasons.append("language_metrics_failed")
    return {
        "version": VALIDATION_VERSION,
        "approved": not reasons,
        "reasons": reasons,
        "threshold": THRESHOLD,
        "minimum_class_support": minimum_support,
        "alpha_distance": "squared_fixed_ordinal_scores_0_to_3",
        "counts": {
            "input": len(rows),
            "development": len(development),
            "validation": len(validation),
            "languages": len(by_language),
        },
        "evidence": {
            "leaked_request_ids": leakage_ids,
            "nonindependent_review_request_ids": independence_ids,
            "repeated_identity_request_ids": repeated_ids,
            "reviewer_authentication": "declared_identity_only",
        },
        "global": overall,
        "by_language": by_language,
    }
