from datetime import UTC, date, datetime

import polars as pl
import pytest

from chart_observatory.metrics.content_profile import (
    build_content_prevalence_dataset,
    classification_observations,
)
from chart_observatory.ui.classifications import ContentClassification
from chart_observatory.ui.taxonomy import TAXONOMY_VERSION, taxonomy_codes


def _classification(track_id: str, violence: int | None) -> ContentClassification:
    scores = {code: None for code in taxonomy_codes()}
    scores["violence"] = violence
    return ContentClassification(
        track_id,
        TAXONOMY_VERSION,
        scores,
        "researcher",
        "fixture",
        "REVIEWED",
        datetime(2026, 9, 8, tzinfo=UTC),
    )


def test_content_profile_preserves_zero_and_excludes_unannotated_from_denominator() -> None:
    observations = pl.DataFrame(
        {
            "canonical_track_id": ["track-a", "track-b", "track-c"],
            "market_code": ["BR", "BR", "BR"],
            "period_start": [date(2020, 1, 1)] * 3,
            "rank": [1, 2, 3],
        }
    )
    rows = classification_observations(
        observations,
        [
            _classification("track-a", 0),
            _classification("track-b", 3),
            _classification("track-c", None),
        ],
    )
    prevalence = build_content_prevalence_dataset(rows)

    violence = prevalence.filter(pl.col("category") == "violence").row(0, named=True)
    assert violence["annotated_track_denominator"] == 2
    assert violence["tracks_with_category"] == 1
    assert violence["prevalence"] == 0.5


def test_content_prevalence_keeps_platforms_separate_and_reports_missing_tracks() -> None:
    observations = pl.DataFrame(
        {
            "canonical_track_id": ["track-a", "track-b", "track-c"],
            "market_code": ["BR"] * 3,
            "period_start": [date(2020, 1, 1)] * 3,
            "rank": [1, 1, 2],
            "provider": ["MGD", "VIDEO", "MGD"],
            "origin_platform": ["SPOTIFY", "YOUTUBE", "SPOTIFY"],
            "chart_family": ["TOP_200", "MOST_POPULAR", "TOP_200"],
        }
    )
    rows = classification_observations(
        observations, [_classification("track-a", 0), _classification("track-b", 3)]
    )
    result = build_content_prevalence_dataset(rows).filter(pl.col("category") == "violence")
    assert result.height == 2
    spotify = result.filter(pl.col("origin_platform") == "SPOTIFY").row(0, named=True)
    assert spotify["observed_track_denominator"] == 2
    assert spotify["annotated_track_denominator"] == 1
    assert spotify["missing_tracks"] == 1
    assert spotify["annotation_coverage"] == 0.5
    assert spotify["prevalence"] == 0.0


def test_unannotated_chart_tracks_are_missing_instead_of_zero() -> None:
    observations = pl.DataFrame(
        {
            "canonical_track_id": ["track-a"],
            "market_code": ["BR"],
            "period_start": [date(2020, 1, 1)],
            "rank": [1],
        }
    )
    result = build_content_prevalence_dataset(classification_observations(observations, []))
    assert result.height == len(taxonomy_codes())
    assert result["prevalence"].null_count() == result.height
    assert result["annotation_coverage"].to_list() == [0.0] * result.height


def test_conflicting_track_annotations_require_explicit_selection() -> None:
    observations = pl.DataFrame(
        {
            "canonical_track_id": ["track-a"],
            "market_code": ["BR"],
            "period_start": [date(2020, 1, 1)],
            "rank": [1],
        }
    )
    with pytest.raises(ValueError, match="multiple classifications"):
        classification_observations(
            observations, [_classification("track-a", 0), _classification("track-a", 3)]
        )
