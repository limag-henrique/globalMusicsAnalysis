from pathlib import Path

import polars as pl

from chart_observatory.corpus.eligibility import EligibilityRules
from chart_observatory.corpus.freeze import freeze_source_artifacts


def test_freeze_source_artifacts_records_hashes_and_eligibility(tmp_path: Path) -> None:
    observations = tmp_path / "observations.parquet"
    coverage = tmp_path / "coverage.parquet"
    dataset = tmp_path / "dataset.parquet"
    output = tmp_path / "manifest.json"
    pl.DataFrame({"country_code": ["BR"], "rank": [1]}).write_parquet(observations)
    pl.DataFrame(
        {
            "country_code": ["BR", "US"],
            "eligible": [True, False],
            "first_date": ["2020-01-01", "2020-01-01"],
            "last_date": ["2023-01-01", "2023-01-01"],
        }
    ).write_parquet(coverage)
    pl.DataFrame({"value": [1, 2]}).write_parquet(dataset)

    manifest = freeze_source_artifacts(
        observations,
        coverage,
        output,
        analytical_datasets=(dataset,),
        rules=EligibilityRules(minimum_years=3),
    )

    assert manifest["status"] == "FROZEN"
    assert manifest["operational_membership_status"] == "PENDING_POSTGRESQL_LOAD"
    assert manifest["eligible_cells"] == 1
    assert len(manifest["observations"]["sha256"]) == 64
    assert output.exists()
