"""Versioned, conservative lyric derivatives; originals are never rewritten."""

from __future__ import annotations

import hashlib
import html
import math
import re
import unicodedata
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

TEXT_QUALITY_VERSION = "lyrics-text-quality-v5"
_LETRAS_FOOTER = re.compile(
    r"(?:^|\n[ \t]*|(?<=\s))Adicionar aos favoritos\s+Adicionar à playlist\s+"
    r"Tamanho do texto\s+Cifra\s+(?:Imprimir\s+)?Corrigir\s+"
    r"(?:Enviar tradução\s+)?Rolagem automática"
    r"(?:\s+Anotações\s+Ativadas\s+Desativadas)?\s*$",
    re.IGNORECASE,
)
_SECTION_HEADER = re.compile(r"^\s*\[([^\]]{1,80})\]\s*$", re.IGNORECASE)
_NON_INITIAL_SECTION = re.compile(
    r"^(?:pre[- ]?chorus|post[- ]?chorus|chorus|refrain|hook|bridge|outro|breakdown|"
    r"(?:verse|vers|verso|ritornello|estrofa|couplet|куплет|主歌)\s*"
    r"(?:[2-9]|[ivxlcdm]+|二|三|四|五))",
    re.IGNORECASE,
)
_ENTITY = re.compile(r"&#(?:[0-9]+|x[0-9a-fA-F]+);|&(?:amp|quot|apos|lt|gt|nbsp);")

_PARTIAL_TEXT = re.compile(
    r"only a portion|lyrics snippet|see full lyrics|remaining lyrics|"
    r"(?:apenas|somente) (?:um )?trecho da letra|"
    r"(?:ver|veja|ler) (?:a )?letra completa|"
    r"(?:ver|leer) (?:la )?letra completa",
    re.IGNORECASE,
)


def recording_duration_mismatch(native_ms, provider_seconds):
    """Flag only a measurable discrepancy; missing/invalid values prove nothing."""
    if (
        not isinstance(native_ms, int)
        or isinstance(native_ms, bool)
        or native_ms <= 0
        or not isinstance(provider_seconds, (int, float))
        or isinstance(provider_seconds, bool)
    ):
        return False
    try:
        expected, observed = native_ms / 1000, float(provider_seconds)
    except (OverflowError, ValueError):
        return False
    return (
        math.isfinite(expected)
        and math.isfinite(observed)
        and observed > 0
        and abs(expected - observed) > max(3, expected * 0.02)
    )


def has_partial_lyrics_notice(text: str) -> bool:
    """Detect explicit preview notices, without inferring missing verses."""
    return bool(_PARTIAL_TEXT.search(text))


def _normalized_lyric_line(line: str) -> str:
    value = unicodedata.normalize("NFKD", line).casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = "".join(ch if ch.isalnum() else " " for ch in value)
    return " ".join(value.split())


def _starts_at_non_initial_section(lines: list[str]) -> bool:
    for line in lines:
        if not line.strip():
            continue
        match = _SECTION_HEADER.match(line)
        return bool(match and _NON_INITIAL_SECTION.match(match.group(1).strip()))
    return False


def _refrain_only_pattern(lines: list[str]) -> bool:
    lyric_lines = [
        normalized
        for line in lines
        if not _SECTION_HEADER.match(line)
        and (normalized := _normalized_lyric_line(line))
    ]
    if len(lyric_lines) < 8:
        return False
    counts: dict[str, int] = {}
    for line in lyric_lines:
        counts[line] = counts.get(line, 0) + 1
    repeated_characters = sum(len(line) * (count - 1) for line, count in counts.items())
    total_characters = sum(len(line) * count for line, count in counts.items())
    return (
        len(counts) <= 8
        and total_characters >= 240
        and total_characters > 0
        and repeated_characters / total_characters >= 0.55
    )


@dataclass(frozen=True)
class LyricTextDerivative:
    text: str
    original_sha256: str
    derivative_sha256: str
    transformations: tuple[str, ...]
    flags: tuple[str, ...]
    version: str = TEXT_QUALITY_VERSION

    @property
    def changed(self) -> bool:
        return self.original_sha256 != self.derivative_sha256


def outer_lyric_containers(containers: list[Tag]) -> list[Tag]:
    """Keep nested sections in their parent, without reading them a second time."""
    identities = {id(node) for node in containers}
    return [node for node in containers if not any(id(p) in identities for p in node.parents)]


def prepare_lyric_derivative(text: str, source: str) -> LyricTextDerivative:
    """Remove only known encoding/UI artifacts; do not infer missing verses."""
    original_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    transformations: list[str] = []
    flags: list[str] = []
    cleaned = text
    if source.upper() == "LETRAS":
        cleaned, count = _LETRAS_FOOTER.subn("", cleaned)
        if count:
            cleaned = cleaned.rstrip()
            transformations.append("terminal_letras_footer_removed")
    if _ENTITY.search(cleaned):
        decoded = html.unescape(cleaned)
        if decoded != cleaned:
            transformations.append("html_entities_decoded")
            cleaned = decoded
    if "Adicionar aos favoritos" in cleaned and "Rolagem automática" in cleaned:
        flags.append("remaining_interface_residue")
    if _ENTITY.search(cleaned):
        flags.append("remaining_encoded_entity")
    if has_partial_lyrics_notice(cleaned):
        flags.append("explicit_partial_lyrics_notice")
    if _starts_at_non_initial_section(cleaned.splitlines()):
        flags.append("possible_missing_initial_section")
    if re.search(r"\bYou might also like\b", cleaned, re.IGNORECASE):
        flags.append("remaining_interface_residue")
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if _refrain_only_pattern(lines):
        flags.append("suspected_refrain_only")
    if len(lines) >= 12 and len(lines) % 2 == 0:
        midpoint = len(lines) // 2
        if lines[:midpoint] == lines[midpoint:]:
            flags.append("suspected_duplicated_container_halves")
    if len(cleaned.strip()) < 100:
        flags.append("very_short_text")
    elif len(cleaned.strip()) < 300:
        flags.append("short_text")
    if not cleaned.strip():
        flags.append("empty_after_cleaning")
    return LyricTextDerivative(
        cleaned,
        original_hash,
        hashlib.sha256(cleaned.encode("utf-8")).hexdigest(),
        tuple(transformations),
        tuple(flags),
    )


def html_lyric_text(element: Tag) -> str:
    """Read a complete DOM container, retaining line and paragraph boundaries."""
    for node in element.find_all(["script", "style", "button", "nav"]):
        node.decompose()
    for node in element.find_all("br"):
        node.replace_with("\n")
    for node in element.find_all(["p", "div"]):
        node.append("\n\n" if node.name == "p" else "\n")
    value = element.get_text()
    value = "\n".join(line.strip() for line in value.splitlines())
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def html_fragment_text(value: str) -> str:
    return html_lyric_text(BeautifulSoup(value, "html.parser"))
