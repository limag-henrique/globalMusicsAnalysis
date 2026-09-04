from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.db.models.collection import CollectionRun, CoverageCell
from chart_observatory.domain.enums import CoverageStatus


@dataclass(frozen=True)
class CollectionRunResult:
    id: UUID
    started_at: datetime
    finished_at: datetime | None
    status: CoverageStatus
    error_code: str | None = None


class CollectionRunRepository:
    """Append-only persistence for collection attempts and their coverage result."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record_attempt(
        self,
        chart_definition_id: UUID,
        started_at: datetime,
        period_start: date,
        period_end: date,
        status: CoverageStatus,
        *,
        reason: str | None = None,
        error_code: str | None = None,
        parameters: dict[str, object] | None = None,
    ) -> CollectionRun:
        run = CollectionRun(
            chart_definition_id=chart_definition_id,
            started_at=started_at,
            finished_at=started_at,
            status=status.value,
            error_code=error_code,
            parameters=parameters or {},
        )
        self.session.add(run)
        self.session.flush()
        self.session.add(
            CoverageCell(
                chart_definition_id=chart_definition_id,
                collection_run_id=run.id,
                period_start=period_start,
                period_end=period_end,
                status=status.value,
                reason=reason,
            )
        )
        self.session.flush()
        return run

    def coverage_history(self, chart_definition_id: UUID) -> list[CoverageCell]:
        statement = (
            select(CoverageCell)
            .join(CollectionRun, CoverageCell.collection_run_id == CollectionRun.id)
            .where(CoverageCell.chart_definition_id == chart_definition_id)
            .order_by(CollectionRun.started_at, CoverageCell.id)
        )
        return list(self.session.scalars(statement))
