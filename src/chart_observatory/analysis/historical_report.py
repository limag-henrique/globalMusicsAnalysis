"""Reproduce the historical article deliverable from preserved real observations."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from chart_observatory.analysis.historical_models import export_historical_models
from chart_observatory.analysis.historical_panel import export_historical_panel


def build_historical_report(
    annual: Path,
    trends: Path,
    output: Path,
    *,
    context: Path | None = None,
) -> dict[str, Any]:
    music = pl.read_csv(annual)
    if context:
        contextual = (
            pl.read_parquet(context) if context.suffix == ".parquet" else pl.read_csv(context)
        )
        controls = [c for c in ["internet_users", "gdp_pc_ppp_constant"] if c in contextual.columns]
        music = music.join(
            contextual.select("market_code", "year", *controls),
            on=["market_code", "year"],
            how="left",
            validate="1:1",
        )
    observations = pl.read_csv(trends, infer_schema_length=None)
    observations = observations.filter(pl.col("source") == "google_trends_export")
    status = export_historical_panel(music, observations, output)
    panel = pl.read_parquet(output / "country-year-trends.parquet")
    model_status = export_historical_models(panel, output)
    coverage = (
        panel.group_by("market_code", "year")
        .agg(
            pl.len().alias("term_batch_series"),
            pl.col("mean_index").is_not_null().sum().alias("uncensored_series"),
            pl.col("temporal_coverage").min().alias("minimum_temporal_coverage"),
            pl.col("partial_year").any().alias("partial_year"),
            pl.col("classified_tracks").first(),
            pl.col("coverage").first(),
        )
        .sort("market_code", "year")
    )
    coverage.write_csv(output / "historical-coverage.csv")
    models = pl.read_parquet(output / "historical-associations.parquet")
    lines = [
        "# Painel histórico para o artigo",
        "",
        f"{status['countries']} mercados; {status['country_years']} pares musicais país/ano; "
        f"{status['series_years']} resumos anuais de termos/lotes.",
        "",
        "country-year-music mantém uma linha e os denominadores por país/ano. "
        "country-year-trends mantém termos, idiomas e lotes separados, "
        "com períodos, cobertura, censura e hashes. Não há nota nacional de consumo.",
        "",
        "Médias são ponderadas por dias dos buckets disponíveis. Semanas em dezembro "
        "são repartidas entre anos; buckets que excedem a janela são excluídos. "
        "<1 contribui apenas para limites [0,1); não se calcula média pontual "
        "nessas séries. Limites não cobrem dias ausentes. Zero não prova ausência de buscas.",
        "",
        "## Associações exploratórias",
        "",
        "Os modelos usam apenas porn/en do menor lote lexicográfico por país, "
        "2017–2021 completos, ≥300 faixas, ≥80% cobertura temporal e ≥4 anos "
        "elegíveis por país. Índices são padronizados dentro da série local "
        "(média zero e desvio populacional um). A unidade é mudança na "
        "prevalência musical, em pontos percentuais, por um desvio local do Trends. "
        "A padronização não calibra níveis de consumo entre países.",
        "",
        "OLS com efeitos fixos de país/ano e erros agrupados por país (intervalos t). "
        "baseline exige cobertura musical ≥50%; coverage70 ≥70%; adjusted exige "
        "≥50% e controla log da renda PPC e usuários de internet do mesmo ano. "
        "Modelos exigem ≥20 países e matriz de desenho identificável. "
        "q é Benjamini–Hochberg para a família de todos os modelos estimados. "
        "Não há ponderação pelo tamanho da população ou número de músicas.",
        "",
        "| Tema | Especificação | Países | Pares | Coeficiente | IC 95% | q BH | Estado |",
        "|---|---|---:|---:|---:|---|---:|---|",
    ]
    for r in models.to_dicts():
        coef = f"{r['coefficient']:.3f}" if r["coefficient"] is not None else "—"
        ci = f"[{r['ci_lower']:.3f}, {r['ci_upper']:.3f}]" if r["ci_lower"] is not None else "—"
        q = f"{r['q_value_bh']:.3f}" if r["q_value_bh"] is not None else "—"
        lines.append(
            f"| {r['outcome']} | {r['specification']} | {r['n_countries']} | "
            f"{r['n_country_years']} | {coef} | {ci} | {q} | {r['status']} |"
        )
    lines.extend(
        [
            "",
            "## Limitações",
            "",
            "Resultados são associações agregadas exploratórias. Poucos anos, seleção "
            "de países pela cobertura, incerteza da classificação das letras, diferenças "
            "linguísticas e músicas compartilhadas entre mercados limitam a inferência. "
            "Erros agrupados por país não resolvem toda dependência entre mercados. "
            "Controlar renda e internet não estabelece causalidade. Consultar model-samples "
            "e model-exclusions antes de interpretar mudanças entre especificações. "
            "Só a âncora em inglês entra nos modelos: termos nativos ficam no painel "
            "para descrição e futura validação linguística.",
            "",
            "2022 até 13/03 fica descritivo e fora dos modelos. Radar de setembro/2026 "
            "permanece separado. Não há visitas comerciais observadas: o piloto Semrush "
            "está em acesso pendente; nenhum valor foi substituído por zero.",
            "",
            "## Reprodução",
            "",
            "Consultar docs/operations/historical-trends-panel.md. Os arquivos anteriores "
            "do artigo e os downloads originais permanecem preservados. Este relatório "
            "atualiza o estado da coleta histórica do Trends; relatórios anteriores "
            "podem ainda descrevê-la como pendente.",
        ]
    )
    (output / "LEIA-ME.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    inputs = [annual, trends, *([context] if context else [])]
    manifest = {
        **status,
        **model_status,
        "created_at": datetime.now(UTC).isoformat(),
        "schema_version": "historical-trends-v1",
        "inputs": [
            {"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in inputs
        ],
        "outputs": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.iterdir())
            if p.suffix in {".csv", ".parquet", ".md"}
        },
        "commercial_access": "pending",
        "raw_cross_country_comparisons": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {**status, **model_status}
