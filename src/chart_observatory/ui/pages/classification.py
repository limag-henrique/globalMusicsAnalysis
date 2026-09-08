from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import streamlit as st

from chart_observatory.ui.classifications import (
    ContentClassification,
    JsonClassificationRepository,
)
from chart_observatory.ui.data import (
    ObservationFilters,
    build_classification_profile_from_mgd_observations,
    filter_mgd_observations,
)
from chart_observatory.ui.taxonomy import (
    CONTENT_TAXONOMY,
    TAXONOMY_VERSION,
)

MANIFEST_PATH = Path("data/derived/corpus_v1_source_manifest.json")
CLASSIFICATIONS_PATH = Path("data/runtime/content_classifications.json")
CATALOG_LIMIT = 1_000


def classification_form_values(
    record: ContentClassification | None,
) -> dict[str, int | None]:
    """Return a complete, non-mutating form state for the content taxonomy."""
    if record is None:
        return {dimension.code: None for dimension in CONTENT_TAXONOMY}
    return {
        dimension.code: record.scores.get(dimension.code)
        for dimension in CONTENT_TAXONOMY
    }


def profile_display_rows(frame: pl.DataFrame) -> list[dict[str, object]]:
    """Format the aggregate profile without conflating zero scores with missing data."""
    return [
        {
            "Mercado": row["country_code"],
            "Dimensão": row["category"],
            "Tracks classificadas": row["classified_track_count"],
            "Prevalência": f"{float(row['prevalence']) * 100:.1f}%".replace(".", ","),
            "Média": (
                "—"
                if row["mean_score"] is None
                else f"{float(row['mean_score']):.2f}/3".replace(".", ",")
            ),
        }
        for row in frame.sort(["country_code", "category"]).to_dicts()
    ]


def _classification_ids(repository: JsonClassificationRepository) -> set[str] | None:
    try:
        return {record.canonical_track_id for record in repository.list_all()}
    except ValueError as error:
        st.warning(f"Não foi possível ler as classificações locais: {error}")
        return None


def _observations_path() -> Path | None:
    if not MANIFEST_PATH.exists():
        st.warning(
            f"Parquet do corpus não encontrado via manifesto esperado: {MANIFEST_PATH}. "
            "Execute a preparação do Corpus v1 antes de classificar."
        )
        return None
    try:
        import json

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        observations_path = Path(manifest["observations"]["path"])
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        st.warning(f"Não foi possível localizar as observações no manifesto: {error}")
        return None
    if not observations_path.exists():
        st.warning(f"O Parquet de observações não está disponível: {observations_path}")
        return None
    return observations_path


def _catalog_rows(
    observations_path: Path, query: str, annotated_track_ids: set[str]
) -> pl.DataFrame | None:
    try:
        return filter_mgd_observations(
            observations_path,
            ObservationFilters(query=query, limit=CATALOG_LIMIT),
            annotated_track_ids,
        )
    except (OSError, pl.exceptions.PolarsError) as error:
        st.warning(f"Não foi possível consultar o catálogo de faixas: {error}")
        return None


def _track_options(catalog: pl.DataFrame) -> dict[str, str]:
    tracks = catalog.select("native_id", "track_title", "artist").unique(
        subset=["native_id"], maintain_order=True
    )
    return {
        row["native_id"]: (
            f"{row['track_title'] or 'Faixa sem título'} · "
            f"{row['artist'] or 'Artista não informado'} ({row['native_id']})"
        )
        for row in tracks.to_dicts()
    }


def _render_form(repository: JsonClassificationRepository, track_id: str) -> None:
    try:
        record = repository.get(track_id)
    except ValueError as error:
        st.warning(f"Classificação indisponível; o arquivo não será alterado: {error}")
        return

    values = classification_form_values(record)
    with st.form("classification-form"):
        selected_scores: dict[str, int | None] = {}
        for dimension in CONTENT_TAXONOMY:
            options = ["Sem anotação", *dimension.levels]
            current_score = values[dimension.code]
            selected_label = st.selectbox(
                dimension.label,
                options,
                index=0 if current_score is None else current_score + 1,
            )
            selected_scores[dimension.code] = (
                None if selected_label == "Sem anotação" else dimension.levels.index(selected_label)
            )
        reviewer = st.text_input("Revisor", value=record.reviewer if record else "")
        notes = st.text_area("Notas", value=record.notes if record else "")
        save = st.form_submit_button("Salvar classificação")

    if not save:
        return
    updated = ContentClassification(
        canonical_track_id=track_id,
        taxonomy_version=TAXONOMY_VERSION,
        scores=selected_scores,
        reviewer=reviewer,
        notes=notes,
        review_status="REVIEWED",
        updated_at=datetime.now(UTC),
    )
    try:
        repository.upsert(updated)
        repository.get(track_id)
    except ValueError as error:
        st.warning(f"Não foi possível salvar; o arquivo não foi substituído: {error}")
        return
    st.success("Classificação salva.")


def _render_profile(
    observations_path: Path, repository: JsonClassificationRepository
) -> None:
    st.subheader("Perfil por mercado e dimensão")
    try:
        classifications = repository.list_all()
    except ValueError as error:
        st.warning(f"Perfil indisponível; classificação local inválida: {error}")
        return
    try:
        profile = build_classification_profile_from_mgd_observations(
            observations_path, classifications
        )
    except (OSError, pl.exceptions.PolarsError) as error:
        st.warning(f"Perfil indisponível; não foi possível consultar o corpus: {error}")
        return
    st.dataframe(profile_display_rows(profile), use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Classificação · Chart Observatory", layout="wide")
    st.title("Classificação")
    st.caption("Anotação manual explícita; nenhum valor é salvo automaticamente.")

    repository = JsonClassificationRepository(CLASSIFICATIONS_PATH, TAXONOMY_VERSION)
    annotated_track_ids = _classification_ids(repository)
    if annotated_track_ids is None:
        return
    query = st.text_input("Buscar faixa ou artista")
    observations_path = _observations_path()
    if observations_path is None:
        return
    catalog = _catalog_rows(observations_path, query, annotated_track_ids)
    if catalog is None:
        return
    if catalog.is_empty():
        st.info("Nenhuma faixa corresponde à busca atual.")
        return
    st.caption(f"Catálogo limitado às primeiras {CATALOG_LIMIT} observações correspondentes.")
    options = _track_options(catalog)
    track_id = st.selectbox("Faixa selecionada", list(options), format_func=options.__getitem__)
    _render_form(repository, track_id)
    _render_profile(observations_path, repository)
    st.caption(
        "A escala registra a intensidade/centralidade do conteúdo observado nesta primeira "
        "versão; ela não estabelece independentemente o enquadramento (por exemplo, neutro "
        "ou glorificante). Ausência de letra não é tratada como ausência de conteúdo."
    )


if __name__ == "__main__":
    main()
