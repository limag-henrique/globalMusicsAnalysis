from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl
from lifelines import CoxPHFitter, KaplanMeierFitter  # type: ignore[import-untyped]


@dataclass(frozen=True)
class SurvivalResult:
    status: str
    n_observations: int
    median_survival: float | None = None
    survival_at: dict[str, float] = field(default_factory=dict)
    hazard_ratios: dict[str, float] = field(default_factory=dict)
    ci_low: dict[str, float] = field(default_factory=dict)
    ci_high: dict[str, float] = field(default_factory=dict)
    error: str | None = None


def fit_survival(frame: pl.DataFrame) -> SurvivalResult:
    required = {"duration", "event"}
    if not required.issubset(frame.columns) or frame.height == 0:
        return SurvivalResult(
            "INSUFFICIENT_DATA", frame.height, error="duration/event columns required"
        )
    try:
        pandas_frame = frame.to_pandas()
        km = KaplanMeierFitter().fit(pandas_frame["duration"], pandas_frame["event"])
        values = {
            f"survival_at_{int(time)}": float(km.survival_function_at_times(time).iloc[0])
            for time in sorted(
                {1, 7, 30, 90} & set(int(value) for value in pandas_frame["duration"])
            )
        }
        covariates = [
            column for column in frame.columns if column not in {"duration", "event", "track_id"}
        ]
        hazard_ratios: dict[str, float] = {}
        ci_low: dict[str, float] = {}
        ci_high: dict[str, float] = {}
        if covariates:
            cox_frame = pandas_frame[["duration", "event", *covariates]].copy()
            cox = CoxPHFitter().fit(cox_frame, duration_col="duration", event_col="event")
            hazard_ratios = {key: float(value) for key, value in cox.hazard_ratios_.items()}
            ci = cox.confidence_intervals_
            ci_low = {key: float(value) for key, value in ci.iloc[:, 0].items()}
            ci_high = {key: float(value) for key, value in ci.iloc[:, 1].items()}
        return SurvivalResult(
            "FITTED",
            frame.height,
            float(km.median_survival_time_),
            values,
            hazard_ratios,
            ci_low,
            ci_high,
        )
    except (ValueError, RuntimeError, KeyError) as error:
        return SurvivalResult("INSUFFICIENT_DATA", frame.height, error=str(error))
