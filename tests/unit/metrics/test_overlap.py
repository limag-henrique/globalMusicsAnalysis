from uuid import uuid4

from chart_observatory.metrics.overlap import RankedItem, jaccard_overlap, rank_correlations


def test_overlap_uses_common_observed_depth_and_reports_items() -> None:
    shared, only_a, only_b = uuid4(), uuid4(), uuid4()
    left = [RankedItem(1, shared, "video-a"), RankedItem(2, only_a, "video-b")]
    right = [
        RankedItem(1, shared, "song-a"),
        RankedItem(2, only_b, "song-b"),
        RankedItem(3, uuid4(), "song-c"),
    ]
    result = jaccard_overlap(left, right, requested_top_n=200)
    assert result.effective_top_n == 2
    assert result.jaccard == 1 / 3
    assert result.method == "RESOLVED_CANONICAL_TRACK_JACCARD"
    assert (result.left_charted_items, result.right_charted_items) == (2, 2)


def test_correlations_are_null_when_shared_sample_is_insufficient() -> None:
    shared = uuid4()
    result = rank_correlations([RankedItem(1, shared, "a")], [RankedItem(2, shared, "b")])
    assert result.shared_tracks == 1
    assert result.spearman is None
    assert result.kendall is None
