"""Aggregate-only scientific quality reporting for the human-gated pilot."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from chart_observatory.db.models.corpus import LyricClassificationSnapshot, LyricDocument
from chart_observatory.db.models.lyrics_batch import LyricClassificationBatchItem
from chart_observatory.lyrics.identity_quarantine import (
    excluded_document_ids,
    load_quarantine_entries,
    load_suspended_sources,
)


class HumanPilotReview(BaseModel):
    model_config = ConfigDict(frozen=True)

    opaque_key: UUID
    reviewer: str = Field(min_length=1)
    values: dict[str, int | str]


class BlindedPilotItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    opaque_key: UUID
    language_stratum: str
    text_length_stratum: str


class TokenCostStratum(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_count: int
    input_tokens: int
    output_tokens: int
    thought_tokens: int
    known_cost_usd: Decimal | None


class PilotQualityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_items: int
    quarantined_items: int
    status_distribution: dict[str, int]
    confidence_distribution: dict[str, int]
    confidence_outliers: list[UUID]
    intensity_distributions: dict[str, dict[int, int]]
    validation_error_rate: Decimal
    token_cost_by_stratum: dict[str, TokenCostStratum]
    agreement_metrics: dict[str, float | None]
    blinded_items: list[BlindedPilotItem]


def weighted_cohens_kappa(left: Sequence[int], right: Sequence[int]) -> float | None:
    """Quadratic weighted Cohen's kappa for ordinal intensity codes."""

    if len(left) != len(right) or not left:
        return None
    if any(value < 0 for value in (*left, *right)):
        return None
    if list(left) == list(right) and len(set(left)) == 1:
        return 1.0
    maximum = max(*left, *right)
    minimum = min(*left, *right)
    if maximum == minimum:
        return None
    categories = list(range(minimum, maximum + 1))
    index = {value: position for position, value in enumerate(categories)}
    size = len(categories)
    observed = [[0.0 for _ in categories] for _ in categories]
    left_counts = [0.0 for _ in categories]
    right_counts = [0.0 for _ in categories]
    for left_value, right_value in zip(left, right, strict=True):
        i = index[left_value]
        j = index[right_value]
        observed[i][j] += 1.0
        left_counts[i] += 1.0
        right_counts[j] += 1.0
    count = float(len(left))
    denominator = float((size - 1) ** 2)
    observed_disagreement = 0.0
    expected_disagreement = 0.0
    for i in range(size):
        for j in range(size):
            weight = ((i - j) ** 2) / denominator
            observed_disagreement += weight * observed[i][j] / count
            expected_disagreement += weight * (left_counts[i] * right_counts[j]) / (count**2)
    if expected_disagreement == 0:
        return 1.0 if observed_disagreement == 0 else None
    return 1.0 - observed_disagreement / expected_disagreement


