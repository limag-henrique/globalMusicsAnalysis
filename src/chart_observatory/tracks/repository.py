from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.db.models.tracks import (
    CanonicalTrack,
    ExternalIdClaim,
    PlatformItem,
    PlatformItemTrackLink,
)
from chart_observatory.tracks.normalization import normalize_isrc


class TrackRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_track(self, title: str) -> CanonicalTrack:
        row = CanonicalTrack(title=title)
        self.session.add(row)
        self.session.flush()
        return row

    def create_platform_item(
        self, platform_code: str, native_id: str, item_kind: str, title: str | None = None
    ) -> PlatformItem:
        row = PlatformItem(
            platform_code=platform_code, native_id=native_id, item_kind=item_kind, title=title
        )
        self.session.add(row)
        self.session.flush()
        return row

    def link_item(self, track_id: UUID, item_id: UUID, evidence: str) -> PlatformItemTrackLink:
        link = PlatformItemTrackLink(
            canonical_track_id=track_id, platform_item_id=item_id, evidence=evidence
        )
        self.session.add(link)
        return link

    def items_for_track(self, track_id: UUID) -> list[PlatformItem]:
        return list(
            self.session.scalars(
                select(PlatformItem)
                .join(PlatformItemTrackLink)
                .where(PlatformItemTrackLink.canonical_track_id == track_id)
                .order_by(PlatformItem.created_at, PlatformItem.native_id)
            )
        )

    def claim_external_id(
        self, track_id: UUID, namespace: str, raw_value: str, source_code: str
    ) -> ExternalIdClaim:
        normalized = normalize_isrc(raw_value) if namespace.upper() == "ISRC" else raw_value.strip()
        claim = ExternalIdClaim(
            namespace=namespace.upper(),
            raw_value=raw_value,
            normalized_value=normalized,
            source_code=source_code,
            canonical_track_id=track_id,
        )
        self.session.add(claim)
        return claim

    def claim_item_external_id(
        self, item_id: UUID, namespace: str, raw_value: str, source_code: str
    ) -> ExternalIdClaim:
        normalized = normalize_isrc(raw_value) if namespace.upper() == "ISRC" else raw_value.strip()
        claim = ExternalIdClaim(
            namespace=namespace.upper(),
            raw_value=raw_value,
            normalized_value=normalized,
            source_code=source_code,
            platform_item_id=item_id,
        )
        self.session.add(claim)
        return claim

    def claims_for(self, namespace: str, normalized_value: str) -> list[ExternalIdClaim]:
        return list(
            self.session.scalars(
                select(ExternalIdClaim)
                .where(
                    ExternalIdClaim.namespace == namespace.upper(),
                    ExternalIdClaim.normalized_value == normalized_value,
                )
                .order_by(ExternalIdClaim.created_at, ExternalIdClaim.id)
            )
        )
