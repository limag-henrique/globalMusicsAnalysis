from pathlib import Path

import polars as pl
import pytest

from chart_observatory.analysis.historical_models import export_historical_models
from chart_observatory.analysis.historical_panel import export_historical_panel


def test_export_weights_days_preserves_censoring_and_music_denominators(tmp_path: Path) -> None:
    annual = pl.DataFrame(
        {"market_code": ["BR"], "year": [2021], "classified_tracks": [400], "coverage": [0.8]}
    )
    rows = pl.DataFrame(
        {
            "country_iso2": ["BR"] * 3,
            "term": ["porn"] * 3,
            "language": ["en"] * 3,
            "comparison_group": ["batch"] * 3,
            "aggregation": ["Month"] * 3,
            "sample_date": ["2021-01-01", "2021-02-01", "2021-03-01"],
            "period_start": ["2021-01-01"] * 3,
            "period_end": ["2021-03-13"] * 3,
            "value": [10.0, None, 90.0],
            "status": [
                "observed_relative_index",
                "below_reporting_threshold",
                "observed_relative_index",
            ],
            "raw_sha256": ["hash"] * 3,
        }
    )
    export_historical_panel(annual, rows, tmp_path)
    panel = pl.read_parquet(tmp_path / "country-year-trends.parquet")
    assert panel.height == 1
    r = panel.row(0, named=True)
    assert r["classified_tracks"] == 400
    assert r["covered_days"] == 59
    assert r["expected_days"] == 72
    assert r["excluded_boundary_samples"] == 1
    assert r["mean_index"] is None
    assert abs(r["mean_lower"] - 310 / 59) < 1e-10
    assert abs(r["mean_upper"] - 338 / 59) < 1e-10
    assert r["cross_country_comparable"] is False


def test_week_crossing_calendar_year_is_split_and_duplicate_samples_rejected(
    tmp_path: Path,
) -> None:
    annual = pl.DataFrame(
        {
            "market_code": ["BR", "BR"],
            "year": [2020, 2021],
            "classified_tracks": [400, 500],
            "coverage": [0.8, 0.9],
        }
    )
    row = {
        "country_iso2": "BR",
        "term": "porn",
        "language": "en",
        "comparison_group": "batch",
        "aggregation": "Week",
        "sample_date": "2020-12-28",
        "period_start": "2020-01-01",
        "period_end": "2021-12-31",
        "value": 10.0,
        "status": "observed_relative_index",
        "raw_sha256": "hash",
    }
    export_historical_panel(annual, pl.from_dicts([row]), tmp_path)
    panel = pl.read_parquet(tmp_path / "country-year-trends.parquet").sort("year")
    assert panel["covered_days"].to_list() == [4, 3]
    assert panel["expected_days"].to_list() == [366, 365]
    assert panel["mean_index"].to_list() == [10.0, 10.0]
    with pytest.raises(ValueError, match="Duplicate Trends"):
        export_historical_panel(annual, pl.from_dicts([row, row]), tmp_path)


def test_models_use_one_local_anchor_exclude_partial_and_publish_insufficient_n(
    tmp_path: Path,
) -> None:
    rows = []
    for group in ["a", "b"]:
        for year in range(2017, 2023):
            rows.append(
                {
                    "market_code": "BR",
                    "year": year,
                    "term": "porn",
                    "language": "en",
                    "comparison_group": group,
                    "mean_index": float(year - 2016),
                    "partial_year": year == 2022,
                    "temporal_coverage": 1.0,
                    "coverage": 0.9,
                    "classified_tracks": 400,
                    "explicitness_pct": float(year - 2015),
                }
            )
    export_historical_models(pl.from_dicts(rows), tmp_path)
    sample = pl.read_csv(tmp_path / "model-samples.csv")
    assert sample["comparison_group"].unique().to_list() == ["a"]
    assert 2022 not in sample["year"].to_list()
    assert sample.filter(pl.col("model_id") == "explicitness_pct__baseline").height == 5
    results = pl.read_csv(tmp_path / "historical-associations.csv")
    assert set(results["status"]) == {"insufficient_countries"}
    assert results["coefficient"].null_count() == results.height


def test_fixed_effects_export_recovers_known_within_country_coefficient(tmp_path: Path) -> None:
    rows = []
    for country in range(25):
        for t in range(5):
            x = (t + country) % 5 - 2
            rows.append(
                {
                    "market_code": f"X{country}",
                    "year": 2017 + t,
                    "term": "porn",
                    "language": "en",
                    "comparison_group": "a",
                    "mean_index": float(10 + x),
                    "partial_year": False,
                    "temporal_coverage": 1.0,
                    "coverage": 0.9,
                    "classified_tracks": 400,
                    "explicitness_pct": 10 + country * 0.1 + t * 0.2 + 2 * x,
                }
            )
    export_historical_models(pl.from_dicts(rows), tmp_path)
    results = pl.read_csv(tmp_path / "historical-associations.csv")
    baseline = results.filter(pl.col("specification") == "baseline").row(0, named=True)
    assert baseline["n_countries"] == 25
    assert baseline["n_country_years"] == 125
    assert abs(baseline["coefficient"] - 2.8284271247461903) < 1e-9
    assert baseline["status"] == "exploratory_country_year_fixed_effects"
