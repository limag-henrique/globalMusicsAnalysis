from decimal import Decimal

import pytest
from pydantic import ValidationError

from chart_observatory.lyrics.classification import (
    AntisocialDimension,
    CostRateCard,
    GenerationPolicy,
    UsageTelemetry,
)


def test_gemini_3_policy_uses_thinking_without_sampling() -> None:
    """Catches a Gemini 3 policy that sends incompatible sampling arguments."""
    policy = GenerationPolicy.for_model("gemini-3.5-flash", "MINIMAL")

    assert policy.temperature is None
    assert policy.top_p is None
    assert policy.top_k is None
    assert policy.thinking_level == "MINIMAL"


def test_classification_rejects_invalid_intensity_and_stance() -> None:
    """Catches acceptance of taxonomy values outside the agreed vocabulary or range."""
    with pytest.raises(ValidationError):
        AntisocialDimension(intensity=4, stance="glorified")
    with pytest.raises(ValidationError):
        AntisocialDimension(intensity=1, stance="celebrated")


def test_rate_card_returns_no_cost_for_partial_usage() -> None:
    """Catches a cost estimate that invents missing output or thought token counts."""
    rate_card = CostRateCard(
        input_usd_per_million_tokens=Decimal("1"),
        output_usd_per_million_tokens=Decimal("2"),
        thought_usd_per_million_tokens=Decimal("3"),
    )

    assert rate_card.calculate(UsageTelemetry(input_tokens=100)) is None
