"""Canonical, streaming JSONL contract for Vertex Gemini batch inference."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from uuid import UUID

from google.genai import types

from chart_observatory.db.models.lyrics_batch import LyricClassificationBatchItem
from chart_observatory.lyrics.classification import CostRateCard
from chart_observatory.lyrics.classification_queue import ClassificationCandidate
from chart_observatory.lyrics.gemini_pipeline import build_lyrics_prompt


class BatchJsonlError(ValueError):
    """Raised when an input artifact violates the private wire contract."""


class CostEstimateUnavailable(ValueError):
    """Raised when a positive, conservative estimate cannot be established."""


@dataclass(frozen=True, slots=True)
class BatchJsonlArtifact:
    path: Path
    sha256: str
    byte_count: int
    request_count: int
    first_key: UUID
    last_key: UUID


@dataclass(frozen=True, slots=True)
class BatchExportItem:
    item: LyricClassificationBatchItem
    candidate: ClassificationCandidate
    config: types.GenerateContentConfig


@dataclass(frozen=True, slots=True)
class PilotUsage:
    request_bytes: int
    input_tokens: int
    output_tokens: int
    thought_tokens: int


@dataclass(frozen=True, slots=True)
class BatchCostEstimate:
    expected_input_tokens: int
    expected_output_tokens: int
    conservative_input_tokens: int
    conservative_output_tokens: int
    expected_cost_usd: Decimal
    conservative_cost_usd: Decimal


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def build_batch_request(
    item: LyricClassificationBatchItem,
    candidate: ClassificationCandidate,
    config: types.GenerateContentConfig,
) -> dict[str, object]:
    """Build an envelope whose opaque key is outside model-visible request content."""

    if not candidate.text or not candidate.text.strip():
        raise BatchJsonlError("blank lyrics cannot be exported")
    if item.lyric_document_id != candidate.lyric_document_id:
        raise BatchJsonlError("batch item and candidate document do not match")
    generation_config = config.model_dump(mode="json", by_alias=True, exclude_none=True)
    return {
        "key": str(item.opaque_key),
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_lyrics_prompt(candidate.text, candidate.language)}],
                }
            ],
            "generationConfig": generation_config,
        },
    }


def canonical_request_sha256(payload: Mapping[str, object]) -> str:
    """Hash the canonical echoed provider request for output reconciliation."""

    return hashlib.sha256(_canonical_json_bytes(payload["request"])).hexdigest()


def write_batch_jsonl(
    run_id: UUID,
    items: Iterable[BatchExportItem],
    directory: Path,
    *,
    max_requests: int = 190_000,
    max_bytes: int = 900 * 1024 * 1024,
) -> list[BatchJsonlArtifact]:
    """Stream canonical rows into safety-limited files and verify every artifact."""

    if max_requests < 1 or max_bytes < 1:
        raise ValueError("batch JSONL limits must be positive")
    directory.mkdir(parents=True, exist_ok=True)
    artifacts: list[BatchJsonlArtifact] = []
    expected: dict[UUID, str] = {}
    part = 0
    handle = None
    temporary_path: Path | None = None
    final_path: Path | None = None
    digest = hashlib.sha256()
    byte_count = 0
    request_count = 0
    first_key: UUID | None = None
    last_key: UUID | None = None

    def open_part() -> None:
        nonlocal part, handle, temporary_path, final_path
        nonlocal digest, byte_count, request_count, first_key, last_key
        part += 1
        final_path = directory / f"{run_id}-part-{part:05d}.jsonl"
        temporary_path = final_path.with_suffix(".jsonl.tmp")
        handle = temporary_path.open("xb")
        digest = hashlib.sha256()
        byte_count = 0
        request_count = 0
        first_key = None
        last_key = None

    def close_part() -> None:
        nonlocal handle
        if handle is None or temporary_path is None or final_path is None:
            return
        handle.flush()
        handle.close()
        handle = None
        temporary_path.replace(final_path)
        if first_key is None or last_key is None:
            raise BatchJsonlError("empty JSONL part")
        artifact = BatchJsonlArtifact(
            path=final_path,
            sha256=digest.hexdigest(),
            byte_count=byte_count,
            request_count=request_count,
            first_key=first_key,
            last_key=last_key,
        )
        validated = validate_batch_jsonl(final_path, expected)
        if validated != artifact:
            raise BatchJsonlError("artifact changed during validation")
        artifacts.append(artifact)

    try:
        for export_item in items:
            payload = build_batch_request(
                export_item.item, export_item.candidate, export_item.config
            )
            row = _canonical_json_bytes(payload) + b"\n"
            if len(row) > max_bytes:
                raise BatchJsonlError("one request exceeds the JSONL byte limit")
            if handle is None:
                open_part()
            if request_count and (
                request_count >= max_requests or byte_count + len(row) > max_bytes
            ):
                close_part()
                open_part()
            assert handle is not None
            key = export_item.item.opaque_key
            if key in expected:
                raise BatchJsonlError("duplicate opaque key")
            request_hash = canonical_request_sha256(payload)
            expected[key] = request_hash
            handle.write(row)
            digest.update(row)
            byte_count += len(row)
            request_count += 1
            first_key = first_key or key
            last_key = key
        close_part()
    except Exception:
        if handle is not None:
            handle.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    if not artifacts:
        raise BatchJsonlError("no requests were exported")
    return artifacts


def iter_batch_request_hashes(path: Path) -> Iterator[tuple[UUID, str]]:
    """Stream opaque keys and canonical request hashes from a validated artifact."""

    with path.open("rb") as handle:
        for raw_line in handle:
            try:
                payload = json.loads(raw_line)
                if not isinstance(payload, dict) or set(payload) != {"key", "request"}:
                    raise ValueError
                key = UUID(str(payload["key"]))
                request_hash = canonical_request_sha256(payload)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise BatchJsonlError("cannot recover request hashes from artifact") from exc
            yield key, request_hash


def validate_batch_jsonl(path: Path, expected: Mapping[UUID, str | None]) -> BatchJsonlArtifact:
    """Validate keys, structure, canonical encoding, and request fingerprints."""

    digest = hashlib.sha256()
    byte_count = 0
    count = 0
    seen: set[UUID] = set()
    first_key: UUID | None = None
    last_key: UUID | None = None
    with path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            byte_count += len(raw_line)
            if not raw_line.endswith(b"\n"):
                raise BatchJsonlError("JSONL row is not newline terminated")
            try:
                payload = json.loads(raw_line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BatchJsonlError("malformed JSONL row") from exc
            if not isinstance(payload, dict) or set(payload) != {"key", "request"}:
                raise BatchJsonlError("row envelope contains forbidden fields")
            try:
                key = UUID(str(payload["key"]))
            except (TypeError, ValueError) as exc:
                raise BatchJsonlError("malformed opaque key") from exc
            if key in seen:
                raise BatchJsonlError("duplicate opaque key")
            if key not in expected or expected[key] is None:
                raise BatchJsonlError("unknown opaque key")
            request = payload["request"]
            if not isinstance(request, dict) or set(request) != {
                "contents",
                "generationConfig",
            }:
                raise BatchJsonlError("request contains forbidden metadata")
            if canonical_request_sha256(payload) != expected[key]:
                raise BatchJsonlError("request fingerprint mismatch")
            if _canonical_json_bytes(payload) + b"\n" != raw_line:
                raise BatchJsonlError("JSONL row is not canonical")
            seen.add(key)
            count += 1
            first_key = first_key or key
            last_key = key
    if count == 0 or first_key is None or last_key is None:
        raise BatchJsonlError("empty JSONL artifact")
    return BatchJsonlArtifact(
        path=path,
        sha256=digest.hexdigest(),
        byte_count=byte_count,
        request_count=count,
        first_key=first_key,
        last_key=last_key,
    )


def _median(values: Sequence[int]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return Decimal(ordered[middle])
    return Decimal(ordered[middle - 1] + ordered[middle]) / 2


def estimate_batch_cost(
    artifacts: Sequence[BatchJsonlArtifact],
    exact_input_tokens: Sequence[int] | None,
    pilot_usage: Sequence[PilotUsage],
    rate_card: CostRateCard,
    max_output_tokens: int,
) -> BatchCostEstimate:
    """Estimate cost; after a representative pilot, reserve above its worst token/byte ratio."""

    if not artifacts or max_output_tokens < 1:
        raise CostEstimateUnavailable("batch cost inputs are unavailable")
    input_rate = rate_card.input_usd_per_million_tokens
    output_rate = rate_card.output_usd_per_million_tokens
    if input_rate is None or output_rate is None or input_rate <= 0 or output_rate <= 0:
        raise CostEstimateUnavailable("positive batch token rates are required")
    request_count = sum(artifact.request_count for artifact in artifacts)
    total_bytes = sum(artifact.byte_count for artifact in artifacts)
    if exact_input_tokens is not None:
        if len(exact_input_tokens) != request_count or any(
            value <= 0 for value in exact_input_tokens
        ):
            raise CostEstimateUnavailable("exact input token counts are incomplete")
        expected_input = sum(exact_input_tokens)
    else:
        if not pilot_usage or any(
            item.request_bytes <= 0 or item.input_tokens <= 0 for item in pilot_usage
        ):
            raise CostEstimateUnavailable("pilot usage is required for corpus estimation")
        ratios = [Decimal(item.input_tokens) / Decimal(item.request_bytes) for item in pilot_usage]
        ratio = sorted(ratios)[len(ratios) // 2]
        expected_input = max(1, int(Decimal(total_bytes) * ratio))
    if pilot_usage:
        output_totals = [item.output_tokens + item.thought_tokens for item in pilot_usage]
        expected_output = max(1, int(_median(output_totals) * request_count))
    else:
        expected_output = request_count * max_output_tokens
    conservative_input = total_bytes
    if len(pilot_usage) >= 20:
        worst_observed_ratio = max(
            Decimal(item.input_tokens) / Decimal(item.request_bytes) for item in pilot_usage
        )
        conservative_input = int(
            (Decimal(total_bytes) * worst_observed_ratio * Decimal("1.20")).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
    # A pilot does not bound token density in all languages. Retain the UTF-8
    # byte allowance even when the observed token/byte ratio is lower.
    conservative_input = max(conservative_input, total_bytes, sum(exact_input_tokens or ()))
    conservative_output = request_count * max_output_tokens
    million = Decimal(1_000_000)
    expected_cost = (
        Decimal(expected_input) * input_rate + Decimal(expected_output) * output_rate
    ) / million
    conservative_cost = (
        Decimal(conservative_input) * input_rate + Decimal(conservative_output) * output_rate
    ) / million
    if expected_cost <= 0 or conservative_cost <= 0 or conservative_cost < expected_cost:
        raise CostEstimateUnavailable("cost estimate is non-positive or not conservative")
    return BatchCostEstimate(
        expected_input_tokens=expected_input,
        expected_output_tokens=expected_output,
        conservative_input_tokens=conservative_input,
        conservative_output_tokens=conservative_output,
        expected_cost_usd=expected_cost,
        conservative_cost_usd=conservative_cost,
    )
