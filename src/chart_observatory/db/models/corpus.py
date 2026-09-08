from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

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
