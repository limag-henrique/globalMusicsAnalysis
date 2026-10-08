"""Explicitly authorized live canary; collection performs no external initialization."""

import os
import time
from dataclasses import dataclass
from decimal import Decimal

import pytest


@dataclass(frozen=True, slots=True)
class LiveCanaryResult:
    request_count: int
    opaque_key: str
    returned_key: str
    snapshot_status: str


def run_one_item_canary_from_environment() -> LiveCanaryResult:
    from pathlib import Path

    from sqlalchemy import select

    from chart_observatory.application import ResearchApplication
    from chart_observatory.config import Settings
    from chart_observatory.db.models.corpus import LyricClassificationSnapshot
    from chart_observatory.db.models.lyrics_batch import LyricClassificationBatchItem
    from chart_observatory.lyrics.batch_contract import BatchRunState
    from chart_observatory.lyrics.batch_service import (
        BATCH_MAX_OUTPUT_TOKENS,
        BatchClassificationService,
    )
    from chart_observatory.lyrics.batch_storage import BatchStorageAdapter
    from chart_observatory.lyrics.batch_vertex import VertexBatchAdapter
    from chart_observatory.lyrics.gemini_pipeline import GeminiLyricsClassifier

    required = (
        "CHART_OBSERVATORY_DATABASE_URL",
        "GOOGLE_CLOUD_PROJECT",
        "GEMINI_BATCH_BUCKET",
        "GEMINI_BATCH_INPUT_USD_PER_MILLION_TOKENS",
        "GEMINI_BATCH_OUTPUT_USD_PER_MILLION_TOKENS",
        "LIVE_VERTEX_BATCH_MAX_COST_USD",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("missing live canary environment: " + ", ".join(missing))
    if os.getenv("GEMINI_MODEL") != "gemini-3.8-flash":
        raise RuntimeError("live canary requires GEMINI_MODEL=gemini-3.8-flash")
    if os.getenv("GEMINI_THINKING_LEVEL") != "LOW":
        raise RuntimeError("live canary requires GEMINI_THINKING_LEVEL=LOW")
    cap = Decimal(os.environ["LIVE_VERTEX_BATCH_MAX_COST_USD"])
    if not cap.is_finite() or cap <= 0 or cap > Decimal("600"):
        raise RuntimeError("live canary cost cap must be in (0, 600]")

    settings = Settings.load(Path.cwd())
    application = ResearchApplication(
        Path("data/runtime"), database_url=os.environ["CHART_OBSERVATORY_DATABASE_URL"]
    )
    assert settings.google_cloud_project and settings.gemini_batch_bucket
    storage = BatchStorageAdapter.from_adc(
        settings.google_cloud_project, settings.gemini_batch_bucket
    )
    vertex = VertexBatchAdapter(settings.google_cloud_project, "global")
    counter = GeminiLyricsClassifier(
        settings.google_cloud_project,
        "global",
        "gemini-3.8-flash",
        thinking_level="LOW",
        max_output_tokens=BATCH_MAX_OUTPUT_TOKENS,
    )
    service = BatchClassificationService(
        application.session, settings, storage, vertex, token_counter=counter
    )
    prepared = service.prepare_canary(cap)
    if len(prepared) != 1 or prepared[0].request_count != 1:
        raise RuntimeError("live canary preparation did not reserve exactly one item")
    run_id = prepared[0].run_id
    service.submit(run_id, cap)
    deadline = time.monotonic() + 6 * 60 * 60
    terminal = {
        BatchRunState.SUCCEEDED,
        BatchRunState.FAILED,
        BatchRunState.CANCELLED,
        BatchRunState.EXPIRED,
    }
    while True:
        job = service.status(run_id)
        if job.state in terminal:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("live canary did not become terminal within six hours")
        time.sleep(30)
    service.import_results(run_id)
    service.finalize(run_id)
    service.cleanup(run_id)
    item = application.session.scalar(
        select(LyricClassificationBatchItem).where(
            LyricClassificationBatchItem.batch_run_id == run_id
        )
    )
    if item is None:
        raise RuntimeError("live canary produced no batch item")
    snapshot = application.session.scalar(
        select(LyricClassificationSnapshot).where(
            LyricClassificationSnapshot.id == item.snapshot_id
        )
    )
    if snapshot is None:
        raise RuntimeError("live canary produced no snapshot")
    return LiveCanaryResult(
        request_count=1,
        opaque_key=str(item.opaque_key),
        returned_key=str(snapshot.batch_item_key),
        snapshot_status=snapshot.classification_status,
    )


@pytest.mark.live
def test_vertex_batch_canary_round_trips_opaque_key() -> None:
    if os.getenv("RUN_VERTEX_BATCH_CANARY") != "1":
        pytest.skip("explicit live authorization required")
    result = run_one_item_canary_from_environment()
    assert result.request_count == 1
    assert result.returned_key == result.opaque_key
    assert result.snapshot_status in {
        "classified",
        "ambiguous",
        "blocked",
        "language_unsupported",
    }
