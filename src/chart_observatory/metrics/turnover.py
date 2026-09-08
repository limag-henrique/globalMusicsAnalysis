from collections.abc import Mapping
from dataclasses import dataclass
from statistics import mean, median
from uuid import UUID


@dataclass(frozen=True)
class TurnoverMetrics:
    top_n: int
    new_entries: int
    exits: int
    retained_tracks: int
    jaccard: float | None
    turnover_rate: float | None
    mean_rank_displacement: float | None
    median_survival_time: float | None = None


def compute_turnover(
    period_a: Mapping[UUID | str, int],
    period_b: Mapping[UUID | str, int],
    *,
    top_n: int = 50,
) -> TurnoverMetrics:
    """Compare two adjacent chart periods using resolved canonical tracks."""
    left = {track: rank for track, rank in period_a.items() if 0 < rank <= top_n}
    right = {track: rank for track, rank in period_b.items() if 0 < rank <= top_n}
    left_tracks = set(left)
    right_tracks = set(right)
    retained = left_tracks & right_tracks
    union = left_tracks | right_tracks
    jaccard = len(retained) / len(union) if union else None
    return TurnoverMetrics(
        top_n=top_n,
        new_entries=len(right_tracks - left_tracks),
        exits=len(left_tracks - right_tracks),
        retained_tracks=len(retained),
        jaccard=jaccard,
        turnover_rate=1.0 - jaccard if jaccard is not None else None,
        mean_rank_displacement=(
            mean(abs(right[track] - left[track]) for track in retained) if retained else None
        ),
    )


def median_survival(periods_present: Mapping[UUID | str, int]) -> float | None:
    """Return the median number of observed periods per resolved track."""
    if not periods_present:
        return None
    return float(median(periods_present.values()))
