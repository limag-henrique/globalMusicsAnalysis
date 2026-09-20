from decimal import Decimal
from pathlib import Path

from chart_observatory.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_research_window_is_loaded_from_configuration() -> None:
    settings = Settings.load(PROJECT_ROOT)

    assert settings.research.start_date.isoformat() == "2021-01-01"
    assert settings.research.end_date is None


def test_market_universe_is_not_a_static_country_whitelist() -> None:
    settings = Settings.load(PROJECT_ROOT)

    assert settings.countries == ()


def test_google_cloud_project_uses_environment_name(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")

    settings = Settings.load(PROJECT_ROOT)

    assert settings.google_cloud_project == "test-project"


def test_gemini_settings_use_unprefixed_environment_aliases(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("GEMINI_THINKING_LEVEL", "LOW")
    monkeypatch.setenv("GEMINI_OUTPUT_TOKEN_ALLOWANCE", "2048")
    monkeypatch.setenv("GEMINI_INPUT_USD_PER_MILLION_TOKENS", "0.5")
    monkeypatch.setenv("GEMINI_OUTPUT_USD_PER_MILLION_TOKENS", "1.5")
    monkeypatch.setenv("GEMINI_THOUGHT_USD_PER_MILLION_TOKENS", "2.5")

    settings = Settings.load(PROJECT_ROOT)

    assert settings.gemini_model == "gemini-3.5-flash"
    assert settings.gemini_thinking_level == "LOW"
    assert settings.gemini_output_token_allowance == 2048
    assert settings.gemini_input_usd_per_million_tokens == Decimal("0.5")
    assert settings.gemini_output_usd_per_million_tokens == Decimal("1.5")
    assert settings.gemini_thought_usd_per_million_tokens == Decimal("2.5")
