from datetime import date
from pathlib import Path

import polars as pl

from chart_observatory.sources.catalog import (
    CatalogFilters,
    filter_source_catalog,
    scan_source_catalog,
    write_source_catalog,
)


def _write_fixture(root: Path) -> tuple[Path, ...]:
    mgd = root / "mgd_observations.parquet"
    pl.DataFrame(
        {
            "provider": ["MGD", "MGD"],
            "origin_platform": ["SPOTIFY", "SPOTIFY"],
            "country_code": ["BR", "US"],
            "chart_name": ["Top 200", "Top 200"],
            "period_start": [date(2021, 1, 1), date(2022, 1, 1)],
            "period_end": [date(2021, 1, 1), date(2022, 1, 1)],
            "rank": [1, 2],
            "track_title": ["Brazilian song", "American song"],
            "artist": ["Artist BR", "Artist US"],
            "native_id": ["mgd-1", "mgd-2"],
            "metric_value": [100, None],
            "metric_type": ["STREAMS", None],
            "source_artifact": ["mgd.csv", "mgd.csv"],
            "source_row_number": [1, 2],
        }
    ).write_parquet(mgd)

    kaggle = root / "kaggle_spotify_observations.parquet"
    pl.DataFrame(
        {
            "provider": ["KAGGLE_DHRUVILDAVE"],
            "origin_platform": ["SPOTIFY"],
            "country_code": ["BRAZIL"],
            "chart_name": ["top200"],
            "period_start": [date(2021, 1, 1)],
            "period_end": [date(2021, 1, 1)],
            "rank": [1],
            "track_title": ["Brazilian song"],
            "artist": ["Artist BR"],
            "native_id": ["https://open.spotify.com/track/kaggle-1"],
            "metric_value": [200],
            "metric_type": ["STREAMS"],
            "source_artifact": ["charts.csv"],
            "source_row_number": [1],
        }
    ).write_parquet(kaggle)

    youtube = root / "youtube_video_most_popular.parquet"
    pl.DataFrame(
        {
            "provider": ["YOUTUBE_DATA_API"],
            "platform_code": ["YOUTUBE_VIDEO"],
            "chart_family": ["YOUTUBE_VIDEO_MOST_POPULAR"],
            "country_code": ["BR"],
            "chart_name": ["YouTube Video Most Popular"],
            "period_start": [date(2026, 9, 8)],
            "period_end": [date(2026, 9, 8)],
            "rank": [1],
            "native_id": ["video-1"],
            "item_kind": ["VIDEO"],
            "title": ["Popular video"],
            "metric_type": ["VIEWS"],
            "metric_value": [300.0],
            "view_count": [300],
            "semantic_equivalence": ["NOT_YOUTUBE_MUSIC_TOP_SONGS"],
            "raw_artifact_path": ["raw/youtube"],
        }
    ).write_parquet(youtube)
    return mgd, kaggle, youtube


def test_catalog_normalizes_sources_and_preserves_video_semantics(tmp_path: Path) -> None:
    frame = scan_source_catalog(_write_fixture(tmp_path)).collect()

    assert frame.height == 4
    assert set(frame["market_code"].to_list()) == {"BR", "US"}
    assert frame.filter(pl.col("item_kind") == "VIDEO")["semantic_equivalence"].to_list() == [
        "NOT_YOUTUBE_MUSIC_TOP_SONGS"
    ]
    assert frame.filter(pl.col("native_id") == "mgd-2")["metric_value"].to_list() == [None]


def test_catalog_filters_by_country_year_text_provider_and_limit(tmp_path: Path) -> None:
    frame = filter_source_catalog(
        _write_fixture(tmp_path),
        CatalogFilters(
            country_code="BR",
            year=2021,
            query="brazilian",
            provider="MGD",
            limit=1,
        ),
    )

    assert frame.height == 1
    assert frame["provider"].to_list() == ["MGD"]
    assert frame["period_start"].to_list() == [date(2021, 1, 1)]


def test_catalog_normalizes_chart_family_names_for_cross_source_filtering(tmp_path: Path) -> None:
    frame = filter_source_catalog(
        _write_fixture(tmp_path), CatalogFilters(chart_family="TOP_200", limit=10)
    )

    assert frame.height == 3
    assert set(frame["chart_family"].to_list()) == {"TOP_200"}


def test_catalog_materializes_the_same_normalized_schema(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    output = tmp_path / "source_catalog.parquet"

    write_source_catalog(paths, output)
    frame = pl.read_parquet(output)

    assert frame.height == 4
    assert frame.columns == list(scan_source_catalog(paths).collect_schema().names())
    assert frame["provider"].value_counts().sort("provider").to_dicts() == [
        {"provider": "KAGGLE_DHRUVILDAVE", "count": 1},
        {"provider": "MGD", "count": 2},
        {"provider": "YOUTUBE_DATA_API", "count": 1},
    ]


def test_catalog_can_query_its_materialized_output_without_reinterpreting_rows(
    tmp_path: Path,
) -> None:
    paths = _write_fixture(tmp_path)
    output = tmp_path / "source_catalog.parquet"
    write_source_catalog(paths, output)

    frame = filter_source_catalog(
        [output], CatalogFilters(country_code="BR", year=2021, limit=10)
    )

    assert frame.height == 2
    assert set(frame["item_kind"].to_list()) == {"TRACK"}
