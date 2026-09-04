from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class AuditEvent(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_events"
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
