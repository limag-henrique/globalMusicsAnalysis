from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import streamlit as st

from chart_observatory.ui.data import (
    ManifestSummary,
    load_manifest_summary,
    load_optional_parquet,
    load_youtube_summary,
    manifest_metric_labels,
)
from chart_observatory.ui.source_inventory import load_capabilities, load_manifests

MANIFEST_PATH = Path("data/derived/corpus_v1_source_manifest.json")
COVERAGE_PATH = Path("data/derived/mgd_coverage.parquet")
ANALYTICAL_ROOT = Path("data/derived/analytical")
TURNOVER_PATH = ANALYTICAL_ROOT / "turnover_by_market_period.parquet"
GENRE_CLAIMS_PATH = ANALYTICAL_ROOT / "genre_claims.parquet"
GENRE_DIVERSITY_PATH = ANALYTICAL_ROOT / "genre_diversity_by_market_period.parquet"
YOUTUBE_PATH = Path("data/normalized/youtube_video_most_popular.parquet")


def _market_inventory() -> list[dict[str, str]]:
    return load_capabilities(Path("research/market_capabilities.csv"))


def _source_inventory() -> list[dict[str, str]]:
    return load_manifests(Path("research/mgd_source_manifest.json"))


def _load_manifest() -> tuple[ManifestSummary | None, dict[str, str] | None, str | None]:
    try:
        summary = load_manifest_summary(MANIFEST_PATH)
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return None, None, f"Não foi possível ler o manifesto {MANIFEST_PATH}: {error}"
    if not isinstance(payload, dict):
        return None, None, f"O manifesto {MANIFEST_PATH} não contém um objeto JSON."
    return summary, manifest_metric_labels(payload), None


def _artifact_frame(path: Path, label: str) -> pl.DataFrame | None:
    frame, status = load_optional_parquet(path)
    if status:
        st.warning(f"{label}: {status}")
        return None
    if frame.is_empty():
        st.info(f"{label}: o artefato está disponível, mas não contém linhas.")
        return None
    return frame


def _render_coverage() -> None:
    st.subheader("Cobertura e elegibilidade")
    coverage = _artifact_frame(COVERAGE_PATH, "Cobertura MGD")
    if coverage is None:
        return
    st.bar_chart(coverage, x="country_code", y="coverage_ratio")
    st.dataframe(coverage, use_container_width=True, hide_index=True)


def _render_turnover() -> None:
    st.subheader("Rotatividade entre períodos")
    turnover = _artifact_frame(TURNOVER_PATH, "Rotatividade")
    if turnover is None:
        return
    st.metric("Comparações mercado–período", f"{turnover.height:,}".replace(",", "."))
    st.dataframe(turnover, use_container_width=True, hide_index=True)


def _render_genres() -> None:
    st.subheader("Gêneros e diversidade")
    claims = _artifact_frame(GENRE_CLAIMS_PATH, "Claims de gênero")
    diversity = _artifact_frame(GENRE_DIVERSITY_PATH, "Diversidade de gênero")
    claim_column, diversity_column = st.columns(2)
    with claim_column:
        if claims is not None:
            st.metric("Claims normalizados", f"{claims.height:,}".replace(",", "."))
            st.dataframe(claims, use_container_width=True, hide_index=True)
    with diversity_column:
        if diversity is not None:
            st.metric("Períodos com diversidade", f"{diversity.height:,}".replace(",", "."))
            st.line_chart(diversity, x="year", y="shannon_entropy", color="country_code")
            st.dataframe(diversity, use_container_width=True, hide_index=True)


def _render_youtube() -> None:
    st.subheader("YouTube Video Most Popular")
    frame, status = load_optional_parquet(YOUTUBE_PATH)
    if status:
        st.warning(status)
        return
    if frame.is_empty():
        st.info("O artefato do YouTube está disponível, mas não contém linhas.")
        return
    summary = load_youtube_summary(YOUTUBE_PATH)
    observations, regions, videos = st.columns(3)
    observations.metric("Observações", f"{summary.observations:,}".replace(",", "."))
    regions.metric("Regiões", summary.markets)
    videos.metric("Vídeos", f"{summary.videos:,}".replace(",", "."))
    st.caption("NOT_YOUTUBE_MUSIC_TOP_SONGS")
    st.caption("Não equivale a uma parada de músicas mais tocadas do YouTube Music.")


def _render_freeze(summary: ManifestSummary, labels: dict[str, str]) -> None:
    st.subheader("Congelamento e proveniência")
    st.write(f"Manifesto: `{MANIFEST_PATH}`")
    st.write(f"Status: `{labels['freeze']}`")
    st.write(f"SHA-256: `{labels['manifest_sha256']}`")
    st.caption(
        f"Tipo: {summary.freeze_kind or 'não informado'} · "
        f"Congelado em: {summary.frozen_at or 'não informado'} · "
        f"Período: {summary.date_start or 'não informado'} a {summary.date_end or 'não informado'}"
    )


def _render_source_inventory() -> None:
    st.subheader("Inventário de fontes")
    capabilities_tab, sources_tab = st.tabs(["Capacidades de mercado", "Fontes de dados"])
    with capabilities_tab:
        inventory = _market_inventory()
        if inventory:
            st.dataframe(inventory, use_container_width=True, hide_index=True)
        else:
            st.info("Execute `chart-observatory sources coverage` para criar o inventário.")
    with sources_tab:
        sources = _source_inventory()
        if sources:
            st.dataframe(sources, use_container_width=True, hide_index=True)
        else:
            st.info("Execute `chart-observatory sources mgd inspect` para criar o inventário.")


def main() -> None:
    st.set_page_config(page_title="Chart Observatory · Corpus v1", layout="wide")
    st.title("Chart Observatory · Corpus v1")
    st.caption("Visão geral do corpus congelado e de seus artefatos analíticos.")

    summary, labels, error = _load_manifest()
    if error or summary is None or labels is None:
        st.warning(error or f"Manifesto indisponível: {MANIFEST_PATH}")
        _render_source_inventory()
        return

    observations, tracks, markets, freeze = st.columns(4)
    observations.metric("Observações", labels["observations"])
    tracks.metric("Faixas canônicas", labels["tracks"])
    markets.metric("Mercados elegíveis", labels["markets"])
    freeze.metric("Status do corpus", labels["freeze"])

    _render_coverage()
    _render_turnover()
    _render_genres()
    _render_youtube()
    _render_freeze(summary, labels)
    _render_source_inventory()


if __name__ == "__main__":
    main()
