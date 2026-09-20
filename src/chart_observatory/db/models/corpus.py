from datetime import date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import (
    DDL,
    JSON,
    BigInteger,
    Column,
    Date,
    DateTime,
    DefaultClause,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.engine import Connection
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class MarketGeography(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "market_geography"
    __table_args__ = (UniqueConstraint("country_code", "source_version"),)

    country_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    iso3: Mapped[str] = mapped_column(String(3), nullable=False)
    country_name: Mapped[str] = mapped_column(String(160), nullable=False)
    m49: Mapped[str] = mapped_column(String(3), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    subregion: Mapped[str] = mapped_column(String(100), nullable=False)
    intermediate_region: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="UN_M49_ISO_3166")
    source_version: Mapped[str] = mapped_column(String(40), nullable=False)


class ChartCellProfile(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "chart_cell_profiles"
    __table_args__ = (
        UniqueConstraint("provider", "platform_code", "country_code", "chart_family", "frequency"),
    )

    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    platform_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    chart_family: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    first_date: Mapped[date | None] = mapped_column(Date)
    last_date: Mapped[date | None] = mapped_column(Date)
    expected_periods: Mapped[int] = mapped_column(nullable=False, default=0)
    observed_periods: Mapped[int] = mapped_column(nullable=False, default=0)
    coverage_ratio: Mapped[float] = mapped_column(nullable=False, default=0.0)
    longest_gap: Mapped[int] = mapped_column(nullable=False, default=0)
    number_of_tracks: Mapped[int] = mapped_column(nullable=False, default=0)
    median_chart_depth: Mapped[float] = mapped_column(nullable=False, default=0.0)
    source_quality: Mapped[float] = mapped_column(nullable=False, default=1.0)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class CanonicalChartEntry(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "canonical_chart_entries"
    __table_args__ = (
        UniqueConstraint(
            "origin_platform",
            "country_code",
            "chart_family",
            "period_start",
            "period_end",
            "canonical_track_id",
        ),
    )

    origin_platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    chart_family: Mapped[str] = mapped_column(String(100), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    canonical_track_id: Mapped[UUID] = mapped_column(
        ForeignKey("canonical_tracks.id"), nullable=False, index=True
    )
    rank: Mapped[int] = mapped_column(nullable=False)
    metric_type: Mapped[str] = mapped_column(String(30), nullable=False, default="NONE")
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 6))
    selected_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    selected_chart_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("chart_entries.id"), nullable=False
    )
    source_entry_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conflict_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NONE")
    reconciliation_version: Mapped[str] = mapped_column(String(40), nullable=False)


class SourceConflict(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "source_conflicts"
    canonical_chart_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("canonical_chart_entries.id"), nullable=False, index=True
    )
    conflict_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_values: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SOURCE_CONFLICT")


class CorpusVersion(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "corpus_versions"
    __table_args__ = (UniqueConstraint("name", "version"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="FROZEN")
    rules: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    source_snapshot_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    software_version: Mapped[str] = mapped_column(String(50), nullable=False)
    git_revision: Mapped[str | None] = mapped_column(String(64))
    dirty: Mapped[bool] = mapped_column(nullable=False, default=True)
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CorpusMembership(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "corpus_memberships"
    __table_args__ = (UniqueConstraint("corpus_version_id", "member_type", "member_key"),)

    corpus_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("corpus_versions.id"), nullable=False, index=True
    )
    member_type: Mapped[str] = mapped_column(String(30), nullable=False)
    member_key: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80))
    platform_code: Mapped[str | None] = mapped_column(String(50))
    country_code: Mapped[str | None] = mapped_column(String(20))
    chart_family: Mapped[str | None] = mapped_column(String(100))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    eligible: Mapped[bool] = mapped_column(nullable=False, default=True)
    reason: Mapped[str | None] = mapped_column(String(500))


class GenreTaxonomy(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "genre_taxonomy"
    __table_args__ = (UniqueConstraint("code", "version"),)

    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(40), nullable=False)


class GenreClaim(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "genre_claims"
    canonical_track_id: Mapped[UUID] = mapped_column(
        ForeignKey("canonical_tracks.id"), nullable=False, index=True
    )
    raw_label: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_genre: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_version: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, default="UNREVIEWED")


class TrackLanguage(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "track_languages"
    __table_args__ = (UniqueConstraint("canonical_track_id", "language_code", "source"),)

    canonical_track_id: Mapped[UUID] = mapped_column(
        ForeignKey("canonical_tracks.id"), nullable=False, index=True
    )
    language_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    raw_value: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_version: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    is_multilingual: Mapped[bool] = mapped_column(nullable=False, default=False)


class LyricDocument(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "lyric_documents"
    __table_args__ = (UniqueConstraint("canonical_track_id", "source", "content_sha256"),)

    canonical_track_id: Mapped[UUID] = mapped_column(
        ForeignKey("canonical_tracks.id"), nullable=False, index=True
    )
    language_code: Mapped[str | None] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_version: Mapped[str] = mapped_column(String(40), nullable=False)
    rights_status: Mapped[str] = mapped_column(String(40), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class SemanticAnnotation(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "semantic_annotations"
    __table_args__ = (UniqueConstraint("lyric_document_id", "category", "model_version"),)

    lyric_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("lyric_documents.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[float] = mapped_column(nullable=False)
    confidence: Mapped[float | None] = mapped_column()
    method: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, default="UNREVIEWED")


class LyricClassificationSnapshot(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    """An immutable automatic-classification outcome for one lyric document."""

    __tablename__ = "lyric_classification_snapshots"
    __table_args__ = (
        Index(
            "ix_lyric_classification_snapshots_signature",
            "canonical_track_id",
            "lyrics_hash",
            "model_id",
            "taxonomy_version",
            "prompt_version",
        ),
        Index(
            "ix_lyric_classification_snapshots_classification_status",
            "classification_status",
        ),
    )

    lyric_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("lyric_documents.id"), nullable=False
    )
    canonical_track_id: Mapped[UUID] = mapped_column(
        ForeignKey("canonical_tracks.id"), nullable=False
    )
    lyrics_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    classification_status: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float | None] = mapped_column()
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column()
    output_tokens: Mapped[int | None] = mapped_column()
    thought_tokens: Mapped[int | None] = mapped_column()
    total_tokens: Mapped[int | None] = mapped_column()
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    append_order: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False)
    forced_from_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("lyric_classification_snapshots.id")
    )


def _reject_immutable_lyric_classification_snapshot_change(
    _mapper: Mapper[object], _connection: Connection, _target: object
) -> None:
    raise InvalidRequestError("immutable lyric classification snapshot")


_APPEND_ORDER_IDENTITY = LyricClassificationSnapshot.__table__.c.append_order.identity


def _use_sqlite_append_order_default(
    _target: object, connection: Connection, **_kwargs: object
) -> None:
    if connection.dialect.name == "sqlite":
        append_order = cast(
            Column[object], LyricClassificationSnapshot.__table__.columns["append_order"]
        )
        append_order.server_default = DefaultClause(text("0"))
        append_order.identity = None


def _restore_append_order_identity(
    _target: object, connection: Connection, **_kwargs: object
) -> None:
    if connection.dialect.name == "sqlite":
        append_order = cast(
            Column[object], LyricClassificationSnapshot.__table__.columns["append_order"]
        )
        append_order.server_default = _APPEND_ORDER_IDENTITY
        append_order.identity = _APPEND_ORDER_IDENTITY


event.listen(
    LyricClassificationSnapshot,
    "before_update",
    _reject_immutable_lyric_classification_snapshot_change,
)
event.listen(
    LyricClassificationSnapshot.__table__,
    "before_create",
    _use_sqlite_append_order_default,
)

event.listen(
    LyricClassificationSnapshot.__table__,
    "after_create",
    DDL(  # type: ignore[no-untyped-call]
        """
        CREATE TRIGGER lyric_classification_snapshots_append_order
        AFTER INSERT ON lyric_classification_snapshots
        BEGIN
            UPDATE lyric_classification_snapshots
            SET append_order = (
                SELECT COALESCE(MAX(append_order), 0) + 1
                FROM lyric_classification_snapshots
                WHERE id != NEW.id
            )
            WHERE id = NEW.id;
        END
        """
    ).execute_if(dialect="sqlite"),
)
event.listen(
    LyricClassificationSnapshot.__table__,
    "after_create",
    _restore_append_order_identity,
)
event.listen(
    LyricClassificationSnapshot.__table__,
    "after_create",
    DDL(  # type: ignore[no-untyped-call]
        """
        CREATE TRIGGER lyric_classification_snapshots_immutable_update
        BEFORE UPDATE ON lyric_classification_snapshots
        WHEN NOT (OLD.append_order = 0 AND NEW.append_order > 0)
        BEGIN
            SELECT RAISE(ABORT, 'lyric classification snapshots are immutable');
        END
        """
    ).execute_if(dialect="sqlite"),
)
event.listen(
    LyricClassificationSnapshot.__table__,
    "after_create",
    DDL(  # type: ignore[no-untyped-call]
        """
        CREATE TRIGGER lyric_classification_snapshots_immutable_delete
        BEFORE DELETE ON lyric_classification_snapshots
        BEGIN
            SELECT RAISE(ABORT, 'lyric classification snapshots are immutable');
        END
        """
    ).execute_if(dialect="sqlite"),
)
event.listen(
    LyricClassificationSnapshot,
    "before_delete",
    _reject_immutable_lyric_classification_snapshot_change,
)
