"""Mutable operational ledger for asynchronous lyric-classification batches."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class LyricClassificationBatchRun(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """One finite provider batch and its immutable source-object identity."""

    __tablename__ = "lyric_classification_batch_runs"

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_model_version: Mapped[str | None] = mapped_column(String(200))
    taxonomy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    thinking_level: Mapped[str] = mapped_column(String(16), nullable=False)
    project_id: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str] = mapped_column(String(40), nullable=False)
    bucket_name: Mapped[str] = mapped_column(String(222), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(Text)
    source_generation: Mapped[int | None] = mapped_column(BigInteger)
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    source_byte_count: Mapped[int | None] = mapped_column(BigInteger)
    request_count: Mapped[int] = mapped_column(nullable=False, default=0)
    output_uri_prefix: Mapped[str | None] = mapped_column(Text)
    output_object_names: Mapped[list[str] | None] = mapped_column(JSON)
    provider_job_name: Mapped[str | None] = mapped_column(Text, unique=True)
    expected_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    conservative_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    known_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    provider_successful_count: Mapped[int | None] = mapped_column()
    provider_failed_count: Mapped[int | None] = mapped_column()
    imported_count: Mapped[int] = mapped_column(nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(nullable=False, default=0)
    job_error_code: Mapped[str | None] = mapped_column(String(100))
    job_error_message: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleaned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pilot_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pilot_accepted_by: Mapped[str | None] = mapped_column(String(200))
    summary_written: Mapped[bool] = mapped_column(nullable=False, default=False)


class LyricClassificationBatchItem(CreatedAtMixin, Base):
    """Reserved corpus item reconciled only through a random UUIDv4 key."""

    __tablename__ = "lyric_classification_batch_items"
    __table_args__ = (
        UniqueConstraint("batch_run_id", "line_number", name="uq_lyric_batch_item_line"),
        Index(
            "uq_lyric_batch_items_active_signature",
            "canonical_track_id",
            "lyrics_hash",
            "model_id",
            "taxonomy_version",
            "prompt_version",
            unique=True,
            postgresql_where=text("state IN ('reserved','submitted','running')"),
            sqlite_where=text("state IN ('reserved','submitted','running')"),
        ),
    )

    opaque_key: Mapped[UUID] = mapped_column(primary_key=True)
    batch_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("lyric_classification_batch_runs.id"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(nullable=False)
    lyric_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("lyric_documents.id"), nullable=False, index=True
    )
    canonical_track_id: Mapped[UUID] = mapped_column(
        ForeignKey("canonical_tracks.id"), nullable=False, index=True
    )
    lyrics_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    request_sha256: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("lyric_classification_snapshots.id"), unique=True
    )
    retry_of_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("lyric_classification_snapshots.id")
    )
    provider_status: Mapped[str | None] = mapped_column(String(80))
    error_code: Mapped[str | None] = mapped_column(String(100))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
