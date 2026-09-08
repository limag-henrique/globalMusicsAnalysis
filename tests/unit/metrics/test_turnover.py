from chart_observatory.metrics.turnover import compute_turnover, median_survival


def test_turnover_separates_new_exits_retained_and_rank_displacement() -> None:
    result = compute_turnover({"a": 1, "b": 10, "c": 49}, {"a": 3, "b": 8, "d": 4})
    assert result.new_entries == 1
    assert result.exits == 1
    assert result.retained_tracks == 2
    assert result.jaccard == 2 / 4
    assert result.turnover_rate == 0.5
    assert result.mean_rank_displacement == 2.0


def test_median_survival_is_missing_for_empty_input() -> None:
    assert median_survival({}) is None
    assert median_survival({"a": 2, "b": 4, "c": 8}) == 4.0
