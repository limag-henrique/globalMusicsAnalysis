import polars as pl

from chart_observatory.ui.article_analytics import market_anxiety_summary


def test_market_anxiety_summary_ranks_markets_by_average_turnover() -> None:
    frame = pl.DataFrame(
        {
            "market_code": ["BR", "BR", "US"],
            "turnover_rate": [0.8, 0.6, 0.2],
            "mean_rank_displacement": [4.0, 2.0, 1.0],
        }
    )

    result = market_anxiety_summary(frame)

    assert result.to_dicts() == [
        {
            "market_code": "BR",
            "mean_turnover_rate": 0.7,
            "mean_rank_displacement": 3.0,
            "periods": 2,
        },
        {
            "market_code": "US",
            "mean_turnover_rate": 0.2,
            "mean_rank_displacement": 1.0,
            "periods": 1,
        },
    ]
