from __future__ import annotations

from pathlib import Path

import polars as pl


def market_anxiety_summary(frame: pl.DataFrame) -> pl.DataFrame:
    """Rank markets by average Top-N turnover and rank displacement."""
    schema = {
        "market_code": pl.String,
        "mean_turnover_rate": pl.Float64,
        "mean_rank_displacement": pl.Float64,
        "periods": pl.UInt32,
    }
    if frame.height == 0:
        return pl.DataFrame(schema=schema)
    required = {"market_code", "turnover_rate", "mean_rank_displacement"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"market anxiety summary is missing columns: {sorted(missing)}")
    return (
        frame.group_by("market_code")
        .agg(
            pl.col("turnover_rate").mean().alias("mean_turnover_rate"),
            pl.col("mean_rank_displacement").mean().alias("mean_rank_displacement"),
            pl.len().alias("periods"),
        )
        .select(list(schema))
        .sort("mean_turnover_rate", descending=True)
    )


def _read_optional(name: str) -> pl.DataFrame | None:
    path = Path("data/derived/article") / f"{name}.parquet"
    if not path.is_file():
        return None
    return pl.read_parquet(path)


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Análises do artigo · Chart Observatory", layout="wide")
    st.title("Análises do artigo")
    st.caption(
        "Resultados descritivos por mercado. Associação não implica causalidade;"
        " fontes e períodos mantêm suas semânticas nativas."
    )
    anxiety = _read_optional("market_anxiety")
    if anxiety is None:
        st.info("Dados ainda não disponíveis. Execute corpus analytics.")
    else:
        st.subheader("Permanência e ansiedade de mercado")
        summary = market_anxiety_summary(anxiety)
        st.dataframe(summary.to_dicts(), use_container_width=True, hide_index=True)
        st.bar_chart(summary.to_pandas().set_index("market_code")["mean_turnover_rate"])

    persistence = _read_optional("persistence")
    if persistence is not None and persistence.height:
        st.subheader("Permanência das faixas")
        st.line_chart(
            persistence.group_by("market_code")
            .agg(pl.col("native_periods").mean().alias("mean_native_periods"))
            .sort("market_code")
            .to_pandas()
            .set_index("market_code")
        )

    genre = _read_optional("genre_variation")
    if genre is not None and genre.height:
        st.subheader("Variação e dispersão de gêneros")
        st.dataframe(genre.to_dicts(), use_container_width=True, hide_index=True)
        chart = (
            genre.group_by("year", "genre")
            .agg(pl.col("genre_share").mean().alias("genre_share"))
            .pivot(index="year", on="genre", values="genre_share")
            .sort("year")
        )
        st.line_chart(chart.to_pandas().set_index("year"))

    content = _read_optional("content_prevalence")
    if content is not None and content.height:
        st.subheader("Conteúdo das letras")
        st.dataframe(content.to_dicts(), use_container_width=True, hide_index=True)
    elif content is None:
        st.info("Letras/anotações autorizadas ainda não foram carregadas.")

    virality = _read_optional("virality_features")
    if virality is not None and virality.height:
        st.subheader("Viralidade")
        st.dataframe(virality.to_dicts(), use_container_width=True, hide_index=True)
    else:
        st.info("Vínculos de viralidade ainda não foram fornecidos.")


if __name__ == "__main__":
    main()
