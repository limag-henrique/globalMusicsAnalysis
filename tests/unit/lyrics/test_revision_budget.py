from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.lyrics_batch import LyricClassificationBatchRun
from chart_observatory.lyrics.batch_service import CostBudgetExceeded
from chart_observatory.lyrics.revision_budget import RevisionBudgetPolicy
from chart_observatory.lyrics.campaign_budget import CampaignBudget


def test_history_and_2026_share_110_main_budget_and_count_open_jobs(tmp_path):
    ledger = CampaignBudget(tmp_path / "budget.sqlite")
    ledger.attest(external_complete=True, provider_complete=True, evidence={"source": "test"})
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(LyricClassificationBatchRun(
            kind="main", state="submitted", model_id="gemini-3.8-flash",
            taxonomy_version="lyrics-classification-v1",
            prompt_version="lyrics-classification-prompt-v3", thinking_level="LOW",
            project_id="p", location="global", bucket_name="b", request_count=1,
            conservative_cost_usd=Decimal("100"), summary_written=False,
        ))
        session.commit()
        policy = RevisionBudgetPolicy(budget_path=ledger.path)
        assert policy(session, Decimal("10"), Decimal("300")) == Decimal("110")
        with pytest.raises(CostBudgetExceeded):
            policy(session, Decimal("10.01"), Decimal("300"))
        future = RevisionBudgetPolicy(phase="2026", budget_path=ledger.path)
        assert future(session, Decimal("10"), Decimal("300")) == Decimal("110")
        with pytest.raises(CostBudgetExceeded):
            future(session, Decimal("10.01"), Decimal("300"))


def test_paid_review_is_subtracted_before_new_generation(tmp_path):
    ledger = CampaignBudget(tmp_path / "budget.sqlite")
    ledger.attest(external_complete=True, provider_complete=True, evidence={"source": "test"})
    ledger.record_existing("human", "review", Decimal("25"), Decimal("25"),
                           settled=True, evidence={"invoice": "test"})
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        policy = RevisionBudgetPolicy(budget_path=ledger.path)
        assert policy(session, Decimal("10"), Decimal("180"), category="pilot") == Decimal("35")
        with pytest.raises(CostBudgetExceeded):
            policy(session, Decimal("11"), Decimal("180"), category="pilot")


def test_external_confirmation_is_not_assumed_from_an_empty_database(tmp_path):
    ledger = CampaignBudget(tmp_path / "budget.sqlite")
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        with pytest.raises(CostBudgetExceeded, match="reconcil"):
            RevisionBudgetPolicy(budget_path=ledger.path)(session, Decimal("1"), Decimal("180"))
