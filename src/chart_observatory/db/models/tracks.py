from uuid import UUID

from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin

track_artists = Table(
    "track_artists",
    Base.metadata,
    Column("track_id", ForeignKey("canonical_tracks.id"), primary_key=True),
    Column("artist_id", ForeignKey("artists.id"), primary_key=True),
)


class Artist(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "artists"
    name: Mapped[str] = mapped_column(String(500), nullable=False)


class CanonicalTrack(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "canonical_tracks"
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    artists: Mapped[list[Artist]] = relationship(secondary=track_artists)


class PlatformItem(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "platform_items"
    __table_args__ = (UniqueConstraint("platform_code", "native_id"),)
    platform_code: Mapped[str] = mapped_column(String(50), nullable=False)
    native_id: Mapped[str] = mapped_column(String(500), nullable=False)
    item_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str | None] = mapped_column(String(1000))


class ExternalIdClaim(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "external_id_claims"
    namespace: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    source_code: Mapped[str] = mapped_column(String(80), nullable=False)
    canonical_track_id: Mapped[UUID | None] = mapped_column(ForeignKey("canonical_tracks.id"))
    platform_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("platform_items.id"))


class PlatformItemTrackLink(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "platform_item_track_links"
    __table_args__ = (UniqueConstraint("canonical_track_id", "platform_item_id"),)
    canonical_track_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_tracks.id"))
    platform_item_id: Mapped[UUID] = mapped_column(ForeignKey("platform_items.id"))
    evidence: Mapped[str] = mapped_column(String(100), nullable=False)
    item: Mapped[PlatformItem] = relationship()
