from datetime import date
from uuid import uuid4

import pytest

from chart_observatory.charts.coverage import CoverageRecord, CoverageService
from chart_observatory.domain.enums import CoverageStatus
from chart_observatory.domain.errors import TemporalAlignmentRequired


def test_all_coverage_states_are_retained_and_common_window_is_explicit() -> None:
    first, second = uuid4(), uuid4()
    records = [
        CoverageRecord(
            first, date(2021, 1, 1), date(2026, 8, 28), CoverageStatus.AVAILABLE, "WEEKLY"
        ),
        CoverageRecord(
            second, date(2022, 1, 7), date(2026, 9, 3), CoverageStatus.AVAILABLE, "WEEKLY"
        ),
    ]
    records.extend(
        CoverageRecord(first, date(2021, 1, index), date(2021, 1, index), status, "WEEKLY")
        for index, status in enumerate(CoverageStatus, start=1)
        if status is not CoverageStatus.AVAILABLE
    )
    service = CoverageService(records)
    window = service.common_observation_window([first, second])
    assert window.start == date(2022, 1, 7)
    assert window.end == date(2026, 8, 28)
    assert window.excluded_cells == 5


def test_mixed_native_frequencies_require_policy() -> None:
    first, second = uuid4(), uuid4()
    service = CoverageService(
        [
            CoverageRecord(
                first, date(2026, 1, 1), date(2026, 1, 2), CoverageStatus.AVAILABLE, "DAILY"
            ),
            CoverageRecord(
                second, date(2026, 1, 1), date(2026, 1, 7), CoverageStatus.AVAILABLE, "WEEKLY"
            ),
        ]
    )
    with pytest.raises(TemporalAlignmentRequired):
        service.common_observation_window([first, second])
