import pytest

from chart_observatory.ingestion.rank_uncertainty import audit_rank_bounds


def rows():
    return [
        dict(period_end=day, source_rank=rank, native_id=key, metric_value=value)
        for day, rank, key, value in [
            (1, 1, "A", 100),
            (1, 2, "B", 90),
            (2, 1, "A", 100),
            (2, 2, "C", 80),
        ]
    ]


def test_full_calendar_does_not_prove_censored_annual_second_place():
    result = audit_rank_bounds(rows(), expected_periods={1, 2}, depth=2, quota=2)
    first, second = result["rankings"]
    assert first["annual_streams_lower"] == first["annual_streams_upper"] == 200
    assert first["exact_position_guaranteed"]
    assert second["observed_rank"] == 2 and second["annual_streams_upper"] == 170
    assert not second["exact_position_guaranteed"]
    assert second["worst_possible_rank"] is None


def test_incomplete_chart_or_calendar_cannot_generate_rank_certificates():
    with pytest.raises(ValueError, match="complete expected calendar"):
        audit_rank_bounds(rows(), expected_periods={1, 2, 3}, depth=2, quota=2)
    with pytest.raises(ValueError, match="every published"):
        audit_rank_bounds(rows()[:-1], expected_periods={1, 2}, depth=2, quota=2)
