from uuid import uuid4

from chart_observatory.metrics.presence import presence_summary


def test_presence_counts_countries_platforms_and_native_items_separately() -> None:
    result = presence_summary(
        uuid4(),
        [
            ("BR", "YOUTUBE_VIDEO", "video-a"),
            ("BR", "YOUTUBE_VIDEO", "video-b"),
            ("US", "SPOTIFY", "track-a"),
        ],
    )
    assert (result.countries, result.platforms, result.charted_items) == (2, 2, 3)
