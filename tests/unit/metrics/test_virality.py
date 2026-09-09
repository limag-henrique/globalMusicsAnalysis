from datetime import date

import polars as pl

from chart_observatory.metrics.virality import (
    build_virality_features,
    link_virality_to_tracks,
)


def _videos() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "native_id": ["video-a", "video-b", "video-unresolved"],
            "market_code": ["BR", "US", "BR"],
            "period_start": [date(2026, 9, 8)] * 3,
            "rank": [1, 2, 3],
            "view_count": [1000, 800, None],
            "track_title": ["Song", "Song", "Unknown"],
        }
    )


def test_virality_links_one_track_to_multiple_videos_without_summing_views() -> None:
    links = pl.DataFrame(
        {
            "video_native_id": ["video-a", "video-b"],
            "canonical_track_id": ["track-a", "track-a"],
        }
    )
    linked = link_virality_to_tracks(
        pl.DataFrame({"canonical_track_id": ["track-a"]}), _videos(), links
    )
    features = build_virality_features(linked)

    assert features.to_dicts() == [
        {
            "canonical_track_id": "track-a",
            "linked_video_count": 2,
            "markets_with_video": 2,
            "best_video_rank": 1,
            "max_view_count": 1000,
            "median_view_count": 900.0,
        }
    ]


def test_virality_drops_unresolved_video_links() -> None:
    links = pl.DataFrame(
        {"video_native_id": ["video-unresolved"], "canonical_track_id": [None]}
    )

    linked = link_virality_to_tracks(pl.DataFrame(), _videos(), links)

    assert linked.height == 0
