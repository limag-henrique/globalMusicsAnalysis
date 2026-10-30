from datetime import date

import polars as pl
import pytest

from chart_observatory.lyrics.annual_cohort import select_annual_top80


def test_top80_is_per_market_year_stream_ordered_and_duplicate_days_do_not_inflate():
    rows = [dict(provider="A", market_code=market, year=year,
                 chart_track_id=str(i), period_start=date(year, 1, 1),
                 metric_value=1000-i, track_title=f"Song {i}", artist="Artist")
            for market, year in [("BR", 2024), ("BR", 2025), ("AR", 2025)]
            for i in range(85)]
    rows.append(dict(rows[-1]))
    cohort = select_annual_top80(pl.DataFrame(rows).lazy())
    assert cohort.height == 240
    assert cohort.group_by("market_code", "year").len()["len"].to_list() == [80]*3
    br = cohort.filter((pl.col("market_code") == "BR") & (pl.col("year") == 2025))
    assert br["chart_track_id"].to_list() == [str(i) for i in range(80)]
    assert br["annual_rank"].to_list() == list(range(1, 81))


def test_one_provider_per_year_uses_best_day_coverage_without_adding_mirrors():
    rows = [dict(provider=p, market_code="BR", year=2025, chart_track_id="one",
                 period_start=date(2025, 1, day), metric_value=value,
                 track_title="One", artist="Artist")
            for p, day, value in [("A", 1, 1000), ("B", 1, 10), ("B", 2, 20)]]
    result = select_annual_top80(pl.DataFrame(rows).lazy())
    assert result["provider"].to_list() == ["B"]
    assert result["annual_streams"].to_list() == [30]
    assert result["observed_days"].to_list() == [2]


def test_conflicting_daily_stream_values_fail_instead_of_inflating_popularity():
    rows = [dict(provider="A", market_code="BR", year=2025, chart_track_id="one",
                 period_start=date(2025, 1, 1), metric_value=value,
                 track_title="One", artist="Artist") for value in [10, 20]]
    with pytest.raises(ValueError, match="conflicting daily"):
        select_annual_top80(pl.DataFrame(rows).lazy())


def test_equal_streams_have_repeatable_native_id_tiebreaker():
    rows = [dict(provider="A", market_code="BR", year=2025, chart_track_id=native,
                 period_start=date(2025, 1, 1), metric_value=10,
                 track_title="Song", artist="Artist") for native in ["b", "a"]]
    result = select_annual_top80(pl.DataFrame(rows).lazy())
    assert result["chart_track_id"].to_list() == ["a", "b"]
