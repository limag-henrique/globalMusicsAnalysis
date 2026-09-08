from datetime import UTC, date, datetime

import polars as pl

from chart_observatory.ui.classifications import ContentClassification
from chart_observatory.ui.data import (
    ObservationFilters,
    build_classification_profile,
    build_classification_profile_from_mgd_observations,
    filter_mgd_observations,
    load_manifest_summary,
    load_track_detail,
)
from chart_observatory.ui.taxonomy import TAXONOMY_VERSION, taxonomy_codes


def classification_for_test(
    track_id: str, scores: dict[str, int | None]
) -> ContentClassification:
    return ContentClassification(
        canonical_track_id=track_id,
        taxonomy_version=TAXONOMY_VERSION,
        scores=scores,
        reviewer="test",
        notes="",
        review_status="reviewed",
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_manifest_summary_reads_frozen_counts_and_hash(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"status":"FROZEN","manifest_sha256":"' + "a" * 64
        + '","date_start":"2017-01-01","date_end":"2022-03-13",'
        '"observations":{"rows":12},"total_cells":2,"eligible_cells":1,'
        '"analytical_datasets":[{"path":"track_master.parquet","rows":3}]}',
        encoding="utf-8",
    )

    summary = load_manifest_summary(manifest)

    assert summary.status == "FROZEN"
    assert summary.observations == 12
    assert summary.manifest_sha256 == "a" * 64


def test_observation_filter_respects_rank_market_and_query(tmp_path) -> None:
    path = tmp_path / "observations.parquet"
    pl.DataFrame(
        {
            "country_code": ["BR", "US", "BR"],
            "period_start": [date(2020, 1, 1)] * 3,
            "period_end": [date(2020, 1, 1)] * 3,
            "rank": [1, 1, 4],
            "track_title": ["Love Song", "Love Song", "Other"],
            "artist": ["Artist", "Artist", "Artist"],
            "native_id": ["track-1", "track-1", "track-2"],
            "metric_value": [100, 90, 80],
        }
    ).write_parquet(path)

    result = filter_mgd_observations(
        path,
        ObservationFilters(country_code="BR", max_rank=3, query="love", limit=10),
        annotated_track_ids={"track-1"},
    )

    assert result.select("native_id").to_series().to_list() == ["track-1"]
    assert result.select("classification_state").item() == "ANNOTATED"


def test_track_detail_aggregates_markets_ranks_survival_and_genres(tmp_path) -> None:
    observations = tmp_path / "observations.parquet"
    pl.DataFrame(
        {
            "country_code": ["BR", "US", "BR"],
            "period_start": [date(2020, 1, 1), date(2020, 1, 8), date(2020, 1, 15)],
            "rank": [4, 2, 8],
            "track_title": ["Song"] * 3,
            "artist": ["Artist"] * 3,
            "native_id": ["track-1"] * 3,
            "metric_value": [100, 90, 80],
        }
    ).write_parquet(observations)
    survival = tmp_path / "survival.parquet"
    pl.DataFrame({"track_id": ["track-1"], "duration": [3], "event": [1]}).write_parquet(survival)
    genres = tmp_path / "genres.parquet"
    pl.DataFrame(
        {"canonical_track_id": ["track-1"], "normalized_genre": ["pop"]}
    ).write_parquet(genres)

    detail = load_track_detail(observations, survival, genres, "track-1")

    assert detail is not None
    assert detail.appearances == 3
    assert detail.peak_rank == 2
    assert detail.mean_rank == 14 / 3
    assert detail.markets == ("BR", "US")
    assert detail.duration == 3
    assert detail.genres == ("pop",)


def test_classification_profile_excludes_null_but_counts_zero() -> None:
    observations = pl.DataFrame(
        {"country_code": ["BR", "BR"], "native_id": ["track-1", "track-2"]}
    )
    scores = {code: None for code in taxonomy_codes()}
    scores["violence"] = 0

    profile = build_classification_profile(
        observations, [classification_for_test("track-1", scores)]
    )
    violence = profile.filter(
        (pl.col("country_code") == "BR") & (pl.col("category") == "violence")
    )

    assert violence["classified_track_count"][0] == 1
    assert violence["prevalence"][0] == 0.0


def test_full_profile_is_independent_from_selector_catalog_and_retains_zero(tmp_path) -> None:
    observations_path = tmp_path / "observations.parquet"
    pl.DataFrame(
        {
            "country_code": ["BR", "BR", "US", "US"],
            "native_id": ["track-1", "track-1", "track-2", "track-3"],
        }
    ).write_parquet(observations_path)
    zero_scores = {code: None for code in taxonomy_codes()}
    zero_scores["violence"] = 0
    null_scores = {code: None for code in taxonomy_codes()}
    selector_catalog = pl.DataFrame({"country_code": ["BR"], "native_id": ["track-1"]})

    profile = build_classification_profile_from_mgd_observations(
        observations_path,
        [
            classification_for_test("track-1", zero_scores),
            classification_for_test("track-2", null_scores),
        ],
    )

    selector_profile = build_classification_profile(
        selector_catalog,
        [
            classification_for_test("track-1", zero_scores),
            classification_for_test("track-2", null_scores),
        ],
    )
    assert selector_profile.select("country_code").unique().to_series().to_list() == ["BR"]
    violence = profile.filter(pl.col("category") == "violence").sort("country_code")
    assert violence.select("country_code").to_series().to_list() == ["BR", "US"]
    assert violence.select("classified_track_count").to_series().to_list() == [1, 0]
    assert violence.select("prevalence").to_series().to_list() == [0.0, 0.0]
