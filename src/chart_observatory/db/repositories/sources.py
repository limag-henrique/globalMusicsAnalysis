from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from chart_observatory.db.models.sources import SourceCapability, SourceCoverage, SourceInventory
from chart_observatory.sources.models import MarketCapability, SourceManifest


class SourceInventoryRepository:
    """Store and query source manifests, capabilities, and native-period coverage."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_manifest(
        self,
        manifest: SourceManifest,
        *,
        capabilities: Sequence[MarketCapability] = (),
        coverage: Sequence[Mapping[str, object]] = (),
    ) -> SourceInventory:
        existing = self._session.scalar(
            select(SourceInventory).where(SourceInventory.sha256 == manifest.sha256)
        )
        if existing is not None:
            return existing

        row = SourceInventory(
            provider=manifest.provider,
            origin_platform=manifest.origin_platform,
            filename=manifest.filename,
            artifact_path=str(manifest.path),
            sha256=manifest.sha256,
            size_bytes=manifest.size_bytes,
            row_count=manifest.row_count,
            schema_version=manifest.schema_version,
            status=str(manifest.status),
            countries=list(manifest.countries),
            chart_types=list(manifest.chart_types),
            earliest_date=manifest.earliest_date,
            latest_date=manifest.latest_date,
            number_of_tracks=manifest.number_of_tracks,
            number_of_observations=manifest.number_of_observations,
            missing_periods=manifest.missing_periods,
            parser_version=manifest.parser_version,
        )
        self._session.add(row)
        self._session.flush()
        for capability in capabilities:
            self._session.add(
                SourceCapability(
                    source_inventory_id=row.id,
                    provider=capability.provider,
                    origin_platform=capability.origin_platform,
                    country_code=capability.country_code,
                    country_name=capability.country_name,
                    territory_type=capability.territory_type,
                    available=capability.available,
                    earliest_date=capability.earliest_date,
                    latest_date=capability.latest_date,
                    chart_types=list(capability.chart_types),
                    native_frequency=capability.native_frequency,
                    ranking_depth=capability.ranking_depth,
                    number_of_tracks=capability.number_of_tracks,
                    number_of_observations=capability.number_of_observations,
                    coverage_ratio=capability.coverage_ratio,
                )
            )
        for item in coverage:
            self._session.add(
                SourceCoverage(
                    source_inventory_id=row.id,
                    provider=str(item.get("provider", manifest.provider)),
                    origin_platform=str(item.get("origin_platform", manifest.origin_platform)),
                    country_code=str(item["country_code"]).upper(),
                    chart_name=str(item["chart_name"]),
                    period_start=_as_date(item["period_start"]),
                    period_end=_as_date(item["period_end"]),
                    status=str(item["status"]),
                    reason=_as_optional_string(item.get("reason")),
                    native_frequency=_as_optional_string(item.get("native_frequency")),
                    ranking_depth=_as_optional_int(item.get("ranking_depth")),
                )
            )
        self._session.flush()
        return row

    def list_manifests(
        self, *, provider: str | None = None, status: str | None = None
    ) -> list[SourceInventory]:
        statement: Select[tuple[SourceInventory]] = select(SourceInventory).order_by(
            SourceInventory.created_at, SourceInventory.filename
        )
        if provider is not None:
            statement = statement.where(SourceInventory.provider == provider)
        if status is not None:
            statement = statement.where(SourceInventory.status == status)
        return list(self._session.scalars(statement).all())

    def list_capabilities(
        self,
        *,
        provider: str | None = None,
        origin_platform: str | None = None,
        country_code: str | None = None,
        available: bool | None = None,
    ) -> list[SourceCapability]:
        statement: Select[tuple[SourceCapability]] = select(SourceCapability).order_by(
            SourceCapability.provider,
            SourceCapability.origin_platform,
            SourceCapability.country_code,
        )
        if provider is not None:
            statement = statement.where(SourceCapability.provider == provider)
        if origin_platform is not None:
            statement = statement.where(SourceCapability.origin_platform == origin_platform)
        if country_code is not None:
            statement = statement.where(SourceCapability.country_code == country_code.upper())
        if available is not None:
            statement = statement.where(SourceCapability.available == available)
        return list(self._session.scalars(statement).all())

    def list_coverage(
        self,
        *,
        provider: str | None = None,
        origin_platform: str | None = None,
        country_code: str | None = None,
        status: str | None = None,
    ) -> list[SourceCoverage]:
        statement: Select[tuple[SourceCoverage]] = select(SourceCoverage).order_by(
            SourceCoverage.country_code,
            SourceCoverage.period_start,
            SourceCoverage.provider,
        )
        if provider is not None:
            statement = statement.where(SourceCoverage.provider == provider)
        if origin_platform is not None:
            statement = statement.where(SourceCoverage.origin_platform == origin_platform)
        if country_code is not None:
            statement = statement.where(SourceCoverage.country_code == country_code.upper())
        if status is not None:
            statement = statement.where(SourceCoverage.status == status)
        return list(self._session.scalars(statement).all())


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError("coverage dates must be date instances or ISO strings")


def _as_optional_string(value: object) -> str | None:
    return str(value) if value is not None else None


def _as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return int(str(value))
