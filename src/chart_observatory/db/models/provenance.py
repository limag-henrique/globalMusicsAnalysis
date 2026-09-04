from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class SourceArtifact(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "source_artifacts"
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("data_sources.id"), index=True)
    rights_profile_id: Mapped[UUID] = mapped_column(ForeignKey("rights_profiles.id"))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collector_version: Mapped[str] = mapped_column(String(50), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    acquisition_parameters: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
