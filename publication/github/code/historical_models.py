"""Exploratory within-country associations; never regress on raw cross-country indices."""

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import polars as pl
import statsmodels.formula.api as smf  # type: ignore[import-untyped]
from statsmodels.stats.multitest import multipletests  # type: ignore[import-untyped]


def export_historical_models(panel: pl.DataFrame, output: Path) -> dict[str, int]:
    """Export fixed-effects sensitivity results and exact samples, including failures."""
    outcomes = [c for c in panel.columns if c.endswith("_pct")]
    anchor = panel.filter((pl.col("term") == "porn") & (pl.col("language") == "en"))
    canonical = anchor.group_by("market_code").agg(pl.col("comparison_group").min())
    anchor = anchor.join(canonical, on=["market_code", "comparison_group"], how="semi")
    controls = ["gdp_pc_ppp_constant", "internet_users"]
    if anchor.select(pl.struct("market_code", "year").n_unique()).item() != anchor.height:
        raise ValueError("Ambiguous anchor country/year")
    results: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for outcome in outcomes:
        for label, min_coverage, adjusted in [
            ("baseline", 0.5, False),
            ("coverage70", 0.7, False),
            ("adjusted", 0.5, True),
        ]:
            model_id = f"{outcome}__{label}"
            eligible = []
            for r in anchor.to_dicts():
                reasons = []
                if r["year"] > 2021 or r["partial_year"]:
                    reasons.append("partial_or_recent_year")
                if r["mean_index"] is None:
                    reasons.append("censored_or_missing_index")
                if r["temporal_coverage"] < 0.8:
                    reasons.append("temporal_coverage_below80")
                if r["classified_tracks"] < 300 or r["coverage"] < min_coverage:
                    reasons.append("musical_coverage")
                if r[outcome] is None:
                    reasons.append("missing_music_outcome")
                if adjusted and any(r.get(c) is None for c in controls):
                    reasons.append("missing_controls")
                elif adjusted and r[controls[0]] <= 0:
                    reasons.append("nonpositive_income")
                if reasons:
                    exclusions.append(
                        {
                            "model_id": model_id,
                            "market_code": r["market_code"],
                            "year": r["year"],
                            "reason": ";".join(reasons),
                        }
                    )
                else:
                    eligible.append(r)
            by_country: dict[str, list[dict[str, Any]]] = {}
            for r in eligible:
                by_country.setdefault(r["market_code"], []).append(r)
            standardized = []
            for country, rows in by_country.items():
                values = np.array([r["mean_index"] for r in rows], dtype=float)
                sd = float(values.std(ddof=0))
                if len(rows) < 4 or sd == 0:
                    exclusions.extend(
                        {
                            "model_id": model_id,
                            "market_code": country,
                            "year": r["year"],
                            "reason": "short_or_constant_series",
                        }
                        for r in rows
                    )
                    continue
                for r in rows:
                    s = {
                        "model_id": model_id,
                        "market_code": country,
                        "year": r["year"],
                        "comparison_group": r["comparison_group"],
                        "trends_z": (r["mean_index"] - float(values.mean())) / sd,
                        "music_value": r[outcome],
                        "classified_tracks": r["classified_tracks"],
                        "coverage": r["coverage"],
                        "temporal_coverage": r["temporal_coverage"],
                        "log_income": math.log(r[controls[0]]) if adjusted else None,
                        "internet_users": r[controls[1]] if adjusted else None,
                    }
                    standardized.append(s)
            samples.extend(standardized)
            countries = len({r["market_code"] for r in standardized})
            result: dict[str, Any] = {
                "model_id": model_id,
                "outcome": outcome,
                "specification": label,
                "n_country_years": len(standardized),
                "n_countries": countries,
                "coefficient": None,
                "standard_error": None,
                "ci_lower": None,
                "ci_upper": None,
                "p_value": None,
                "q_value_bh": None,
                "status": "insufficient_countries",
                "cross_country_raw_levels": False,
                "unit": "music percentage points per within-country Trends SD",
            }
            if countries >= 20:
                df = pd.DataFrame(standardized)
                formula = "music_value ~ trends_z + C(market_code) + C(year)"
                if adjusted:
                    formula += " + log_income + internet_users"
                model = smf.ols(formula, data=df)
                matrix = model.exog
                rank = np.linalg.matrix_rank(matrix)
                if rank < matrix.shape[1] or len(df) - rank < countries:
                    result["status"] = "rank_deficient_or_low_residual_df"
                elif df["music_value"].nunique() < 2:
                    result["status"] = "constant_outcome"
                else:
                    fit = model.fit(
                        cov_type="cluster", cov_kwds={"groups": df["market_code"]}, use_t=True
                    )
                    low, high = fit.conf_int().loc["trends_z"]
                    fitted_values = [
                        fit.params["trends_z"],
                        fit.bse["trends_z"],
                        low,
                        high,
                        fit.pvalues["trends_z"],
                    ]
                    if all(math.isfinite(float(v)) for v in fitted_values):
                        for key, value in zip(
                            ["coefficient", "standard_error", "ci_lower", "ci_upper", "p_value"],
                            fitted_values,
                            strict=True,
                        ):
                            result[key] = float(value)
                        result["status"] = "exploratory_country_year_fixed_effects"
                    else:
                        result["status"] = "nonfinite_fit"
            results.append(result)
    valid = [r for r in results if r["p_value"] is not None]
    if valid:
        q_values = multipletests([r["p_value"] for r in valid], method="fdr_bh")[1]
        for r, q in zip(valid, q_values, strict=True):
            r["q_value_bh"] = float(q)
    output.mkdir(parents=True, exist_ok=True)
    exports: list[tuple[str, list[dict[str, Any]], dict[str, Any]]] = [
        ("historical-associations", results, {"model_id": pl.String}),
        (
            "model-samples",
            samples,
            {
                "model_id": pl.String,
                "market_code": pl.String,
                "year": pl.Int64,
                "comparison_group": pl.String,
            },
        ),
        (
            "model-exclusions",
            exclusions,
            {
                "model_id": pl.String,
                "market_code": pl.String,
                "year": pl.Int64,
                "reason": pl.String,
            },
        ),
    ]
    for name, records, empty_fields in exports:
        frame = (
            pl.from_dicts(records, infer_schema_length=None)
            if records
            else pl.DataFrame(schema=empty_fields)
        )
        frame.write_csv(output / f"{name}.csv")
        frame.write_parquet(output / f"{name}.parquet")
    return {
        "model_specs": len(results),
        "estimated_models": len(valid),
        "sample_rows": len(samples),
        "exclusion_rows": len(exclusions),
    }
