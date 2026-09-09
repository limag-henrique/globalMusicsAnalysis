from datetime import UTC, date, datetime

import polars as pl

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
