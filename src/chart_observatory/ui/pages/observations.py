from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

import polars as pl
import streamlit as st

from chart_observatory.sources.catalog import CatalogFilters, catalog_source_paths
from chart_observatory.ui.classifications import JsonClassificationRepository
from chart_observatory.ui.data import (
    TrackDetail,
    filter_source_observations,
    load_track_detail,
)
from chart_observatory.ui.taxonomy import (
    CONTENT_TAXONOMY,
    TAXONOMY_VERSION,
    level_label,
)

MANIFEST_PATH = Path("data/derived/corpus_v1_source_manifest.json")
CLASSIFICATIONS_PATH = Path("data/runtime/content_classifications.json")
SURVIVAL_PATH = Path("data/derived/analytical/survival_by_track.parquet")
GENRE_CLAIMS_PATH = Path("data/derived/analytical/genre_claims.parquet")


def format_observation_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Translate query rows into the compact, human-readable table shown on the page."""
    state_labels = {"ANNOTATED": "Anotada", "UNANNOTATED": "Sem anotação"}
    return [
        {
            "Faixa": row.get("track_title") or "—",
            "Artista": row.get("artist") or "—",
            "Posição": row.get("rank") or "—",
            "Mercado": row.get("country_code") or "—",
            "Data": row.get("period_start") or "—",
            "Valor da métrica": (
                row["metric_value"] if row.get("metric_value") is not None else "—"
            ),
            "Classificação": state_labels.get(str(row.get("classification_state")), "—"),
            "ID nativo": row.get("native_id") or "—",
        }
        for row in rows
    ]


def format_source_catalog_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Translate the unified catalog into a source-aware research table."""
    state_labels = {"ANNOTATED": "Anotada", "UNANNOTATED": "Sem anotação"}
    return [
        {
            "Fonte": row.get("provider") or "—",
            "Plataforma": row.get("origin_platform") or "—",
            "Tipo": row.get("item_kind") or "—",
            "Mercado": row.get("market_code") or row.get("source_country_code") or "—",
            "Chart": row.get("chart_name") or "—",
            "Período": row.get("period_start") or "—",
            "Posição": row.get("rank") or "—",
            "Faixa/vídeo": row.get("track_title") or "—",
            "Artista/canal": row.get("artist") or row.get("channel_title") or "—",
            "Métrica": row.get("metric_value") if row.get("metric_value") is not None else "—",
            "Tipo de métrica": row.get("metric_type") or "—",
            "Visualizações": row.get("view_count") if row.get("view_count") is not None else "—",
            "ID nativo": row.get("native_id") or "—",
            "Artefato de origem": row.get("source_artifact") or "—",
            "Classificação": state_labels.get(str(row.get("classification_state")), "—"),
            "Equivalência": row.get("semantic_equivalence") or "—",
        }
        for row in rows
    ]


