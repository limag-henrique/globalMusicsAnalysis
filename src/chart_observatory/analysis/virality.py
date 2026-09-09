from __future__ import annotations

import polars as pl

from chart_observatory.analysis.models import ModelResult
from chart_observatory.analysis.rq import _fit_formula


def fit_rq5_virality(frame: pl.DataFrame) -> ModelResult:
    """Fit the content-by-virality interaction against chart success."""
    formula = "chart_success ~ content * virality + C(country_code) + C(genre) + year"
    required = {"chart_success", "content", "virality", "country_code", "genre", "year"}
    missing = required.difference(frame.columns)
    if missing:
        return ModelResult(
            "RQ5_VIRALITY",
            formula,
            "INSUFFICIENT_DATA",
            frame.height,
            error=f"missing columns: {sorted(missing)}",
        )
    return _fit_formula(frame, name="RQ5_VIRALITY", formula=formula, mixed_group="track_id")
