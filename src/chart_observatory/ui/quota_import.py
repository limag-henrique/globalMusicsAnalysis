"""Read-only human browsing of pending country/year lyric imports."""

import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pycountry
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from chart_observatory.config import Settings
from chart_observatory.ingestion.import_quotas import load_quotas
from chart_observatory.lyrics.staging_review import (
    browse_pending,
    coverage_for_run,
    list_snapshots,
    pending_detail,
)


@st.cache_resource
def review_engine():
    return create_engine(Settings.load(Path.cwd()).database_url, pool_pre_ping=True)


def snapshot_label(snapshot):
    date = datetime.fromisoformat(snapshot["created_at"])
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)
    return (
        date.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
        + " · "
        + snapshot["run_id"][:10]
    )


@st.cache_data(max_entries=4, show_spinner="Conferindo cobertura do snapshot...")
def review_coverage(run_id, quotas):
    return coverage_for_run(review_engine(), quotas, run_id=run_id)


def quotas_for_snapshot(snapshot):
    root = Path.cwd().resolve()
    source = Path(snapshot["manifest"].get("selection_root", "")).resolve()
    path = source / "sources/country_quotas.csv"
    return load_quotas(path) if source.is_relative_to(root) and path.exists() else {}


def countries_for_snapshot(snapshot):
    quotas = quotas_for_snapshot(snapshot)
    return sorted(quotas) if quotas else sorted(country.alpha_2 for country in pycountry.countries)


def source_link(detail):
    result = detail["source_result"]
    metadata = result.get("source_metadata") or {}
    url = metadata.get("url")
    if result.get("source") == "LRCLIB" and isinstance(metadata.get("id"), int):
        url = f"https://lrclib.net/api/get/{metadata['id']}"
    if not isinstance(url, str):
        return None
    parsed = urlparse(url)
    if (
        parsed.scheme == "https"
        and not parsed.username
        and parsed.hostname
        in {
            "genius.com",
            "www.genius.com",
            "www.letras.mus.br",
            "letras.mus.br",
            "www.azlyrics.com",
            "www.musixmatch.com",
            "lrclib.net",
        }
    ):
        return url
    return None


