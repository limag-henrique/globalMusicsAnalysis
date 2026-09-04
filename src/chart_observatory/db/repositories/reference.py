from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.db.models.reference import Country, DataSource, Platform
from chart_observatory.domain.enums import PlatformCode, SourceCode

PLATFORM_NAMES = {
    PlatformCode.APPLE_MUSIC: "Apple Music",
    PlatformCode.SPOTIFY: "Spotify",
    PlatformCode.YOUTUBE_VIDEO: "YouTube Video",
    PlatformCode.YOUTUBE_MUSIC: "YouTube Music",
    PlatformCode.AMAZON_MUSIC: "Amazon Music",
}

SOURCE_NAMES = {
    SourceCode.APPLE_MUSIC_API: ("Apple Music API", True),
    SourceCode.YOUTUBE_DATA_API: ("YouTube Data API", True),
    SourceCode.YOUTUBE_MUSIC_CHARTS: ("YouTube Music Charts", True),
    SourceCode.SPOTIFY_CHARTS: ("Spotify Charts", True),
    SourceCode.SPOTIFY_WEB_API: ("Spotify Web API", True),
    SourceCode.AMAZON_MUSIC_API: ("Amazon Music API", True),
    SourceCode.SOUNDCHARTS: ("Soundcharts", True),
    SourceCode.CHARTMETRIC: ("Chartmetric", True),
    SourceCode.LUMINATE: ("Luminate", True),
    SourceCode.MANUAL_AUTHORIZED_FILE: ("Manual authorized file", False),
}

COUNTRY_NAMES = {
    "BR": "Brasil",
    "US": "Estados Unidos",
    "GB": "Reino Unido",
    "FR": "França",
    "DE": "Alemanha",
    "ES": "Espanha",
    "PT": "Portugal",
    "IT": "Itália",
    "SE": "Suécia",
}


class ReferenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def seed_defaults(self) -> None:
        for platform_code, name in PLATFORM_NAMES.items():
            self._insert_if_missing(Platform, str(platform_code), name)
        for source_code, (name, network_source) in SOURCE_NAMES.items():
            self._insert_if_missing(
                DataSource,
                str(source_code),
                name,
                network_source=network_source,
            )
        for country_code, name in COUNTRY_NAMES.items():
            self._insert_if_missing(Country, country_code, name)
        self._session.flush()

    def get_platform(self, code: str) -> Platform:
        return self._session.scalars(select(Platform).where(Platform.code == code)).one()

    def get_source(self, code: str) -> DataSource:
        return self._session.scalars(select(DataSource).where(DataSource.code == code)).one()

    def list_countries(self) -> Sequence[Country]:
        return self._session.scalars(select(Country).order_by(Country.code)).all()

    def _insert_if_missing(
        self,
        model: type[Platform] | type[DataSource] | type[Country],
        code: str,
        name: str,
        **values: object,
    ) -> None:
        exists = self._session.scalar(select(model.id).where(model.code == code))
        if exists is None:
            self._session.add(model(code=code, name=name, **values))
