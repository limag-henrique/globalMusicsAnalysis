from datetime import date, datetime
from uuid import UUID

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class CollectionRun(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "collection_runs"
    chart_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("chart_definitions.id"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class CoverageCell(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "coverage_cells"
    chart_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("chart_definitions.id"), index=True
    )
    collection_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("collection_runs.id"))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
