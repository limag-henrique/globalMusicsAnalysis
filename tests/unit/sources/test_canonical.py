from datetime import date

from chart_observatory.sources.canonical import canonicalize
from chart_observatory.sources.models import SourceObservation


def observation(provider: str, title: str) -> SourceObservation:
    return SourceObservation(
        provider=provider,
        origin_platform="SPOTIFY",
        country_code="BR",
        chart_name="Top 200",
        period_start=date(2022, 1, 1),
        period_end=date(2022, 1, 1),
        rank=1,
        track_title=title,
        artist="Artist",
    )


def test_canonicalization_keeps_duplicates_but_selects_precedence() -> None:
    entries = canonicalize([observation("KAGGLE_DHRUVILDAVE", "Song"), observation("MGD", "Song")])
    assert len(entries) == 1
    assert len(entries[0].observations) == 2
    assert entries[0].preferred_source == "MGD"
    assert entries[0].status == "CANONICAL"


def test_disagreement_is_explicit_source_conflict() -> None:
    entries = canonicalize([observation("MGD", "Song A"), observation("CHARTMETRIC", "Song B")])
    assert entries[0].selected_observation is None
    assert entries[0].status == "SOURCE_CONFLICT"
