from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class AnalysisRun(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "analysis_runs"
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    input_snapshot_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    output_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    software_version: Mapped[str] = mapped_column(String(50), nullable=False)
    git_revision: Mapped[str | None] = mapped_column(String(64))
    dirty: Mapped[bool] = mapped_column(Boolean, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
