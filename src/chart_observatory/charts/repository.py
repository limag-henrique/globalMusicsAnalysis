from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from chart_observatory.db.models.charts import ChartDefinition, ChartEntry, ChartSnapshot


class ChartRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_definition(
        self,
        platform_code: str,
        source_code: str,
        country_code: str,
        chart_name: str,
        native_frequency: str,
        nominal_depth: int | None,
    ) -> ChartDefinition:
        row = ChartDefinition(
            platform_code=platform_code,
            source_code=source_code,
            country_code=country_code,
            chart_name=chart_name,
            native_frequency=native_frequency,
            nominal_depth=nominal_depth,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def create_snapshot(
        self,
        definition_id: UUID,
        period_start: date,
        period_end: date,
        observed_at: datetime,
        checksum: str,
        *,
        supersedes_snapshot_id: UUID | None = None,
        effective_start: date | None = None,
        effective_end: date | None = None,
        provider_metadata: dict[str, object] | None = None,
    ) -> ChartSnapshot:
        row = ChartSnapshot(
            chart_definition_id=definition_id,
            period_start=period_start,
            period_end=period_end,
            observed_at=observed_at,
            checksum=checksum,
            supersedes_snapshot_id=supersedes_snapshot_id,
            effective_start=effective_start,
            effective_end=effective_end,
            provider_metadata=provider_metadata or {},
        )
        self.session.add(row)
        self.session.flush()
        return row

    def add_entry(
        self,
        snapshot_id: UUID,
        platform_item_id: UUID,
        position: int,
        metric_value: Decimal | None,
        *,
        metric_type: str = "NONE",
        canonical_track_id: UUID | None = None,
        raw_fields: dict[str, object] | None = None,
    ) -> ChartEntry:
        row = ChartEntry(
            snapshot_id=snapshot_id,
            platform_item_id=platform_item_id,
            canonical_track_id=canonical_track_id,
            position=position,
            metric_type=metric_type,
            metric_value=metric_value,
            raw_fields=raw_fields or {},
        )
        self.session.add(row)
        self.session.flush()
        return row
