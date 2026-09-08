from datetime import date
from uuid import UUID

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class SourceInventory(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """Immutable inventory metadata for one discovered source artifact."""

    __tablename__ = "source_inventories"

    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    origin_platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    countries: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    chart_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    earliest_date: Mapped[date | None] = mapped_column(Date)
    latest_date: Mapped[date | None] = mapped_column(Date)
    number_of_tracks: Mapped[int | None] = mapped_column(Integer)
    number_of_observations: Mapped[int | None] = mapped_column(Integer)
    missing_periods: Mapped[int | None] = mapped_column(Integer)
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)


class SourceCapability(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """A provider/platform/market capability observed in an inventory run."""

    __tablename__ = "source_capabilities"
    __table_args__ = (
        UniqueConstraint(
            "source_inventory_id",
            "provider",
            "origin_platform",
            "country_code",
        ),
    )

    source_inventory_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_inventories.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    origin_platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    country_name: Mapped[str | None] = mapped_column(String(160))
    territory_type: Mapped[str] = mapped_column(String(30), nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    earliest_date: Mapped[date | None] = mapped_column(Date)
    latest_date: Mapped[date | None] = mapped_column(Date)
    chart_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    native_frequency: Mapped[str | None] = mapped_column(String(20))
    ranking_depth: Mapped[int | None] = mapped_column(Integer)
    number_of_tracks: Mapped[int | None] = mapped_column(Integer)
    number_of_observations: Mapped[int | None] = mapped_column(Integer)
    coverage_ratio: Mapped[float | None] = mapped_column()


class SourceCoverage(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """A native-period coverage claim attached to a source inventory run."""

    __tablename__ = "source_coverage"
    __table_args__ = (
        UniqueConstraint(
            "source_inventory_id",
            "provider",
            "origin_platform",
            "country_code",
            "chart_name",
            "period_start",
            "period_end",
        ),
    )

    source_inventory_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_inventories.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    origin_platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    chart_name: Mapped[str] = mapped_column(String(200), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(500))
    native_frequency: Mapped[str | None] = mapped_column(String(20))
    ranking_depth: Mapped[int | None] = mapped_column(Integer)
