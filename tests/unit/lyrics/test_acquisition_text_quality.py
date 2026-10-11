from __future__ import annotations

import json

import httpx
import pytest

from chart_observatory.lyrics.genius_client import GeniusClient
from chart_observatory.lyrics.letras_client import LetrasClient


def test_genius_fetch_preserves_first_verse_after_nested_metadata() -> None:
    html = """<div data-lyrics-container="true"><div>2 Contributors</div>
        [Verse 1]<br>First complete verse with enough words<br>Another line</div>
        <div data-lyrics-container="true">[Verse 2]<br>Second complete verse</div>"""
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=html))
    ) as http:
        lyrics = GeniusClient(http_client=http).fetch("Example", "Artist")

    assert lyrics == (
        "[Verse 1]\nFirst complete verse with enough words\nAnother line\n"
        "[Verse 2]\nSecond complete verse"
    )


def test_letras_fetch_returns_lyrics_without_terminal_interface_footer() -> None:
    html = """<div class="lyric-original"><p>One complete lyric line</p>
        <p>Another complete lyric line</p>
        Adicionar aos favoritos Adicionar à playlist Tamanho do texto Cifra Imprimir
        Corrigir Rolagem automática Anotações Ativadas Desativadas</div><div></div>"""
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=html))
    ) as http:
        lyrics = LetrasClient(http_client=http).fetch("Example", "Artist")

    assert lyrics == "One complete lyric line\n\nAnother complete lyric line"


def test_letras_embedded_json_preserves_unicode_and_decodes_numeric_entities() -> None:
    html = (
        '<script type="application/json">'
        + json.dumps(
            {"lyrics": "Canção com &#39;acentos&#39; e emoção\nOutro verso completo"},
            ensure_ascii=False,
        )
        + "</script>"
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=html))
    ) as http:
        lyrics = LetrasClient(http_client=http).fetch("Example", "Artist")

    assert lyrics == "Canção com 'acentos' e emoção\nOutro verso completo"


@pytest.mark.parametrize(
    "footer",
    [
        "Adicionar aos favoritos Adicionar à playlist Tamanho do texto Cifra Corrigir "
        "Rolagem automática Anotações Ativadas Desativadas",
        "Adicionar aos favoritos Adicionar à playlist Tamanho do texto Cifra Imprimir Corrigir "
        "Enviar tradução Rolagem automática Anotações Ativadas Desativadas",
    ],
)
def test_letras_fetch_removes_observed_terminal_footer_variants(footer: str) -> None:
    html = (
        '<div class="lyric-original">First complete lyric line<br>Second complete lyric line<br>'
        + footer
        + "</div>"
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=html))
    ) as http:
        lyrics = LetrasClient(http_client=http).fetch("Example", "Artist")

    assert lyrics == "First complete lyric line\nSecond complete lyric line"
