import polars as pl

from chart_observatory.analysis.virality import fit_rq5_virality


def test_rq5_reports_insufficient_data_when_success_outcome_is_missing() -> None:
    result = fit_rq5_virality(pl.DataFrame({"content": [0.1], "virality": [1.0]}))

    assert result.status == "INSUFFICIENT_DATA"


def test_rq5_fits_content_virality_interaction() -> None:
    rows = [
        (country, genre, year, replicate)
        for year in (2020, 2021, 2022)
        for country in ("BR", "US", "FR")
        for genre in ("funk", "pop", "rap")
        for replicate in (0, 1)
    ]
    frame = pl.DataFrame(
        {
            "chart_success": [
                float(i + replicate + 1) for i, (_, _, _, replicate) in enumerate(rows)
            ],
            "content": [0.1 + (i % 5) * 0.1 for i in range(len(rows))],
            "virality": [float(replicate) for _, _, _, replicate in rows],
            "country_code": [country for country, _, _, _ in rows],
            "genre": [genre for _, genre, _, _ in rows],
            "year": [year for _, _, year, _ in rows],
        }
    )

    result = fit_rq5_virality(frame)

    assert result.status == "FITTED"
    assert "content:virality" in result.coefficients
