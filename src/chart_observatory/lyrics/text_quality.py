"""Versioned, conservative lyric derivatives; originals are never rewritten."""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

TEXT_QUALITY_VERSION = "lyrics-text-quality-v2"
_LETRAS_FOOTER = re.compile(
    r"(?:^|\n[ \t]*|(?<=\s))Adicionar aos favoritos\s+Adicionar à playlist\s+"
    r"Tamanho do texto\s+Cifra\s+(?:Imprimir\s+)?Corrigir\s+"
    r"(?:Enviar tradução\s+)?Rolagem automática"
    r"(?:\s+Anotações\s+Ativadas\s+Desativadas)?\s*$",
    re.IGNORECASE,
)
_SECOND_SECTION = re.compile(
    r"^\s*\[(?:Verse|Vers|Куплет|Ritornello|Verso|Estrofa)\s+2(?:[^\]]*)\]",
    re.IGNORECASE,
)
_ENTITY = re.compile(r"&#(?:[0-9]+|x[0-9a-fA-F]+);|&(?:amp|quot|apos|lt|gt|nbsp);")


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
    if _SECOND_SECTION.search(cleaned):
        flags.append("possible_missing_initial_section")
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
