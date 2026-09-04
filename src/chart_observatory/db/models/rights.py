from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class RightsProfileRow(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "rights_profiles"

    source_id: Mapped[UUID] = mapped_column(ForeignKey("data_sources.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grants: Mapped[list["RightsGrantRow"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class RightsGrantRow(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "rights_grants"
    __table_args__ = (UniqueConstraint("profile_id", "operation"),)

    profile_id: Mapped[UUID] = mapped_column(ForeignKey("rights_profiles.id"), index=True)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    profile: Mapped[RightsProfileRow] = relationship(back_populates="grants")
