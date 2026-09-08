from __future__ import annotations

import numpy as np
import polars as pl
import statsmodels.formula.api as smf  # type: ignore[import-untyped]

from chart_observatory.analysis.models import ModelResult


def _insufficient(name: str, formula: str, frame: pl.DataFrame, error: str) -> ModelResult:
    return ModelResult(name, formula, "INSUFFICIENT_DATA", frame.height, error=error)


def _fit_formula(
    frame: pl.DataFrame,
    *,
    name: str,
    formula: str,
    mixed_group: str | None = None,
) -> ModelResult:
    pandas_frame = frame.to_pandas()
    try:
        if pandas_frame.empty:
            return _insufficient(name, formula, frame, "empty analytical dataset")
        if mixed_group and mixed_group in pandas_frame.columns:
            fitted = smf.mixedlm(formula, pandas_frame, groups=pandas_frame[mixed_group]).fit(
                reml=False, method="lbfgs", disp=False
            )
            diagnostics = {"random_intercept": mixed_group, "aic": float(fitted.aic)}
        else:
            fitted = smf.ols(formula, data=pandas_frame).fit()
            diagnostics = {"aic": float(fitted.aic), "r_squared": float(fitted.rsquared)}
        confidence = fitted.conf_int()
        coefficients = {key: float(value) for key, value in fitted.params.items()}
        return ModelResult(
            name,
            formula,
            "FITTED",
            frame.height,
            coefficients,
            {key: float(value[0]) for key, value in confidence.iterrows()},
            {key: float(value[1]) for key, value in confidence.iterrows()},
            diagnostics,
        )
    except (ValueError, RuntimeError, np.linalg.LinAlgError) as error:
        return _insufficient(name, formula, frame, str(error))


def fit_rq2_content_country(frame: pl.DataFrame) -> ModelResult:
    formula = "content ~ C(country_code)"
    return _fit_formula(frame, name="RQ2_CONTENT_COUNTRY", formula=formula)


def fit_rq3_content_country_genre(frame: pl.DataFrame) -> ModelResult:
    formula = (
        "content ~ C(country_code) + C(genre) + year + C(language) + rank + "
        "C(country_code):C(genre)"
    )
    return _fit_formula(
        frame, name="RQ3_CONTENT_COUNTRY_GENRE", formula=formula, mixed_group="track_id"
    )


def fit_rq4_success(frame: pl.DataFrame, outcome: str) -> ModelResult:
    formula = f"{outcome} ~ content + C(country_code) + C(genre) + year + rank"
    return _fit_formula(
        frame, name=f"RQ4_CONTENT_{outcome.upper()}", formula=formula, mixed_group="track_id"
    )
