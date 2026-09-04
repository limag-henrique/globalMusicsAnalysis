from dataclasses import dataclass
from typing import Protocol

from chart_observatory.charts.dto import ChartPayload


@dataclass(frozen=True)
class CurrentChartRequest:
    country_code: str
    chart_name: str


class ChartSource(Protocol):
    def capabilities(self) -> dict[str, object]: ...
    def fetch_current(self, request: CurrentChartRequest) -> ChartPayload: ...
