from datetime import date
from pathlib import Path

from chart_observatory.sources.kaggle import KaggleSpotifyChartsSource


def test_kaggle_keeps_top200_and_viral50_separate() -> None:
    rows = list(
        KaggleSpotifyChartsSource(
            Path(__file__).parents[2] / "fixtures" / "kaggle"
        ).iter_observations()
    )
    assert {row.chart_name for row in rows} == {"top200", "viral50"}
    assert rows[0].metric_value == 1000
    assert rows[1].metric_value is None
    assert rows[1].origin_platform == "SPOTIFY"


def test_kaggle_discovers_all_regions() -> None:
    manifest = KaggleSpotifyChartsSource(
        Path(__file__).parents[2] / "fixtures" / "kaggle"
    ).inspect()
    assert manifest.countries == ("BR", "NG")
    assert manifest.earliest_date == date(2022, 1, 1)


def test_kaggle_import_is_idempotent_for_same_source_checksum(tmp_path: Path) -> None:
    source = KaggleSpotifyChartsSource(Path(__file__).parents[2] / "fixtures" / "kaggle")
    output = tmp_path / "normalized.parquet"
    first = source.import_to(output)
    second = source.import_to(output)
    assert first.rows_written == second.rows_written
    assert second.status.value == "IMPORTED"
