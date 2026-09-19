from __future__ import annotations

from pathlib import Path

import polars as pl


def article_methodology_markdown() -> str:
    """Explain the corpus construction and the current article-analysis boundary."""

    return """### Procedimento realizado até aqui

**Unidade de análise.** A unidade científica é a gravação musical. O
`canonical_track_id` identifica a gravação resolvida; uma observação de chart
continua vinculada à sua fonte, plataforma, mercado, período, posição e métrica.
Vídeos do YouTube são itens distintos e não são tratados automaticamente como
faixas.

**Aquisição e preservação.** Foram inventariadas as fontes e seus direitos/capacidades;
o MGD foi normalizado como Spotify Top 200 histórico (2017-01-01 a 2022-03-13,
68 mercados, 21.257.472 observações). O Kaggle Spotify Charts foi importado para
validação (26.173.514 observações, 70 regiões), o Pro-Música Brasil teve inventário
de 6 itens e captura pública de 50 linhas, e o YouTube Data API produziu o snapshot
atual de 111 regiões (3.037 observações, 1.678 vídeos distintos). O Chartmetric
permanece somente em piloto histórico, sem backfill longitudinal concluído.

**Reconciliação.** A resolução prioriza ID Spotify/ISRC exato; similaridade de
título/artista não confirma uma identidade sozinha. O `track_master` atual tem
**126.213 faixas canônicas**. O catálogo unificado preserva **47.434.073
observações**, separadas por fonte (47.431.036 de faixas e 3.037 de vídeos). A
**deduplicação completa entre fontes ainda está pendente**: equivalências não são
apagadas, e as fontes continuam rastreáveis.

**Elegibilidade e análises.** Foram aplicados cobertura mínima de 95%, pelo menos
3 anos e profundidade mediana mínima de 100; 55 de 68 células foram elegíveis.
As saídas materializadas medem permanência, turnover/renovação do Top-N, variação
de gêneros e distância Jensen–Shannon. Viralidade permanece no nível de vídeo.
Prevalência de conteúdo exclui células sem anotação do denominador, e os resultados
são associações descritivas, não evidência causal.

**Letras e Gemini.** A camada de letras usa fontes em cascata e registra fonte,
status, versão textual e auditoria; correspondências ambíguas não são aceitas.
O Gemini recebe a letra inteira, com linhas numeradas, e retorna JSON estruturado
com idioma, tradução, dimensões semânticas, evidências e indicadores de qualidade.
O processamento é incremental e append-only: faixas concluídas são puladas e erros
podem ser retomados. O pipeline usa Vertex AI com Application Default Credentials
(ADC), obtidas pelo ambiente Google Cloud, sem chave de API do Gemini.

**Limitações atuais.** O conjunto canônico não é a soma deduplicada final de todas
as fontes; YouTube mede vídeos atuais, Chartmetric histórico ainda não foi
completado, e letras/anotações dependem de cobertura e autorização da fonte.
`GLOBAL` não deve ser interpretado como país. Toda tabela do artigo deve informar
fonte, período, denominador, faltantes e versão do artefato."""


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
    with st.expander("Procedimento realizado e status do corpus", expanded=False):
        st.markdown(article_methodology_markdown())
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
