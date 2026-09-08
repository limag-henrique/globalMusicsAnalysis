import polars as pl

from chart_observatory.analysis.survival import fit_survival


def test_survival_reports_median_and_censoring() -> None:
    frame = pl.DataFrame({"duration": [1, 2, 3, 4, 5], "event": [1, 1, 0, 1, 0]})
    result = fit_survival(frame)
    assert result.status == "FITTED"
    assert result.median_survival is not None
