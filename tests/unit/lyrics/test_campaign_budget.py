from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from chart_observatory.lyrics.campaign_budget import BudgetBlocked, CampaignBudget


def reconciled(path):
    budget = CampaignBudget(path)
    budget.attest(external_complete=True, provider_complete=True,
                  evidence={"source": "unit-test-no-provider"})
    return budget


def test_unreconciled_budget_does_not_offer_an_assumed_180_dollars(tmp_path):
    budget = CampaignBudget(tmp_path / "budget.sqlite")
    assert budget.snapshot()["spendable_usd"] == "0"
    with pytest.raises(BudgetBlocked, match="reconcil"):
        budget.reserve("pilot-one", "pilot", Decimal("1"), {"source": "test"})


def test_all_allocations_and_human_review_share_the_global_cap(tmp_path):
    budget = reconciled(tmp_path / "budget.sqlite")
    for category, amount in [("pilot", "10"), ("main", "110"), ("review", "25"),
                              ("services", "10"), ("contingency", "25")]:
        budget.reserve(category, category, Decimal(amount), {"source": "test"})
    assert budget.snapshot()["committed_usd"] == "180"
    with pytest.raises(BudgetBlocked):
        budget.reserve("extra", "review", Decimal("0.01"), {"kind": "human_review"})


def test_pending_commitments_are_not_added_again_and_settlement_releases_only_difference(tmp_path):
    budget = reconciled(tmp_path / "budget.sqlite")
    assert budget.reserve("job", "pilot", Decimal("8"), {"source": "test"}) is True
    assert budget.reserve("job", "pilot", Decimal("8"), {"source": "test"}) is False
    budget.settle("job", Decimal("3"), {"billing_reference": "test"})
    assert budget.snapshot()["committed_usd"] == "3"
    assert budget.snapshot()["realized_usd"] == "3"
    budget.reserve("pilot-two", "pilot", Decimal("7"), {"source": "test"})
    with pytest.raises(BudgetBlocked):
        budget.reserve("pilot-three", "pilot", Decimal("0.01"), {"source": "test"})


def test_concurrent_jobs_cannot_spend_the_same_balance(tmp_path):
    budget = reconciled(tmp_path / "budget.sqlite")
    def reserve(i):
        try:
            budget.reserve(str(i), "pilot", Decimal("6"), {"source": "test"})
            return True
        except BudgetBlocked:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(reserve, range(2))) == 1


def test_actual_overrun_is_recorded_and_blocks_further_spending(tmp_path):
    budget = reconciled(tmp_path / "budget.sqlite")
    budget.reserve("reviewer", "review", Decimal("20"), {"kind": "human_review"})
    budget.settle("reviewer", Decimal("26"), {"invoice": "test"})
    assert budget.snapshot()["realized_usd"] == "26"
    assert budget.snapshot()["within_limits"] is False
    with pytest.raises(BudgetBlocked):
        budget.reserve("later", "main", Decimal("1"), {"source": "test"})


def test_shard_reconciliation_keeps_realized_costs_monotonic(tmp_path):
    budget = reconciled(tmp_path / "budget.sqlite")
    budget.record_existing("parent", "main", Decimal("30"), Decimal("3"),
                           settled=False, evidence={"source": "test"})
    budget.sync_provider([
        dict(key="parent", category="main", committed=Decimal("10"), realized=Decimal("2"),
             settled=False, evidence={"source": "stale"}),
        dict(key="shard", category="main", committed=Decimal("20"), realized=None,
             settled=False, evidence={"source": "test"}),
    ], {"snapshot": "test"})
    assert budget.snapshot()["committed_usd"] == "30"
    assert budget.snapshot()["realized_usd"] == "3"


def test_unknown_cost_cannot_be_settled(tmp_path):
    budget = reconciled(tmp_path / "budget.sqlite")
    with pytest.raises(BudgetBlocked, match="unknown"):
        budget.record_existing("unknown", "review", Decimal("10"), None,
                               settled=True, evidence={"source": "test"})
