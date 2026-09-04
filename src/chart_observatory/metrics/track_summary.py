from decimal import Decimal
from statistics import median
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from chart_observatory.db.models.charts import ChartDefinition, ChartEntry, ChartSnapshot
from chart_observatory.domain.errors import DomainValidationError
from chart_observatory.metrics.models import MetricObservation, TrackPlatformCountrySummary


def _sum_type(rows: list[MetricObservation], metric_type: str) -> Decimal | None:
    values = [
        row.metric_value
        for row in rows
        if row.metric_type == metric_type and row.metric_value is not None
    ]
    return sum(values, Decimal(0)) if values else None


def summarize(rows: list[MetricObservation]) -> TrackPlatformCountrySummary:
    frequencies = {row.native_frequency for row in rows}
    if len(frequencies) > 1:
        raise DomainValidationError("summary groups must have one native frequency")
    resolved = [row for row in rows if row.resolved]
    periods = {(row.period_start, row.period_end) for row in resolved}
    ranks = [row.rank for row in resolved]
    frequency = next(iter(frequencies), "DAILY")
    period_unit = (
        "WEEKS" if frequency == "WEEKLY" else "DAYS" if frequency == "DAILY" else "PERIODS"
    )
    mean_rank = sum((Decimal(rank) for rank in ranks), Decimal(0)) / len(ranks) if ranks else None
    median_rank = Decimal(str(median(ranks))) if ranks else None
    return TrackPlatformCountrySummary(
        appearances=len(resolved),
        distinct_periods=len(periods),
        days_or_weeks_in_chart=len(periods),
        period_unit=period_unit,
        first_period=min((row.period_start for row in resolved), default=None),
        last_period=max((row.period_end for row in resolved), default=None),
        peak_rank=min(ranks, default=None),
        mean_rank=mean_rank,
        median_rank=median_rank,
        top_10=sum(rank <= 10 for rank in ranks),
        top_20=sum(rank <= 20 for rank in ranks),
        top_50=sum(rank <= 50 for rank in ranks),
        top_100=sum(rank <= 100 for rank in ranks),
        stream_sum=_sum_type(resolved, "STREAMS"),
        view_sum=_sum_type(resolved, "VIEWS"),
        unit_sum=_sum_type(resolved, "UNITS"),
        creation_sum=_sum_type(resolved, "CREATIONS"),
        unresolved_numerator=sum(not row.resolved for row in rows),
        unresolved_denominator=len(rows),
    )


def summarize_track_platform_country(
    session: Session,
    canonical_track_id: UUID,
    chart_definition_id: UUID,
) -> TrackPlatformCountrySummary:
    """Summarize one track while retaining unresolved rows in the denominator."""
    statement = (
        select(ChartEntry, ChartSnapshot, ChartDefinition)
        .join(ChartSnapshot, ChartEntry.snapshot_id == ChartSnapshot.id)
        .join(ChartDefinition, ChartSnapshot.chart_definition_id == ChartDefinition.id)
        .where(
            ChartDefinition.id == chart_definition_id,
            or_(
                ChartEntry.canonical_track_id == canonical_track_id,
                ChartEntry.canonical_track_id.is_(None),
            ),
        )
        .order_by(ChartSnapshot.period_start, ChartEntry.position)
    )
    observations = [
        MetricObservation(
            period_start=snapshot.period_start,
            period_end=snapshot.period_end,
            rank=entry.position,
            native_frequency=definition.native_frequency,
            metric_type=entry.metric_type,
            metric_value=entry.metric_value,
            resolved=entry.canonical_track_id == canonical_track_id,
        )
        for entry, snapshot, definition in session.execute(statement)
    ]
    return summarize(observations)
