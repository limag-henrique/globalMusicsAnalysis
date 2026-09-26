"""Collection-safe smoke test for Vertex AI lyric classification using ADC."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from chart_observatory.config import Settings
from chart_observatory.lyrics.classification import LyricsClassification
from chart_observatory.lyrics.gemini_pipeline import (
    GeminiLyricsClassifier,
    GeminiOutcomeStatus,
)

LIVE_SMOKE_ENV_VAR = "CHART_OBSERVATORY_LIVE_SMOKE"

# Self-contained fixture lyric — never accesses production database
_FIXTURE_LYRIC = """Eu te amo tanto meu amor
Você é a razão do meu viver
Quero estar contigo noite e dia
Nosso amor nunca vai morrer"""


def adc_smoke_is_configured() -> bool:
    """Return True only when opt-in flag and all required cloud settings are present."""
    if os.environ.get(LIVE_SMOKE_ENV_VAR) != "1":
        return False
    try:
        settings = Settings.load(Path.cwd())
    except Exception:
        return False
    return bool(
        settings.google_cloud_project
        and settings.google_cloud_location
        and settings.gemini_model
    )


def run_one_fixture_lyric() -> LyricsClassification:
    """Execute classification for exactly one hardcoded fixture lyric."""
    settings = Settings.load(Path.cwd())
    if not settings.google_cloud_project:
        raise ValueError("GOOGLE_CLOUD_PROJECT is required for live smoke test")
    if not settings.gemini_model:
        raise ValueError("GEMINI_MODEL is required for live smoke test")

    classifier = GeminiLyricsClassifier(
        project_id=settings.google_cloud_project,
        location=settings.google_cloud_location,
        model_id=settings.gemini_model,
        thinking_level=settings.gemini_thinking_level,
        max_output_tokens=settings.gemini_output_token_allowance,
    )
    outcome = classifier.classify(_FIXTURE_LYRIC, language="pt")
    if outcome.outcome is not GeminiOutcomeStatus.SUCCESS or outcome.result is None:
        raise RuntimeError(
            f"Live classification failed with outcome: {outcome.outcome.value} "
            f"({outcome.error or 'no error details'})"
        )
    return outcome.result


@pytest.mark.live
def test_classifies_one_lyric_with_adc() -> None:
    if not adc_smoke_is_configured():
        pytest.skip("ADC smoke configuration is absent")
    outcome = run_one_fixture_lyric()
    assert outcome.classification_status in {"classified", "ambiguous"}
