import re

from chart_observatory.domain.errors import DomainValidationError

_ISRC = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}\d{7}$")


def normalize_isrc(raw: str) -> str:
    normalized = raw.replace("-", "").replace(" ", "").upper()
    if not _ISRC.fullmatch(normalized):
        raise DomainValidationError(f"invalid ISRC: {raw!r}")
    return normalized
