from pathlib import Path

from chart_observatory.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_research_window_is_loaded_from_configuration() -> None:
    settings = Settings.load(PROJECT_ROOT)

    assert settings.research.start_date.isoformat() == "2021-01-01"
    assert settings.research.end_date is None


def test_initial_country_codes_are_exact() -> None:
    settings = Settings.load(PROJECT_ROOT)

    assert {country.code for country in settings.countries} == {
        "BR",
        "US",
        "GB",
        "FR",
        "DE",
        "ES",
        "PT",
        "IT",
        "SE",
    }
