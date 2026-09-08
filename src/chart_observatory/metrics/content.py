from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from math import sqrt

import polars as pl


@dataclass(frozen=True)
class ContentObservation:
    country_code: str
    category: str
    track_id: str
    rank: int
    value: float = 1.0
    weight: float | None = None


def wilson_interval(
    successes: int, trials: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    if trials <= 0:
        return (float("nan"), float("nan"))
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    margin = z * sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def category_prevalence(rows: Iterable[ContentObservation]) -> pl.DataFrame:
    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    countries: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        grouped[(row.country_code.upper(), row.category)].add(row.track_id)
        countries[row.country_code.upper()].add(row.track_id)
    output: list[dict[str, object]] = []
    for (country, category), tracks in sorted(grouped.items()):
        denominator = len(countries[country])
        estimate = len(tracks) / denominator if denominator else None
        low, high = wilson_interval(len(tracks), denominator)
        output.append(
            {
                "country_code": country,
                "category": category,
                "tracks_with_category": len(tracks),
                "track_denominator": denominator,
                "prevalence": estimate,
                "ci_low": low,
                "ci_high": high,
            }
        )
    return (
        pl.DataFrame(output)
        if output
        else pl.DataFrame(
            schema={
                "country_code": pl.String,
                "category": pl.String,
                "tracks_with_category": pl.Int64,
                "track_denominator": pl.Int64,
                "prevalence": pl.Float64,
                "ci_low": pl.Float64,
                "ci_high": pl.Float64,
            }
        )
    )


def category_exposure(rows: Iterable[ContentObservation]) -> pl.DataFrame:
    grouped: dict[tuple[str, str], float] = defaultdict(float)
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        weight = row.weight if row.weight is not None else 1.0
        grouped[(row.country_code.upper(), row.category)] += weight
        totals[row.country_code.upper()] += weight
    output: list[dict[str, object]] = []
    for (country, category), weighted_count in sorted(grouped.items()):
        denominator = totals[country]
        output.append(
            {
                "country_code": country,
                "category": category,
                "weighted_exposure": weighted_count,
                "observation_weight_denominator": denominator,
                "exposure": weighted_count / denominator if denominator else None,
            }
        )
    return (
        pl.DataFrame(output)
        if output
        else pl.DataFrame(
            schema={
                "country_code": pl.String,
                "category": pl.String,
                "weighted_exposure": pl.Float64,
                "observation_weight_denominator": pl.Float64,
                "exposure": pl.Float64,
            }
        )
    )
