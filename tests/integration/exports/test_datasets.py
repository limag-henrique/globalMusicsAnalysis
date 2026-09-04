from pathlib import Path

import polars as pl

from chart_observatory.exports.datasets import DATASET_SCHEMAS
from chart_observatory.exports.writer import AtomicDatasetWriter


def test_five_dataset_schemas_are_named_and_round_trip_nulls(tmp_path: Path) -> None:
    assert set(DATASET_SCHEMAS) == {
        "track_master",
        "chart_observations",
        "track_platform_country_summary",
        "cross_platform_presence",
        "coverage_matrix",
    }
    frame = pl.DataFrame({"position": [1, 2], "metric_value": [10.5, None]})
    writer = AtomicDatasetWriter(tmp_path)
    csv_path = writer.write(frame, "chart_observations", "csv")
    parquet_path = writer.write(frame, "chart_observations", "parquet")
    assert pl.read_csv(csv_path)["metric_value"].to_list() == [10.5, None]
    assert pl.read_parquet(parquet_path)["metric_value"].to_list() == [10.5, None]
