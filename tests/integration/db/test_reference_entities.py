from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.repositories.reference import ReferenceRepository


def test_soundcharts_provider_is_distinct_from_spotify_platform() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = ReferenceRepository(session)
        repository.seed_defaults()
        session.commit()

        spotify = repository.get_platform("SPOTIFY")
        soundcharts = repository.get_source("SOUNDCHARTS")

        assert spotify.code == "SPOTIFY"
        assert soundcharts.code == "SOUNDCHARTS"
        assert spotify.__class__ is not soundcharts.__class__


def test_initial_countries_are_seeded_without_europe_aggregate() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = ReferenceRepository(session)
        repository.seed_defaults()
        session.commit()

        assert {country.code for country in repository.list_countries()} == {
            "BR",
            "US",
            "GB",
            "FR",
            "DE",
            "ES",
            "PT",
            "IT",
            "SE",
        }
