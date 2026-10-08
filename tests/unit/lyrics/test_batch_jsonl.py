import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from chart_observatory.db.models.lyrics_batch import LyricClassificationBatchItem
from chart_observatory.lyrics.batch_jsonl import (
    BatchExportItem,
    BatchJsonlArtifact,
    CostEstimateUnavailable,
    PilotUsage,
    build_batch_request,
    estimate_batch_cost,
    iter_batch_request_hashes,
    validate_batch_jsonl,
    write_batch_jsonl,
)
from chart_observatory.lyrics.classification import CostRateCard
from chart_observatory.lyrics.classification_queue import ClassificationCandidate
from chart_observatory.lyrics.gemini_pipeline import build_lyrics_generation_config


def export_item(line: int) -> BatchExportItem:
    key = uuid4()
    candidate = ClassificationCandidate(
        lyric_document_id=uuid4(),
        canonical_track_id=uuid4(),
        lyrics_hash=f"{line:064d}",
        text=f"unique private lyric text number {line}",
        language="pt-BR",
        instrumental=False,
    )
    item = LyricClassificationBatchItem(
        opaque_key=key,
        batch_run_id=uuid4(),
        line_number=line,
        lyric_document_id=candidate.lyric_document_id,
        canonical_track_id=candidate.canonical_track_id,
        lyrics_hash=candidate.lyrics_hash,
        model_id="gemini-3.8-flash",
        taxonomy_version="taxonomy",
        prompt_version="prompt",
        state="reserved",
    )
    return BatchExportItem(
        item=item,
        candidate=candidate,
        config=build_lyrics_generation_config("gemini-3.8-flash", "LOW", 4096),
    )


def test_request_contains_only_key_and_lyric_request() -> None:
    prepared = export_item(1)

    payload = build_batch_request(prepared.item, prepared.candidate, prepared.config)
    encoded = json.dumps(payload)

    assert set(payload) == {"key", "request"}
    assert payload["key"] == str(prepared.item.opaque_key)
    assert "Artist Name" not in encoded
    assert "chart_rank" not in encoded
    assert "responseJsonSchema" in encoded


def test_batch_request_inlines_response_schema_references() -> None:
    prepared = export_item(1)

    payload = build_batch_request(prepared.item, prepared.candidate, prepared.config)
    encoded = json.dumps(payload["request"]["generationConfig"]["responseJsonSchema"])

    assert '"$ref"' not in encoded
    assert '"$defs"' not in encoded


def test_writer_splits_and_validator_matches_request_hashes(tmp_path) -> None:
    items = [export_item(number) for number in range(1, 4)]

    artifacts = write_batch_jsonl(uuid4(), items, tmp_path, max_requests=2, max_bytes=1_000_000)
    expected = {
        key: request_hash
        for artifact in artifacts
        for key, request_hash in iter_batch_request_hashes(artifact.path)
    }

    assert [artifact.request_count for artifact in artifacts] == [2, 1]
    assert all(item.item.request_sha256 is None for item in items)
    for artifact in artifacts:
        assert validate_batch_jsonl(artifact.path, expected).sha256 == artifact.sha256


def test_estimate_refuses_missing_pilot_usage(tmp_path) -> None:
    artifacts = write_batch_jsonl(uuid4(), [export_item(1)], tmp_path)
    rates = CostRateCard(
        input_usd_per_million_tokens=Decimal("0.375"),
        output_usd_per_million_tokens=Decimal("1.875"),
    )

    with pytest.raises(CostEstimateUnavailable):
        estimate_batch_cost(artifacts, None, [], rates, 4096)


def test_estimate_is_positive_and_conservative(tmp_path) -> None:
    artifacts = write_batch_jsonl(uuid4(), [export_item(1), export_item(2)], tmp_path)
    rates = CostRateCard(
        input_usd_per_million_tokens=Decimal("0.375"),
        output_usd_per_million_tokens=Decimal("1.875"),
    )

    estimate = estimate_batch_cost(
        artifacts,
        [500, 600],
        [PilotUsage(request_bytes=2000, input_tokens=500, output_tokens=300, thought_tokens=20)],
        rates,
        4096,
    )

    assert estimate.expected_cost_usd > 0
    assert estimate.conservative_cost_usd >= estimate.expected_cost_usd


def test_corpus_reservation_uses_worst_observed_pilot_token_byte_ratio_with_margin() -> None:
    artifact = BatchJsonlArtifact(
        path=Path("main.jsonl"),
        sha256="a" * 64,
        byte_count=10_000,
        request_count=20,
        first_key=uuid4(),
        last_key=uuid4(),
    )
    usage = [PilotUsage(100, 50, 300, 0) for _ in range(20)]
    rates = CostRateCard(
        input_usd_per_million_tokens=Decimal("0.375"),
        output_usd_per_million_tokens=Decimal("1.875"),
    )

    estimate = estimate_batch_cost([artifact], None, usage, rates, 1_024)

    assert estimate.conservative_input_tokens == 6_000
    assert estimate.conservative_output_tokens == 20_480
    assert estimate.conservative_cost_usd == Decimal("0.040650")
