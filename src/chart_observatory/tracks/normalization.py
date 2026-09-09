import re
import unicodedata

from chart_observatory.domain.errors import DomainValidationError

_ISRC = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}\d{7}$")


def normalize_isrc(raw: str) -> str:
    normalized = raw.replace("-", "").replace(" ", "").upper()
    if not _ISRC.fullmatch(normalized):
        raise DomainValidationError(f"invalid ISRC: {raw!r}")
    return normalized


def normalize_text(raw: str) -> str:
    decomposed = unicodedata.normalize("NFKD", raw)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.casefold()).strip()


def normalize_artist(raw: str) -> str:
    return normalize_text(raw)
