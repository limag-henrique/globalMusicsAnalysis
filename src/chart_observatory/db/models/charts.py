from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.engine import Connection
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class ChartDefinition(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "chart_definitions"
    __table_args__ = (
        UniqueConstraint("platform_code", "source_code", "country_code", "chart_name"),
    )
    platform_code: Mapped[str] = mapped_column(String(50), nullable=False)
    source_code: Mapped[str] = mapped_column(String(80), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    chart_name: Mapped[str] = mapped_column(String(200), nullable=False)
    native_frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    nominal_depth: Mapped[int | None] = mapped_column(Integer)
    methodology_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")


class ChartSnapshot(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "chart_snapshots"
    chart_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("chart_definitions.id"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_start: Mapped[date | None] = mapped_column(Date)
    effective_end: Mapped[date | None] = mapped_column(Date)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
    collector_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supersedes_snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("chart_snapshots.id"))
    provider_metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class ChartEntry(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "chart_entries"
    __table_args__ = (UniqueConstraint("snapshot_id", "position"),)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("chart_snapshots.id"), index=True)
    platform_item_id: Mapped[UUID] = mapped_column(ForeignKey("platform_items.id"), index=True)
    canonical_track_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("canonical_tracks.id"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_type: Mapped[str] = mapped_column(String(20), nullable=False, default="NONE")
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    raw_fields: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


def _reject_immutable_chart_change(
    _mapper: Mapper[object], _connection: Connection, _target: object
) -> None:
    raise InvalidRequestError("immutable chart record")


for _immutable_model in (ChartSnapshot, ChartEntry):
    event.listen(_immutable_model, "before_update", _reject_immutable_chart_change)
    event.listen(_immutable_model, "before_delete", _reject_immutable_chart_change)