def build_pilot_quality_report(
    session: Session,
    run_ids: Sequence[UUID],
    reviews: Iterable[HumanPilotReview] = (),
    quarantine_manifest_path: Path | None = None,
) -> PilotQualityReport:
    """Build deterministic aggregate evidence without exporting lyrics or track metadata."""

    if not run_ids:
        raise ValueError("at least one pilot run is required")
    rows = list(
        session.execute(
            select(
                LyricClassificationBatchItem,
                LyricClassificationSnapshot,
                LyricDocument.language_code,
                func.length(LyricDocument.text),
                LyricDocument.source,
            )
            .join(
                LyricClassificationSnapshot,
                LyricClassificationSnapshot.id == LyricClassificationBatchItem.snapshot_id,
            )
            .join(LyricDocument, LyricDocument.id == LyricClassificationBatchItem.lyric_document_id)
            .where(LyricClassificationBatchItem.batch_run_id.in_(run_ids))
            .order_by(
                LyricClassificationBatchItem.batch_run_id,
                LyricClassificationBatchItem.line_number,
            )
        )
    )
    excluded_ids = excluded_document_ids(load_quarantine_entries(quarantine_manifest_path))
    suspended_sources = load_suspended_sources(quarantine_manifest_path)
    quarantined_items = sum(
        item.lyric_document_id in excluded_ids or str(source).upper() in suspended_sources
        for item, _snapshot, _language, _text_length, source in rows
    )
    rows = [
        row
        for row in rows
        if row[0].lyric_document_id not in excluded_ids
        and str(row[4]).upper() not in suspended_sources
    ]
    statuses: Counter[str] = Counter()
    confidence_bands: Counter[str] = Counter()
    confidence_outliers: list[UUID] = []
    intensities: dict[str, Counter[int]] = defaultdict(Counter)
    strata: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "item_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "thought_tokens": 0,
            "known_cost_usd": Decimal(0),
            "known_cost_count": 0,
        }
    )
    blinded: list[BlindedPilotItem] = []
    model_values: dict[UUID, dict[str, int | str]] = {}
    for item, snapshot, language, text_length, _source in rows:
        statuses[snapshot.classification_status] += 1
        confidence = snapshot.confidence
        if confidence is None:
            confidence_bands["unavailable"] += 1
        elif confidence <= 0.5:
            confidence_bands["0.00-0.50"] += 1
            confidence_outliers.append(item.opaque_key)
        elif confidence < 0.8:
            confidence_bands["0.51-0.79"] += 1
        elif confidence < 0.95:
            confidence_bands["0.80-0.94"] += 1
        else:
            confidence_bands["0.95-1.00"] += 1
        flattened = _flatten_result(snapshot.result_json or {})
        model_values[item.opaque_key] = flattened
        for name, value in flattened.items():
            if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 3:
                intensities[name][value] += 1
        language_stratum = str(language or "unknown")
        length_stratum = _length_stratum(int(text_length or 0))
        stratum_name = f"{language_stratum}|{length_stratum}"
        accumulator = strata[stratum_name]
        accumulator["item_count"] += 1
        accumulator["input_tokens"] += snapshot.input_tokens or 0
        accumulator["output_tokens"] += snapshot.output_tokens or 0
        accumulator["thought_tokens"] += snapshot.thought_tokens or 0
        if snapshot.estimated_cost_usd is not None:
            accumulator["known_cost_usd"] += Decimal(snapshot.estimated_cost_usd)
            accumulator["known_cost_count"] += 1
        blinded.append(
            BlindedPilotItem(
                opaque_key=item.opaque_key,
                language_stratum=language_stratum,
                text_length_stratum=length_stratum,
            )
        )
    total = len(rows)
    error_count = statuses.get("error", 0)
    token_strata = {
        name: TokenCostStratum(
            item_count=int(values["item_count"]),
            input_tokens=int(values["input_tokens"]),
            output_tokens=int(values["output_tokens"]),
            thought_tokens=int(values["thought_tokens"]),
            known_cost_usd=(
                Decimal(values["known_cost_usd"]) if int(values["known_cost_count"]) > 0 else None
            ),
        )
        for name, values in sorted(strata.items())
    }
    return PilotQualityReport(
        total_items=total,
        quarantined_items=quarantined_items,
        status_distribution=dict(sorted(statuses.items())),
        confidence_distribution=dict(sorted(confidence_bands.items())),
        confidence_outliers=confidence_outliers,
        intensity_distributions={
            name: dict(sorted(counts.items())) for name, counts in sorted(intensities.items())
        },
        validation_error_rate=(Decimal(error_count) / Decimal(total) if total else Decimal(0)),
        token_cost_by_stratum=token_strata,
        agreement_metrics=_agreement_metrics(model_values, list(reviews)),
        blinded_items=blinded,
    )


def write_blinded_review_manifest(report: PilotQualityReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in report.blinded_items:
            handle.write(item.model_dump_json() + "\n")
    return path


def _length_stratum(length: int) -> str:
    if length < 500:
        return "short"
    if length < 2_000:
        return "medium"
    return "long"


def _flatten_result(value: object, prefix: str = "") -> dict[str, int | str]:
    flattened: dict[str, int | str] = {}
    if not isinstance(value, dict):
        return flattened
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, dict):
            flattened.update(_flatten_result(item, name))
        elif isinstance(item, (int, str)) and not isinstance(item, bool):
            flattened[name] = item
    return flattened


def _agreement_metrics(
    model_values: dict[UUID, dict[str, int | str]], reviews: list[HumanPilotReview]
) -> dict[str, float | None]:
    by_field: dict[str, list[tuple[int | str, int | str]]] = defaultdict(list)
    for review in reviews:
        model = model_values.get(review.opaque_key, {})
        for field, reviewed_value in review.values.items():
            if field in model:
                by_field[field].append((model[field], reviewed_value))
    metrics: dict[str, float | None] = {}
    for field, pairs in sorted(by_field.items()):
        if pairs and all(isinstance(left, int) and isinstance(right, int) for left, right in pairs):
            metrics[field] = weighted_cohens_kappa(
                [int(left) for left, _ in pairs], [int(right) for _, right in pairs]
            )
        elif pairs:
            metrics[field] = sum(left == right for left, right in pairs) / len(pairs)
    return metrics
