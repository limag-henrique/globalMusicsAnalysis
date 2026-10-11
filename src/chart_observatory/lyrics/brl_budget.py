"""Evidence-backed BRL budget over the unchanged token-cost ledger."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.db.models.lyrics_batch import LyricClassificationBatchRun
from chart_observatory.lyrics.batch_service import CostBudgetExceeded, cumulative_cost_commitment


@dataclass(frozen=True)
class BrlBudgetPolicy:
    cap_brl: Decimal
    ancillary_brl: Decimal
    retry_reserve_brl: Decimal
    billing_anchor_brl: Decimal
    covered_run_ids: frozenset[UUID]
    billing_cutoff: datetime
    project_id: str
    brl_per_ledger_usd: Decimal
    account_remaining_brl: Decimal
    account_baseline_run_ids: frozenset[UUID]

    def _validate(self, session: Session) -> None:
        values = (
            self.cap_brl,
            self.ancillary_brl,
            self.retry_reserve_brl,
            self.billing_anchor_brl,
            self.brl_per_ledger_usd,
            self.account_remaining_brl,
        )
        if (
            any(not value.is_finite() or value < 0 for value in values)
            or self.brl_per_ledger_usd <= 0
            or self.cap_brl > Decimal("3500")
        ):
            raise ValueError("invalid BRL budget policy")
        unpriced = session.scalar(
            select(LyricClassificationBatchRun.id)
            .where(
                LyricClassificationBatchRun.provider_job_name.is_not(None),
                LyricClassificationBatchRun.conservative_cost_usd.is_(None),
                LyricClassificationBatchRun.known_cost_usd.is_(None),
                LyricClassificationBatchRun.id.not_in(self.covered_run_ids),
            )
            .limit(1)
        )
        if unpriced is not None:
            raise ValueError("submitted job has neither verified cost nor reservation")
        rows = list(
            session.scalars(
                select(LyricClassificationBatchRun).where(
                    LyricClassificationBatchRun.id.in_(self.covered_run_ids)
                )
            )
        )
        if len(rows) != len(self.covered_run_ids):
            raise ValueError("settled billing anchor references unknown runs")
        for run in rows:
            terminal = run.terminal_at
            if terminal and terminal.tzinfo is None:
                terminal = terminal.replace(tzinfo=UTC)
            if (
                run.project_id != self.project_id
                or not run.summary_written
                or not terminal
                or terminal >= self.billing_cutoff
                or run.state
                not in {"imported", "cleaned", "succeeded", "failed", "expired", "cancelled"}
            ):
                raise ValueError("run is not covered by the settled billing period")

    def commitments(
        self, session: Session, *, exclude_run_id: UUID | None = None
    ) -> tuple[Decimal, Decimal]:
        self._validate(session)
        global_usd = cumulative_cost_commitment(
            session, exclude_run_id=exclude_run_id, covered_run_ids=self.covered_run_ids
        )
        new_usd = cumulative_cost_commitment(
            session, exclude_run_id=exclude_run_id, covered_run_ids=self.account_baseline_run_ids
        )
        return (
            self.billing_anchor_brl + global_usd * self.brl_per_ledger_usd,
            new_usd * self.brl_per_ledger_usd,
        )

    def remaining_ledger_usd(self, session: Session) -> Decimal:
        total, account_new = self.commitments(session)
        reserve = self.ancillary_brl + self.retry_reserve_brl
        return (
            min(self.cap_brl - total - reserve, self.account_remaining_brl - account_new - reserve)
            / self.brl_per_ledger_usd
        )

    def guard(
        self,
        session: Session,
        new_conservative_cost: Decimal,
        _operator_cap: Decimal,
        *,
        exclude_run_id: UUID | None = None,
    ) -> Decimal:
        if not new_conservative_cost.is_finite() or new_conservative_cost <= 0:
            raise CostBudgetExceeded("positive finite reservation required")
        total, account_new = self.commitments(session, exclude_run_id=exclude_run_id)
        new_brl = new_conservative_cost * self.brl_per_ledger_usd
        reserve = self.ancillary_brl + self.retry_reserve_brl
        if total + new_brl + reserve > self.cap_brl:
            raise CostBudgetExceeded("cumulative BRL cost exceeds R$3500 policy")
        if account_new + new_brl + reserve > self.account_remaining_brl:
            raise CostBudgetExceeded("current account credits cannot cover the reservation")
        return total + new_brl
