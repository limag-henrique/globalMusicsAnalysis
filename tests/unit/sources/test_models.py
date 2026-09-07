from datetime import date
from decimal import Decimal

from chart_observatory.sources.models import SourceObservation, SourceStatus


def observation(**changes: object) -> SourceObservation:
    values: dict[str, object] = {
        "provider": "MGD",
        "origin_platform": "SPOTIFY",
        "country_code": "BR",
        "chart_name": "Top 200",
        "period_start": date(2022, 1, 1),
        "period_end": date(2022, 1, 1),
        "rank": 1,
        "track_title": "Track",
        "artist": "Artist",
        "metric_value": Decimal("10"),
    }
    values.update(changes)
    return SourceObservation(**values)


def test_provider_and_origin_platform_are_independent() -> None:
    row = observation(provider="CHARTMETRIC", origin_platform="SPOTIFY")
    assert row.provider != row.origin_platform
    assert row.observation_key()[0:2] == ("CHARTMETRIC", "SPOTIFY")


def test_missing_metric_remains_null() -> None:
    assert observation(metric_value=None).metric_value is None


def test_equivalence_key_keeps_rank_conflicts_distinct() -> None:
    assert (
        observation(rank=1).canonical_equivalence_key()
        != observation(rank=2).canonical_equivalence_key()
    )


def test_status_values_include_review_and_conflict_states() -> None:
    assert SourceStatus.NEEDS_REVIEW.value == "NEEDS_REVIEW"
    assert SourceStatus.SOURCE_CONFLICT.value == "SOURCE_CONFLICT"