def _manifest_context() -> tuple[Path, list[str], date | None, date | None] | None:
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        observations = payload["observations"]
        observation_path = Path(observations["path"])
        markets = sorted(str(market) for market in payload.get("eligible_markets", []))
        return (
            observation_path,
            markets,
            date.fromisoformat(payload["date_start"]),
            date.fromisoformat(payload["date_end"]),
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _classification_ids() -> set[str] | None:
    try:
        repository = JsonClassificationRepository(CLASSIFICATIONS_PATH, TAXONOMY_VERSION)
        return {record.canonical_track_id for record in repository.list_all()}
    except ValueError as error:
        st.warning(f"Não foi possível ler as classificações locais: {error}")
        return None


def _selected_dates(start: date | None, end: date | None) -> tuple[date | None, date | None]:
    if start is None or end is None:
        st.caption("O manifesto não informa o período disponível.")
        return None, None
    selected = st.date_input("Período", value=(start, end), min_value=start, max_value=end)
    if isinstance(selected, tuple) and len(selected) == 2:
        return selected
    return start, end


def _render_detail(detail: TrackDetail, track_id: str) -> None:
    st.subheader("Detalhe da faixa")
    st.caption(
        f"{detail.track_title or 'Faixa sem título'} · {detail.artist or 'Artista não informado'}"
    )
    appearances, peak, mean_rank, duration, event = st.columns(5)
    appearances.metric("Aparições", detail.appearances)
    peak.metric("Melhor posição", detail.peak_rank)
    mean_rank.metric("Posição média", f"{detail.mean_rank:.1f}")
    duration.metric("Duração", detail.duration if detail.duration is not None else "—")
    event.metric("Evento de saída", detail.event if detail.event is not None else "—")

    markets, genres, classifications = st.columns(3)
    with markets:
        st.caption("Mercados")
        st.dataframe([{"Mercado": market} for market in detail.markets], hide_index=True)
    with genres:
        st.caption("Gêneros")
        st.dataframe([{"Gênero": genre} for genre in detail.genres], hide_index=True)
    with classifications:
        st.caption("Classificação")
        repository = JsonClassificationRepository(CLASSIFICATIONS_PATH, TAXONOMY_VERSION)
        try:
            classification = repository.get(track_id)
        except ValueError as error:
            st.warning(f"Classificação indisponível: {error}")
            return
        if classification is None:
            st.info("Sem anotação para esta faixa.")
            return
        st.dataframe(
            [
                {
                    "Dimensão": dimension.label,
                    "Nível": level_label(dimension.code, classification.scores[dimension.code]),
                }
                for dimension in CONTENT_TAXONOMY
            ],
            hide_index=True,
        )


def main() -> None:
    st.set_page_config(page_title="Observações · Chart Observatory", layout="wide")
    st.title("Observações")
    st.caption(
        "Consulta unificada às observações locais de MGD, Kaggle, Chartmetric, "
        "YouTube e Pro-Música."
    )

    context = _manifest_context()
    if context is None:
        st.warning("Não foi possível ler o manifesto do corpus para consultar as observações.")
        return
    observations_path, markets, date_start, date_end = context
    source_paths = catalog_source_paths(Path("."))
    if not source_paths:
        st.info("Nenhum artefato de fonte disponível para consulta.")
        return

    annotated_track_ids = _classification_ids()
    if annotated_track_ids is None:
        return

    filters_column, limit_column = st.columns((3, 1))
    with filters_column:
        market = st.text_input("País/mercado (ISO ou nome)", placeholder="Todos")
        provider = st.selectbox(
            "Fonte",
            [
                "Todos",
                "MGD",
                "KAGGLE_DHRUVILDAVE",
                "CHARTMETRIC",
                "YOUTUBE_DATA_API",
                "PRO_MUSICA_BRASIL",
            ],
        )
        chart_family = st.selectbox(
            "Família do chart",
            ["Todos", "TOP_200", "VIRAL_50", "YOUTUBE_VIDEO_MOST_POPULAR", "TOP_50_STREAMING"],
        )
        selected_year = st.number_input(
            "Ano (0 = todos)", min_value=0, max_value=2100, value=0, step=1
        )
        selected_start, selected_end = _selected_dates(date_start, date.today())
        max_rank = st.number_input("Melhor posição máxima", min_value=1, value=200, step=1)
        query = st.text_input("Faixa ou artista")
        classification = st.selectbox(
            "Estado da classificação",
            [None, "ANNOTATED", "UNANNOTATED"],
            format_func=lambda state: {
                None: "Todos",
                "ANNOTATED": "Anotada",
                "UNANNOTATED": "Sem anotação",
            }[state],
        )
    with limit_column:
        limit = st.number_input(
            "Limite de resultados", min_value=1, max_value=1_000, value=200, step=50
        )
        st.caption("Máximo de 1.000 linhas por consulta.")

    try:
        observations = filter_source_observations(
            source_paths,
            CatalogFilters(
                provider=None if provider == "Todos" else provider,
                country_code=market.strip() or None,
                year=int(selected_year) or None,
                date_start=selected_start,
                date_end=selected_end,
                max_rank=int(max_rank),
                chart_family=None if chart_family == "Todos" else chart_family,
                query=query,
                classification_state=classification,
                limit=int(limit),
            ),
            annotated_track_ids,
        )
    except (OSError, pl.exceptions.PolarsError) as error:
        st.warning(f"Não foi possível consultar as observações: {error}")
        return
    if observations.is_empty():
        st.info("Nenhuma observação corresponde aos filtros selecionados.")
        return

    rows = format_source_catalog_rows(observations.to_dicts())
    st.dataframe(rows, use_container_width=True, hide_index=True)
    track_ids = (
        observations.filter(pl.col("item_kind") == "TRACK")
        .get_column("native_id")
        .drop_nulls()
        .unique(maintain_order=True)
        .to_list()
    )
    if not track_ids:
        st.info("As linhas selecionadas não possuem detalhe de faixa disponível.")
        return
    track_id = st.selectbox("Faixa selecionada", track_ids)
    try:
        detail = load_track_detail(observations_path, SURVIVAL_PATH, GENRE_CLAIMS_PATH, track_id)
    except (OSError, pl.exceptions.PolarsError) as error:
        st.warning(f"Não foi possível carregar o detalhe da faixa: {error}")
        return
    if detail is None:
        st.info("Não há detalhe disponível para a faixa selecionada.")
        return
    _render_detail(detail, track_id)


if __name__ == "__main__":
    main()
