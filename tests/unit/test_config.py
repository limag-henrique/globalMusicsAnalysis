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


def test_gemini_key_uses_short_environment_name(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI", "test-key")

    settings = Settings.load(PROJECT_ROOT)

    assert settings.gemini_api_key == "test-key"
