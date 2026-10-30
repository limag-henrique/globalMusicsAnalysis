"""US$180 revision ceiling shared by 2017–2026, review and auxiliary costs."""

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.db.models.corpus import LyricClassificationSnapshot
from chart_observatory.db.models.lyrics_batch import LyricClassificationBatchRun
from chart_observatory.lyrics import campaign_budget

REVISION_PROMPT_VERSION = "lyrics-classification-prompt-v3"
REVISION_PROMPT_VERSIONS = frozenset(
    {REVISION_PROMPT_VERSION, "lyrics-classification-prompt-v4-draft1"}
)


def category_for_kind(kind):
    return {
        "canary": "pilot",
        "pilot": "pilot",
        "main": "main",
        "error_retry": "contingency",
        "review": "review",
    }.get(str(kind), "main")


@dataclass(frozen=True)
class RevisionBudgetPolicy:
    phase: Literal["historical", "2026"] = "historical"
    budget_path: Path | None = None

    def reconcile(self, session):
        return self._apply(
            session, Decimal(0), campaign_budget.TOTAL_LIMIT, reconciliation_only=True
        )

    def __call__(
        self,
        session: Session,
        new_conservative_cost: Decimal,
        operator_cap: Decimal,
        *,
        exclude_run_id: UUID | None = None,
        category: str = "main",
    ) -> Decimal:
        return self._apply(
            session,
            new_conservative_cost,
            operator_cap,
            exclude_run_id=exclude_run_id,
            category=category,
        )

    def _apply(
        self,
        session,
        new_conservative_cost,
        operator_cap,
        *,
        exclude_run_id=None,
        category="main",
        reconciliation_only=False,
    ):
        from chart_observatory.lyrics.batch_service import (
            CostBudgetExceeded,
            cumulative_cost_commitment,
        )

        if self.phase not in {"historical", "2026"}:
            raise ValueError("invalid revision phase")
        if not reconciliation_only and any(
            not value.is_finite() or value <= 0 for value in (new_conservative_cost, operator_cap)
        ):
            raise CostBudgetExceeded("finite positive cost and operator cap are required")
        ledger = campaign_budget.CampaignBudget(
            self.budget_path or campaign_budget.DEFAULT_BUDGET_PATH
        )
        runs = list(session.scalars(select(LyricClassificationBatchRun)))
        current = next((r for r in runs if r.id == exclude_run_id), None)
        if current is not None:
            category = category_for_kind(current.kind)
        evidence, entries = [], []
        try:
            for run in runs:
                if run.prompt_version not in REVISION_PROMPT_VERSIONS:
                    continue  # Earlier campaigns are historical, not charged twice.
                if run.conservative_cost_usd is None and run.known_cost_usd is None:
                    if run.provider_job_name:
                        ledger.attest(
                            provider_complete=False, evidence={"unpriced_job": str(run.id)}
                        )
                        raise campaign_budget.BudgetBlocked("revision job has no cost bound")
                    continue  # Preparation has not created any provider job yet.
                committed = cumulative_cost_commitment(
                    session, covered_run_ids=frozenset(r.id for r in runs if r.id != run.id)
                )
                known = Decimal(run.known_cost_usd) if run.known_cost_usd is not None else None
                terminal = run.state in {
                    "succeeded",
                    "imported",
                    "cleaned",
                    "failed",
                    "cancelled",
                    "expired",
                }
                settled = bool(
                    terminal and run.summary_written and known is not None and committed == known
                )
                entries.append(
                    dict(
                        key="batch:" + str(run.id),
                        category=category_for_kind(run.kind),
                        committed=committed,
                        realized=known,
                        settled=settled,
                        evidence={
                            "source": "classification_batch_runs",
                            "run_id": str(run.id),
                            "state": run.state,
                        },
                    )
                )
                evidence.append([str(run.id), str(committed), str(known), settled])
            snapshots = session.scalars(
                select(LyricClassificationSnapshot).where(
                    LyricClassificationSnapshot.batch_run_id.is_(None),
                    LyricClassificationSnapshot.prompt_version.in_(REVISION_PROMPT_VERSIONS),
                )
            )
            for snapshot in snapshots:
                if snapshot.estimated_cost_usd is None:
                    ledger.attest(
                        provider_complete=False, evidence={"unpriced_snapshot": str(snapshot.id)}
                    )
                    raise campaign_budget.BudgetBlocked("revision snapshot has unknown cost")
                actual = Decimal(snapshot.estimated_cost_usd)
                entries.append(
                    dict(
                        key="snapshot:" + str(snapshot.id),
                        category="main",
                        committed=actual,
                        realized=actual,
                        settled=True,
                        evidence={
                            "source": "classification_snapshots",
                            "snapshot_id": str(snapshot.id),
                        },
                    )
                )
                evidence.append(["snapshot", str(snapshot.id), str(actual)])
            digest = hashlib.sha256(
                json.dumps(sorted(evidence, key=str), sort_keys=True).encode()
            ).hexdigest()
            ledger.sync_provider(
                entries,
                evidence={
                    "source": "database_repeatable_budget_read",
                    "commitments_sha256": digest,
                    "campaign_runs": len(evidence),
                },
            )
            if reconciliation_only:
                return ledger
            if exclude_run_id is not None:
                ledger.reserve(
                    "batch:" + str(exclude_run_id),
                    category,
                    new_conservative_cost,
                    {"source": "pre_provider_conservative_bound"},
                    operator_cap,
                )
                return Decimal(ledger.snapshot()["committed_usd"])
            return ledger.preview(category, new_conservative_cost, operator_cap)
        except campaign_budget.BudgetBlocked as exc:
            raise CostBudgetExceeded(str(exc)) from exc
