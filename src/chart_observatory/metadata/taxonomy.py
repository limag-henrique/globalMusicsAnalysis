from __future__ import annotations

import re
import unicodedata

LANGUAGE_ALIASES = {
    "pt-br": "pt",
    "por": "pt",
    "eng": "en",
    "spa": "es",
    "fra": "fr",
    "deu": "de",
    "ita": "it",
    "kor": "ko",
    "jpn": "ja",
    "ara": "ar",
    "hin": "hi",
    "ind": "id",
}


def _fold(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().strip().casefold(),
    )


def normalize_genre(raw_label: str) -> str:
    value = _fold(raw_label)
    if value in {"funk carioca", "baile funk", "brazilian funk", "funk brasileiro"}:
        return "FUNK_BR"
    if "sertanejo" in value:
        return "SERTANEJO_BR"
    if value in {"hip hop", "hip-hop", "rap", "melodic rap"} or "rap" in value:
        return "RAP_HIPHOP"
    if "reggaeton" in value or "urbano latino" in value:
        return "URBANO_LATINO"
    if value.startswith("pop") or value.endswith(" pop"):
        return "POP"
    if "country" in value:
        return "COUNTRY"
    if "rock" in value:
        return "ROCK"
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_").upper() or "UNKNOWN"


def normalize_language(raw_code: str) -> str:
    value = _fold(raw_code).replace("_", "-")
    normalized = LANGUAGE_ALIASES.get(value, value)
    if len(normalized) not in {2, 3}:
        raise ValueError(f"unsupported language code: {raw_code!r}")
    return normalized[:2]
