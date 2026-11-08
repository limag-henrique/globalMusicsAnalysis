import hashlib
import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def module():
    path = Path(__file__).resolve().parents[3] / "scripts/prepare_vertex_readiness.py"
    spec = importlib.util.spec_from_file_location("vertex_readiness_test", path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def evidence():
    return dict(
        verified_on="2026-11-08",
        valid_through="2026-12-31",
        model_id="gemini-3.8-flash",
        location="global",
        mode="batch",
        input_per_million_tokens="0.375",
        output_including_reasoning_per_million_tokens="1.875",
    )


def settings():
    return SimpleNamespace(
        gemini_model="gemini-3.8-flash",
        google_cloud_location="global",
        gemini_batch_input_usd_per_million_tokens=Decimal("0.375"),
        gemini_batch_output_usd_per_million_tokens=Decimal("1.875"),
    )


def test_verified_price_covers_configured_batch_not_other_billing_classes(module):
    module.validate_prices(evidence(), settings(), date(2026, 11, 8))


@pytest.mark.parametrize("today", [date(2026, 11, 7), date(2027, 1, 1)])
def test_future_or_expired_price_cannot_prepare_research(module, today):
    with pytest.raises(ValueError, match="expired or from the future"):
        module.validate_prices(evidence(), settings(), today)


@pytest.mark.parametrize(
    "change",
    [
        dict(location="us-central1"),
        dict(mode="online"),
        dict(model_id="another-model"),
        dict(input_per_million_tokens="0.1"),
        dict(output_including_reasoning_per_million_tokens="0.1"),
    ],
)
def test_model_region_mode_and_both_token_rates_are_bound_to_evidence(module, change):
    with pytest.raises(ValueError, match="differ"):
        module.validate_prices({**evidence(), **change}, settings(), date(2026, 11, 8))


def test_frozen_rankings_are_checked_instead_of_trusting_old_manifest(module, tmp_path):
    path = tmp_path / "ranking.csv"
    path.write_bytes(b"original ranking")
    expected = {"ranking.csv": hashlib.sha256(path.read_bytes()).hexdigest()}
    assert module.verify_inputs(tmp_path, expected) == expected
    path.write_bytes(b"changed ranking")
    with pytest.raises(ValueError, match="input changed"):
        module.verify_inputs(tmp_path, expected)


def test_selection_manifest_cannot_read_outside_project(module, tmp_path):
    with pytest.raises(ValueError, match="outside project"):
        module.verify_inputs(tmp_path, {"../elsewhere": "a" * 64})
