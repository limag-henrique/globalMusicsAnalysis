from datetime import date

import polars as pl

from chart_observatory.exports.article_analytics import (
    build_genre_distance_dataset,
    build_genre_variation_dataset,
    build_market_anxiety_dataset,
    build_persistence_dataset,
    write_article_datasets,
)


def _observations() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "provider": ["MGD"] * 4,
            "origin_platform": ["SPOTIFY"] * 4,
            "market_code": ["BR", "BR", "BR", "US"],
            "chart_family": ["TOP_200"] * 4,
            "period_start": [
                date(2020, 1, 1),
                date(2020, 1, 8),
                date(2020, 1, 15),
                date(2020, 1, 1),
            ],
            "period_end": [
                date(2020, 1, 7),
                date(2020, 1, 14),
                date(2020, 1, 21),
                date(2020, 1, 7),
            ],
            "rank": [1, 3, 5, 2],
            "canonical_track_id": ["track-a", "track-a", "track-a", "track-a"],
            "metric_value": [100.0, 80.0, 60.0, 90.0],
        }
    )


def test_persistence_counts_native_periods_and_calendar_span() -> None:
    result = build_persistence_dataset(_observations())

    assert result.to_dicts() == [
        {
            "provider": "MGD",
            "origin_platform": "SPOTIFY",
            "market_code": "BR",
            "chart_family": "TOP_200",
            "canonical_track_id": "track-a",
            "first_chart_date": date(2020, 1, 1),
            "last_chart_date": date(2020, 1, 15),
            "native_periods": 3,
            "calendar_span_days": 21,
            "peak_rank": 1,
            "mean_rank": 3.0,
            "unresolved_observations": 0,
        },
        {
            "provider": "MGD",
            "origin_platform": "SPOTIFY",
            "market_code": "US",
            "chart_family": "TOP_200",
            "canonical_track_id": "track-a",
            "first_chart_date": date(2020, 1, 1),
            "last_chart_date": date(2020, 1, 1),
            "native_periods": 1,
            "calendar_span_days": 7,
            "peak_rank": 2,
            "mean_rank": 2.0,
            "unresolved_observations": 0,
        },
    ]


def test_persistence_reports_unresolved_observations_in_the_chart_cell() -> None:
    observations = _observations().with_columns(
        pl.when(
            (pl.col("market_code") == "BR") & (pl.col("period_start") == date(2020, 1, 15))
        )
        .then(pl.lit(None, dtype=pl.String))
        .otherwise(pl.col("canonical_track_id"))
        .alias("canonical_track_id")
    )

    result = build_persistence_dataset(observations)

    assert result.filter(pl.col("market_code") == "BR")["unresolved_observations"].to_list() == [
        1
    ]


def test_genre_variation_reports_shares_by_country_and_year() -> None:
    claims = pl.DataFrame(
        {"canonical_track_id": ["track-a", "track-b"], "normalized_genre": ["funk", "pop"]}
    )
    observations = _observations().with_columns(
        pl.lit("track-b").alias("second_track")
    ).drop("second_track")
    result = build_genre_variation_dataset(observations, claims)

    assert result.filter(pl.col("market_code") == "BR")["genre_share"].to_list() == [1.0]
    assert result["genre"].to_list() == ["funk", "funk"]


def test_genre_distance_compares_country_pairs_with_same_year() -> None:
    result = build_genre_distance_dataset(
        {
            ("BR", 2020): {"funk": 3, "pop": 1},
            ("US", 2020): {"funk": 1, "pop": 3},
        }
    )

    assert result.to_dicts()[0]["left_market_code"] == "BR"
    assert result.to_dicts()[0]["right_market_code"] == "US"
    assert result.to_dicts()[0]["jensen_shannon"] > 0


def test_market_anxiety_reports_constant_change_between_periods() -> None:
    observations = pl.DataFrame(
        {
            "market_code": ["BR"] * 4,
            "period_start": [
                date(2020, 1, 1),
                date(2020, 1, 1),
                date(2020, 1, 8),
                date(2020, 1, 8),
            ],
            "canonical_track_id": ["a", "b", "b", "c"],
            "rank": [1, 2, 1, 2],
        }
    )

    result = build_market_anxiety_dataset(observations, top_n=2)

    assert result.to_dicts() == [
        {
            "market_code": "BR",
            "period_start": date(2020, 1, 8),
            "previous_period_start": date(2020, 1, 1),
            "top_n": 2,
            "new_entries": 1,
            "exits": 1,
            "retained_tracks": 1,
            "jaccard": 1 / 3,
            "turnover_rate": 0.6666666666666667,
            "mean_rank_displacement": 1.0,
        }
    ]


def test_write_article_datasets_materializes_core_outputs(tmp_path) -> None:
    claims = pl.DataFrame(
        {"canonical_track_id": ["track-a"], "normalized_genre": ["funk"]}
    )

    paths = write_article_datasets(_observations(), tmp_path, genre_claims=claims)

    assert set(paths) == {
        "persistence",
        "market_anxiety",
        "genre_variation",
        "genre_distance",
    }
    assert pl.read_parquet(paths["persistence"]).height == 2
    assert pl.read_parquet(paths["genre_variation"]).height == 2
