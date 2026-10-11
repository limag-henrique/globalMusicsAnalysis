from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.lyrics_batch import LyricClassificationBatchRun
from chart_observatory.lyrics.batch_service import CostBudgetExceeded
from chart_observatory.lyrics.brl_budget import BrlBudgetPolicy


def test_settled_invoice_anchor_counts_history_once_and_keeps_new_unknown_reservation():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    old_id = uuid4()
    policy = BrlBudgetPolicy(
        cap_brl=Decimal("3500"),
        ancillary_brl=Decimal("35"),
        retry_reserve_brl=Decimal("50"),
        billing_anchor_brl=Decimal("759"),
        covered_run_ids=frozenset({old_id}),
        billing_cutoff=datetime(2026, 10, 1, tzinfo=UTC),
        project_id="p",
        brl_per_ledger_usd=Decimal("12"),
        account_remaining_brl=Decimal("848"),
        account_baseline_run_ids=frozenset({old_id}),
    )
    with Session(engine) as session:
        old = LyricClassificationBatchRun(
            id=old_id,
            kind="main",
            state="failed",
            model_id="gemini-3.8-flash",
            taxonomy_version="t",
            prompt_version="p",
            thinking_level="LOW",
            project_id="p",
            location="global",
            bucket_name="b",
            request_count=100,
            summary_written=True,
            conservative_cost_usd=Decimal("500"),
            known_cost_usd=Decimal("60"),
            submitted_at=datetime(2026, 9, 26, tzinfo=UTC),
            terminal_at=datetime(2026, 9, 28, tzinfo=UTC),
        )
        session.add(old)
        session.commit()
        assert policy.remaining_ledger_usd(session) == Decimal("763") / Decimal("12")
        assert policy.guard(session, Decimal("60"), Decimal("99999")) == Decimal("1479")
        with pytest.raises(CostBudgetExceeded, match="credits"):
            policy.guard(session, Decimal("64"), Decimal("99999"))
        old.terminal_at = datetime(2026, 10, 2, tzinfo=UTC)
        session.commit()
        with pytest.raises(ValueError, match="settled"):
            policy.remaining_ledger_usd(session)
        old.terminal_at = datetime(2026, 9, 28, tzinfo=UTC)
        session.add(
            LyricClassificationBatchRun(
                kind="main",
                state="submitted",
                model_id="gemini-3.8-flash",
                taxonomy_version="t",
                prompt_version="p",
                thinking_level="LOW",
                project_id="p",
                location="global",
                bucket_name="b",
                request_count=1,
                provider_job_name="projects/p/locations/global/batchPredictionJobs/unknown",
            )
        )
        session.commit()
        with pytest.raises(ValueError, match="neither verified cost"):
            policy.remaining_ledger_usd(session)
