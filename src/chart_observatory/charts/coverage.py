from dataclasses import dataclass
from datetime import date
from uuid import UUID

from chart_observatory.domain.enums import CoverageStatus
from chart_observatory.domain.errors import DomainValidationError, TemporalAlignmentRequired


@dataclass(frozen=True)
class CoverageRecord:
    chart_definition_id: UUID
    period_start: date
    period_end: date
    status: CoverageStatus
    native_frequency: str


@dataclass(frozen=True)
class CommonObservationWindow:
    start: date
    end: date
    excluded_cells: int
    native_frequency: str


class CoverageService:
    def __init__(self, records: list[CoverageRecord] | None = None) -> None:
        self.records = list(records or [])

    def record(self, record: CoverageRecord) -> None:
        self.records.append(record)

    def coverage_matrix(self) -> tuple[CoverageRecord, ...]:
        return tuple(
            sorted(
                self.records,
                key=lambda row: (
                    str(row.chart_definition_id),
                    row.period_start,
                    row.period_end,
                    row.status,
                ),
            )
        )

    def common_observation_window(self, chart_ids: list[UUID]) -> CommonObservationWindow:
        available = [
            row
            for row in self.records
            if row.chart_definition_id in chart_ids and row.status is CoverageStatus.AVAILABLE
        ]
        if {row.chart_definition_id for row in available} != set(chart_ids):
            raise DomainValidationError("every selected chart requires AVAILABLE coverage")
        frequencies = {row.native_frequency for row in available}
        if len(frequencies) != 1:
            raise TemporalAlignmentRequired("mixed native frequencies require an alignment policy")
        start = max(
            min(row.period_start for row in available if row.chart_definition_id == chart_id)
            for chart_id in chart_ids
        )
        end = min(
            max(row.period_end for row in available if row.chart_definition_id == chart_id)
            for chart_id in chart_ids
        )
        if start > end:
            raise DomainValidationError("selected charts have no common observation window")
        excluded = sum(
            row.status is not CoverageStatus.AVAILABLE
            for row in self.records
            if row.chart_definition_id in chart_ids
        )
        return CommonObservationWindow(start, end, excluded, next(iter(frequencies)))
