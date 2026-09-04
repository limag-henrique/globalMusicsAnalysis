from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.models.reference import DataSource
from chart_observatory.db.repositories.reference import ReferenceRepository
from chart_observatory.domain.enums import RightsProfileStatus
from chart_observatory.rights.repository import SqlRightsRepository


def test_network_sources_are_seeded_pending_without_grants() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ReferenceRepository(session).seed_defaults()
        repository = SqlRightsRepository(session)
        repository.seed_pending_network_profiles(datetime(2026, 9, 4, tzinfo=UTC))
        sources = session.scalars(
            select(DataSource).where(DataSource.network_source.is_(True))
        ).all()
        profiles = [
            profile
            for source in sources
            for profile in repository.profiles_for(source.id, datetime(2026, 9, 4, tzinfo=UTC))
        ]
        assert len(profiles) == len(sources)
        assert all(profile.status is RightsProfileStatus.PENDING for profile in profiles)
        assert all(profile.grants == () for profile in profiles)
