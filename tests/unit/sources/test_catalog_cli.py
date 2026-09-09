import json
from pathlib import Path

import polars as pl
from typer.testing import CliRunner

from chart_observatory.cli import app


def _write_source(root: Path) -> None:
    normalized = root / "data/normalized"
    normalized.mkdir(parents=True)
    pl.DataFrame(
        {
            "provider": ["MGD", "MGD"],
            "origin_platform": ["SPOTIFY", "SPOTIFY"],
            "country_code": ["BR", "US"],
            "chart_name": ["Top 200", "Top 200"],
            "period_start": ["2021-01-01", "2021-01-01"],
            "rank": [1, 2],
            "track_title": ["BR song", "US song"],
        }
    ).write_parquet(normalized / "mgd_observations.parquet")


def test_catalog_cli_materializes_complete_local_catalog(tmp_path: Path) -> None:
    _write_source(tmp_path)
    output = tmp_path / "data/derived/source_catalog.parquet"

    result = CliRunner().invoke(
        app,
        ["corpus", "catalog", "--root", str(tmp_path), "--output", str(output)],
    )

    assert result.exit_code == 0, result.stdout
    assert output.exists()
    assert pl.read_parquet(output).height == 2
    assert json.loads(result.stdout)["status"] == "MATERIALIZED"


def test_catalog_cli_lists_filtered_rows_as_json(tmp_path: Path) -> None:
    _write_source(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "corpus",
            "catalog",
            "--root",
            str(tmp_path),
            "--country",
            "BR",
            "--year",
            "2021",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "LISTED"
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["market_code"] == "BR"
