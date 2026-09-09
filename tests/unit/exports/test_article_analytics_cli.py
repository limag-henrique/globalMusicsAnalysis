import json
from datetime import date
from pathlib import Path

import polars as pl
from typer.testing import CliRunner

from chart_observatory.cli import app


def test_article_analytics_cli_writes_persistence_and_genre_outputs(tmp_path: Path) -> None:
    source = tmp_path / "canonical.parquet"
    pl.DataFrame(
        {
            "provider": ["MGD", "MGD"],
            "origin_platform": ["SPOTIFY", "SPOTIFY"],
            "market_code": ["BR", "BR"],
            "chart_family": ["TOP_200", "TOP_200"],
            "period_start": [date(2020, 1, 1), date(2020, 1, 8)],
            "period_end": [date(2020, 1, 7), date(2020, 1, 14)],
            "rank": [1, 2],
            "canonical_track_id": ["track-a", "track-a"],
        }
    ).write_parquet(source)
    claims = tmp_path / "genre_claims.parquet"
    pl.DataFrame(
        {"canonical_track_id": ["track-a"], "normalized_genre": ["funk"]}
    ).write_parquet(claims)
    output_dir = tmp_path / "article"

    result = CliRunner().invoke(
        app,
        [
            "corpus",
            "analytics",
            "--observations",
            str(source),
            "--genre-claims",
            str(claims),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "MATERIALIZED"
    assert (output_dir / "persistence.parquet").exists()
    assert pl.read_parquet(output_dir / "genre_variation.parquet").height == 1
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "article-analytics-v1"
    assert len(manifest["input"]["sha256"]) == 64
    assert len(manifest["outputs"]["persistence"]["sha256"]) == 64
