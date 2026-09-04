from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from chart_observatory.db.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class Platform(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "platforms"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DataSource(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "data_sources"

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    network_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Country(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
