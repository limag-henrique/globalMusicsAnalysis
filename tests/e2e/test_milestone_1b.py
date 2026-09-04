from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from chart_observatory.adapters.youtube_data.mapper import map_most_popular_page
from chart_observatory.metrics.models import MetricObservation
from chart_observatory.metrics.presence import presence_summary
from chart_observatory.metrics.track_summary import summarize
from chart_observatory.ui.youtube_views import build_youtube_video_chart_view

FIXTURES = Path(__file__).parents[1] / "fixtures" / "youtube_data"
COUNTRIES = ("BR", "US", "GB", "FR", "DE", "ES", "PT", "IT", "SE")
NOW = datetime(2026, 9, 4, tzinfo=UTC)


def test_nine_country_video_views_use_explicit_non_equivalence_label() -> None:
    views = []
    for country in COUNTRIES:
        raw = (FIXTURES / f"most_popular_{country.lower()}.json").read_bytes()
        page = map_most_popular_page(raw, country, NOW)
        views.append(build_youtube_video_chart_view(country, "10", page.entries))
    assert {view.country_code for view in views} == set(COUNTRIES)
    assert all(view.chart_label == "YouTube Video Most Popular" for view in views)
    assert all(view.semantic_equivalence == "NOT_YOUTUBE_MUSIC_TOP_SONGS" for view in views)
    assert all(view.video_category_id == "10" for view in views)
    assert all(
        view.view_count_definition_version == "2025-03-31_SHORTS_STARTS_OR_REPLAYS"
        for view in views
    )


def test_sibling_videos_remain_two_charted_items_for_one_recording() -> None:
    recording_id = uuid4()
    summary = presence_summary(
        recording_id,
        [
            ("BR", "YOUTUBE_VIDEO", "br-video-a"),
            ("BR", "YOUTUBE_VIDEO", "br-video-b"),
        ],
    )
    assert summary.charted_items == 2
    assert summary.platforms == 1


def test_views_and_streams_remain_separate_in_milestone_1b() -> None:
    summary = summarize(
        [
            MetricObservation(NOW.date(), NOW.date(), 1, "DAILY", "VIEWS", Decimal("1200"), True),
            MetricObservation(NOW.date(), NOW.date(), 1, "DAILY", "STREAMS", Decimal("800"), True),
        ]
    )
    assert summary.view_sum == Decimal("1200")
    assert summary.stream_sum == Decimal("800")
    assert not hasattr(summary, "popularity_score")
