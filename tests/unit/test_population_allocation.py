from decimal import Decimal

import pytest

from chart_observatory.population_allocation import allocate, weight


def test_larger_population_receives_more_and_total_is_exact():
    quotas = allocate({"BR": weight(200_000_000, 1, 0), "SM": weight(30_000, 1, 0)}, 100)
    assert quotas["BR"] > quotas["SM"] >= 1
    assert sum(quotas.values()) == 100


def test_capping_redistributes_without_exceeding_budget():
    quotas = allocate({"a": Decimal(1000), "b": Decimal(1), "c": Decimal(1)}, 100, maximum=40)
    assert quotas == dict(a=40, b=30, c=30)


def test_deterministic_rounding():
    assert allocate(dict(b=1, a=1, c=1), 5) == dict(a=2, b=2, c=1)


def test_all_years_share_one_budget():
    years = range(2018, 2027)
    allocations = [
        allocate(dict(a=9, b=3, c=1), 150_000 // 9 + (i < 150_000 % 9), maximum=20_000)
        for i, _ in enumerate(years)
    ]
    assert sum(sum(q.values()) for q in allocations) == 150_000


def test_impossible_capacity_is_rejected():
    with pytest.raises(ValueError):
        allocate(dict(a=1, b=2), 1001)