def render_quota_import():
    st.title("Importação por cotas · 2018–2026")
    st.caption(
        "Corte em 15/10/2026. Letras e atribuições aguardam conferência; "
        "classificação paga não liberada."
    )
    try:
        engine = review_engine()
        snapshots = list_snapshots(engine)
    except SQLAlchemyError:
        st.error("Não foi possível consultar o banco local.")
        return
    if not snapshots:
        st.info("Ainda não há snapshots da importação pendente neste banco.")
        return
    by_id = {snapshot["run_id"]: snapshot for snapshot in snapshots}
    selected = st.selectbox(
        "Snapshot do banco", list(by_id), format_func=lambda key: snapshot_label(by_id[key])
    )
    snapshot = by_id[selected]
    manifest = snapshot["manifest"]
    columns = st.columns(3)
    columns[0].metric("Candidatas", f"{manifest['candidates']:,}".replace(",", "."))
    columns[1].metric("Com texto", f"{manifest['text_candidates']:,}".replace(",", "."))
    columns[2].metric("Textos distintos", f"{manifest['unique_texts']:,}".replace(",", "."))
    filters = st.columns(4)
    codes = ["Todos", *countries_for_snapshot(snapshot)]
    country = filters[0].selectbox("País", codes, index=codes.index("BR") if "BR" in codes else 0)
    year = filters[1].selectbox("Ano", ["Todos", *range(2018, 2027)], index=9)
    text_filter = filters[2].selectbox("Letra", ["Todas", "Com texto", "Sem texto"])
    page = int(filters[3].number_input("Página", min_value=1, value=1, step=1))
    query = st.text_input("Buscar título, artista ou ID")
    if st.button("Atualizar consulta"):
        st.rerun()
    try:
        result = browse_pending(
            engine,
            run_id=selected,
            country=None if country == "Todos" else country,
            year=None if year == "Todos" else year,
            has_text=None if text_filter == "Todas" else text_filter == "Com texto",
            query=query,
            limit=50,
            offset=(page - 1) * 50,
        )
    except SQLAlchemyError:
        st.error("A consulta ao snapshot não pôde ser concluída.")
        return
    if quotas := quotas_for_snapshot(snapshot):
        try:
            coverage = review_coverage(selected, quotas)
        except SQLAlchemyError:
            coverage = None
            st.warning("Não foi possível consultar a cobertura das cotas.")
        if coverage:
            cells = [
                row
                for row in coverage["cells"]
                if (country == "Todos" or row["country_code"] == country)
                and (year == "Todos" or row["year"] == year)
            ]
            with st.expander("Cobertura das cotas por país e ano", expanded=True):
                st.caption("Cobertura da seleção, independente da busca e do filtro de letras.")
                metrics = st.columns(3)
                metrics[0].metric("Posições previstas", sum(row["quota"] for row in cells))
                metrics[1].metric(
                    "Sem música no ranking",
                    sum(len(row["missing_ranking_positions"]) for row in cells),
                )
                metrics[2].metric(
                    "Selecionadas sem letra",
                    sum(len(row["missing_text_positions"]) for row in cells),
                )
                st.dataframe(
                    [
                        dict(
                            País=row["country_code"],
                            Ano=row["year"],
                            Cota=row["quota"],
                            Selecionadas=row["selected_positions"],
                            Provisórias=row["provisional_positions"],
                            Com_texto=row["positions_with_text"],
                            Sem_ranking=len(row["missing_ranking_positions"]),
                            Sem_letra=len(row["missing_text_positions"]),
                        )
                        for row in cells
                    ],
                    hide_index=True,
                    width="stretch",
                )
    st.caption(
        f"{result['total']} candidatas correspondem aos filtros. "
        "As posições usam as métricas observadas nos charts."
    )
    st.caption(
        "Calendário completo não certifica o ranking anual fora dos limites dos charts. "
        "Seleções provisórias usam apenas os períodos disponíveis."
    )
    if not result["rows"]:
        st.info("Nenhuma candidata nesta página. Confira os filtros ou volte à página 1.")
        return
    rows = result["rows"]
    st.dataframe(
        [
            dict(
                Posição=min((b["position"] for b in row["bindings"]), default=None),
                Música=row["title"] or "Nome pendente",
                Artista=row["artist"] or "A identificar",
                Seleção=(
                    "Provisória"
                    if any(
                        b.get("selection_status") == "PROVISIONAL_OBSERVED_PERIODS"
                        for b in row["bindings"]
                    )
                    else "Calendário elegível"
                ),
                Letra="Disponível para revisão" if row["has_text"] else "Não localizada",
            )
            for row in rows
        ],
        hide_index=True,
        width="stretch",
    )
    labels = {
        row[
            "candidate_id"
        ]: f"{row['title'] or 'Nome pendente'} · {row['artist'] or 'A identificar'}"
        for row in rows
    }
    candidate = st.selectbox(
        "Música para conferir", list(labels), format_func=lambda key: labels.get(key, key)
    )
    try:
        detail = pending_detail(engine, candidate, run_id=selected)
    except ValueError:
        st.error("O texto armazenado não passou na conferência do hash.")
        return
    except SQLAlchemyError:
        st.error("Não foi possível abrir esta candidata.")
        return
    if not detail:
        st.info("A candidata não está disponível neste snapshot.")
        return
    source = detail["source_result"].get("source", "A identificar")
    st.subheader(labels[candidate])
    st.caption(f"Fonte registrada: {source} · atribuição e completude pendentes")
    if previous := detail["source_result"].get("replaced_unverified_result"):
        st.info(
            "Alternativa recuperada para uma letra anteriormente sinalizada. "
            "O registro anterior foi preservado; a transcrição ainda precisa de conferência."
        )
        st.caption(
            f"Fonte anterior: {previous.get('source', 'A identificar')} · "
            f"Hash anterior: {previous.get('text_sha256', 'Não informado')}"
        )
    if url := source_link(detail):
        st.link_button("Abrir fonte da letra", url)
    native = candidate.removeprefix("SPOTIFY:")
    if candidate.startswith("SPOTIFY:") and re.fullmatch(r"[A-Za-z0-9]{22}", native):
        st.link_button("Faixa no Spotify", f"https://open.spotify.com/track/{native}")
    if detail["audit"].get("source_quarantined"):
        st.warning(
            "A fonte está em quarentena. A correspondência com a gravação precisa ser conferida."
        )
    if detail["text"] is None:
        st.info("A letra ainda não foi localizada nesta importação.")
    else:
        st.code(detail["text"], language=None, wrap_lines=True, height=500)
        st.caption(
            "Integridade do arquivo conferida pelo hash. "
            "Isso não certifica a transcrição da gravação."
        )
    with st.expander("Posições e evidências"):
        st.dataframe(detail["payload"].get("chart_bindings", []), hide_index=True, width="stretch")
        st.json(detail["audit"])
    if detail.get("alternatives"):
        st.warning(
            "As fontes apresentam letras diferentes. As alternativas abaixo aguardam conferência."
        )
        for index, alternative in enumerate(detail["alternatives"], 1):
            with st.expander(
                f"Alternativa {index} · {alternative.get('source', 'Fonte desconhecida')}"
            ):
                if alternative.get("error"):
                    st.error("Não foi possível conferir a evidência local desta alternativa.")
                    continue
                if url := source_link({"source_result": alternative}):
                    st.link_button(f"Abrir fonte da alternativa {index}", url)
                st.code(alternative["text"], language=None, wrap_lines=True, height=500)
                st.caption(f"SHA256 conferido: {alternative['text_sha256']}")
