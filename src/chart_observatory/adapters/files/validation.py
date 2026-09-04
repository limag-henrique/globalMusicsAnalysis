from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ImportErrorDetail:
    row_number: int
    field: str
    message: str


def parse_date(
    value: object, field: str, row_number: int
) -> tuple[date | None, ImportErrorDetail | None]:
    try:
        return date.fromisoformat(str(value)), None
    except (TypeError, ValueError):
        return None, ImportErrorDetail(row_number, field, f"invalid {field}")
