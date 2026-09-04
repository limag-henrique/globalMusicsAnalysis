from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class ResolutionRecord(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "resolution_records"
    platform_item_id: Mapped[UUID] = mapped_column(ForeignKey("platform_items.id"), index=True)
    canonical_track_id: Mapped[UUID | None] = mapped_column(ForeignKey("canonical_tracks.id"))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence: Mapped[str] = mapped_column(String(80), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    candidates: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    reviewer: Mapped[str | None] = mapped_column(String(200))
    reviewer_decision: Mapped[str | None] = mapped_column(String(40))
