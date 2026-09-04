from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from chart_observatory.db.models.reference import DataSource
from chart_observatory.db.models.rights import RightsProfileRow
from chart_observatory.domain.enums import RightsOperation, RightsProfileStatus
from chart_observatory.rights.models import RightsGrant, RightsProfile


class RightsRepository(Protocol):
    def profiles_for(self, source_id: UUID, occurred_at: datetime) -> Sequence[RightsProfile]: ...


class InMemoryRightsRepository:
    def __init__(self, profiles: Iterable[RightsProfile] = ()) -> None:
        self.profiles = list(profiles)

    def profiles_for(self, source_id: UUID, occurred_at: datetime) -> Sequence[RightsProfile]:
        return [profile for profile in self.profiles if profile.source_id == source_id]


class SqlRightsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def seed_pending_network_profiles(self, valid_from: datetime) -> None:
        sources = self.session.scalars(
            select(DataSource).where(DataSource.network_source.is_(True))
        ).all()
        for source in sources:
            existing = self.session.scalar(
                select(RightsProfileRow.id).where(RightsProfileRow.source_id == source.id)
            )
            if existing is None:
                self.session.add(
                    RightsProfileRow(
                        id=uuid5(NAMESPACE_URL, f"chart-observatory:pending:{source.code}"),
                        source_id=source.id,
                        status=RightsProfileStatus.PENDING,
                        valid_from=valid_from,
                        valid_until=None,
                    )
                )
        self.session.flush()

    def profiles_for(self, source_id: UUID, occurred_at: datetime) -> Sequence[RightsProfile]:
        rows = self.session.scalars(
            select(RightsProfileRow)
            .where(RightsProfileRow.source_id == source_id)
            .options(selectinload(RightsProfileRow.grants))
        ).all()
        return [
            RightsProfile(
                id=row.id,
                source_id=row.source_id,
                status=RightsProfileStatus(row.status),
                valid_from=row.valid_from,
                valid_until=row.valid_until,
                grants=tuple(
                    RightsGrant(row.id, RightsOperation(grant.operation), grant.allowed)
                    for grant in row.grants
                ),
            )
            for row in rows
        ]
