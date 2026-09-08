import polars as pl

from chart_observatory.analysis.rq import fit_rq2_content_country, fit_rq3_content_country_genre


def test_rq2_fits_country_effects_and_confidence_intervals() -> None:
    frame = pl.DataFrame(
        {
            "content": [0.1, 0.2, 0.8, 0.9, 0.3, 0.4],
            "country_code": ["BR", "BR", "US", "US", "BR", "US"],
        }
    )
    result = fit_rq2_content_country(frame)
    assert result.status == "FITTED"
    assert "Intercept" in result.coefficients
    assert "Intercept" in result.ci_low


def test_rq3_returns_insufficient_status_for_empty_semantic_corpus() -> None:
    result = fit_rq3_content_country_genre(pl.DataFrame())
    assert result.status == "INSUFFICIENT_DATA"
