from pathlib import Path

import polars as pl

from chart_observatory.exports.datasets import DATASET_SCHEMAS
from chart_observatory.exports.writer import AtomicDatasetWriter


def test_five_dataset_schemas_are_named_and_round_trip_nulls(tmp_path: Path) -> None:
    assert {
        "track_master",
        "chart_observations",
        "track_platform_country_summary",
        "cross_platform_presence",
        "coverage_matrix",
    }.issubset(DATASET_SCHEMAS)
    assert {
        "category_prevalence_by_country",
        "category_exposure_by_country",
        "turnover_by_market_period",
        "rq2_content_country",
        "rq3_content_country_genre",
        "rq4_content_success",
        "survival_by_track",
        "survival_model_summary",
    }.issubset(DATASET_SCHEMAS)
    frame = pl.DataFrame({"position": [1, 2], "metric_value": [10.5, None]})
    writer = AtomicDatasetWriter(tmp_path)
    csv_path = writer.write(frame, "chart_observations", "csv")
    parquet_path = writer.write(frame, "chart_observations", "parquet")
    assert pl.read_csv(csv_path)["metric_value"].to_list() == [10.5, None]
    assert pl.read_parquet(parquet_path)["metric_value"].to_list() == [10.5, None]
