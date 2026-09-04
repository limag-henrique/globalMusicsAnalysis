from typing import NoReturn

from chart_observatory.domain.errors import SourceDisabled


class DisabledChartSource:
    def __init__(self, source_code: str) -> None:
        self.source_code = source_code

    def capabilities(self) -> dict[str, object]:
        return {"source_code": self.source_code, "enabled": False}

    def fetch_current(self, request: object) -> NoReturn:
        raise SourceDisabled(f"{self.source_code} is disabled")
