from dataclasses import dataclass
from uuid import UUID

from scipy.stats import kendalltau, spearmanr  # type: ignore[import-untyped]


@dataclass(frozen=True)
class RankedItem:
    position: int
    canonical_track_id: UUID | None
    platform_item_id: str


@dataclass(frozen=True)
class OverlapResult:
    effective_top_n: int
    jaccard: float | None
    method: str
    shared_tracks: int
    left_charted_items: int
    right_charted_items: int
    left_unresolved: int
    right_unresolved: int


@dataclass(frozen=True)
class CorrelationResult:
    shared_tracks: int
    spearman: float | None
    kendall: float | None


def _effective_depth(left: list[RankedItem], right: list[RankedItem], requested: int) -> int:
    left_depth = max((item.position for item in left), default=0)
    right_depth = max((item.position for item in right), default=0)
    return min(requested, left_depth, right_depth)


def jaccard_overlap(
    left: list[RankedItem], right: list[RankedItem], requested_top_n: int
) -> OverlapResult:
    depth = _effective_depth(left, right, requested_top_n)
    left_items = [item for item in left if item.position <= depth]
    right_items = [item for item in right if item.position <= depth]
    left_tracks = {item.canonical_track_id for item in left_items if item.canonical_track_id}
    right_tracks = {item.canonical_track_id for item in right_items if item.canonical_track_id}
    union = left_tracks | right_tracks
    shared = left_tracks & right_tracks
    return OverlapResult(
        depth,
        len(shared) / len(union) if union else None,
        "RESOLVED_CANONICAL_TRACK_JACCARD",
        len(shared),
        len(left_items),
        len(right_items),
        sum(item.canonical_track_id is None for item in left_items),
        sum(item.canonical_track_id is None for item in right_items),
    )


def rank_correlations(left: list[RankedItem], right: list[RankedItem]) -> CorrelationResult:
    left_ranks = {
        item.canonical_track_id: item.position for item in left if item.canonical_track_id
    }
    right_ranks = {
        item.canonical_track_id: item.position for item in right if item.canonical_track_id
    }
    shared = sorted(left_ranks.keys() & right_ranks.keys(), key=str)
    if len(shared) < 2:
        return CorrelationResult(len(shared), None, None)
    left_values = [left_ranks[key] for key in shared]
    right_values = [right_ranks[key] for key in shared]
    spearman = spearmanr(left_values, right_values).statistic
    kendall = kendalltau(left_values, right_values).statistic
    return CorrelationResult(len(shared), float(spearman), float(kendall))
