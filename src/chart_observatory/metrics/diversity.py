from collections.abc import Mapping
from dataclasses import dataclass
from math import log


@dataclass(frozen=True)
class DiversityMetrics:
    shannon_entropy: float
    simpson_diversity: float
    hhi: float


def genre_diversity(distribution: Mapping[str, float]) -> DiversityMetrics:
    total = sum(value for value in distribution.values() if value > 0)
    if total <= 0:
        return DiversityMetrics(0.0, 0.0, 0.0)
    proportions = [value / total for value in distribution.values() if value > 0]
    hhi = sum(value * value for value in proportions)
    return DiversityMetrics(
        shannon_entropy=-sum(value * log(value) for value in proportions),
        simpson_diversity=1.0 - hhi,
        hhi=hhi,
    )


def jensen_shannon(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    keys = set(left) | set(right)
    left_total = sum(max(value, 0.0) for value in left.values()) or 1.0
    right_total = sum(max(value, 0.0) for value in right.values()) or 1.0
    p = {key: max(left.get(key, 0.0), 0.0) / left_total for key in keys}
    q = {key: max(right.get(key, 0.0), 0.0) / right_total for key in keys}
    m = {key: (p[key] + q[key]) / 2 for key in keys}

    def kl(distribution: dict[str, float]) -> float:
        return sum(value * log(value / m[key]) for key, value in distribution.items() if value > 0)

    return (kl(p) + kl(q)) / 2
