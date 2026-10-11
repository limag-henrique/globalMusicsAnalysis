from pathlib import Path

import polars as pl
import pytest

from chart_observatory.analysis.article_context import export_crossings


def test_export_preserves_missing_zero_scope_and_music_denominator(tmp_path: Path) -> None:
    annual = pl.DataFrame(
        {
            "market_code": ["BR", "BR", "TW", "GLOBAL", "HK"],
            "year": [2021, 2022, 2021, 2021, 2021],
            "classified_tracks": [100, 80, 30, 500, 90],
            "violence_pct": [10.0, 20.0, 5.0, 12.0, 3.0],
        }
    )
    observations = pl.DataFrame(
        {
            "market_code": ["BR", "BR", "BR"],
            "reference_year": [2021, 2022, 2020],
            "indicator_code": ["test", "test", "test"],
            "value": [0.0, None, 9.0],
            "source": ["fixture"] * 3,
        }
    )
    export_crossings(annual, observations, ["test"], tmp_path)
    panel = pl.read_parquet(tmp_path / "country-year-crossings.parquet").sort("market_code", "year")
    assert panel.height == 3
    assert panel["classified_tracks"].to_list() == [100, 80, 30]
    assert panel["test"].to_list() == [0.0, None, None]
    assert panel["music_period_end"].to_list() == ["2021-12-31", "2022-03-13", "2021-12-31"]
    coverage = pl.read_parquet(tmp_path / "coverage.parquet").sort("market_code", "reference_year")
    assert coverage["coverage_status"].to_list() == ["observed", "source_missing", "not_returned"]


def test_export_rejects_duplicate_indicator_instead_of_multiplying_music(tmp_path: Path) -> None:
    annual = pl.DataFrame({"market_code": ["BR"], "year": [2021], "classified_tracks": [100]})
    observations = pl.DataFrame(
        {
            "market_code": ["BR", "BR"],
            "reference_year": [2021, 2021],
            "indicator_code": ["test", "test"],
            "value": [1.0, 2.0],
        }
    )
    with pytest.raises(ValueError, match="Duplicate"):
        export_crossings(annual, observations, ["test"], tmp_path)
