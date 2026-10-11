"""Describe coverage and exploratory annual associations from imported real data."""

import argparse
import json
from pathlib import Path

import polars as pl
from scipy.stats import spearmanr


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    panel = pl.read_parquet(args.output / "country-year-crossings.parquet")
    coverage = pl.read_parquet(args.output / "coverage.parquet")
    summary = (
        coverage.group_by("indicator_code")
        .agg(
            pl.len().alias("expected_country_years"),
            pl.col("value").is_not_null().sum().alias("observed_country_years"),
            pl.col("market_code")
            .filter(pl.col("value").is_not_null())
            .n_unique()
            .alias("observed_markets"),
        )
        .sort("indicator_code")
    )
    summary.write_csv(args.output / "indicator-coverage.csv")
    summary.write_parquet(args.output / "indicator-coverage.parquet")
    families = [
        ("Objetificação × gênero", "objectification_pct", "gender_inequality_index"),
        ("Misoginia × gênero", "misogyny_pct", "gender_inequality_index"),
        ("Objetificação × SIGI", "objectification_pct", "sigi_2019"),
        ("Misoginia × SIGI", "misogyny_pct", "sigi_2019"),
        ("Ostentação × desigualdade", "materialism_pct", "gini"),
        ("Ostentação × renda", "materialism_pct", "gdp_pc_ppp_constant"),
        ("Ostentação × desemprego", "materialism_pct", "youth_unemployment"),
        ("Violência × homicídio", "violence_pct", "homicide_unodc_total"),
        ("Crime × homicídio", "crime_pct", "homicide_unodc_total"),
        ("Violência × homicídio feminino", "violence_pct", "homicide_unodc_female"),
        (
            "Violência × mortes por parceiro/família",
            "violence_pct",
            "homicide_unodc_female_intimate_partner_family",
        ),
    ]
    records = []
    for label, music, contextual in families:
        if contextual not in panel.columns:
            continue
        for year in sorted(panel["year"].unique().to_list()):
            # Partial 2022 musical year has contextual data from later months.
            if year == 2022:
                continue
            sample = (
                panel.filter((pl.col("year") == year) & (pl.col("classified_tracks") >= 300))
                .select("market_code", "coverage", music, contextual)
                .drop_nulls()
            )
            rho = None
            if (
                sample.height >= 10
                and sample[music].n_unique() > 1
                and sample[contextual].n_unique() > 1
            ):
                rho = float(spearmanr(sample[music], sample[contextual]).statistic)
            records.append(
                {
                    "crossing": label,
                    "music_indicator": music,
                    "context_indicator": contextual,
                    "year": year,
                    "n_markets": sample.height,
                    "spearman_rho": rho,
                    "min_classification_coverage": sample["coverage"].min(),
                    "median_classification_coverage": sample["coverage"].median(),
                    "status": "exploratory_unadjusted"
                    if rho is not None
                    else "insufficient_variation_or_n",
                    "sample_markets": ";".join(sorted(sample["market_code"].to_list())),
                }
            )
    correlations = pl.from_dicts(records, infer_schema_length=None)
    correlations.write_csv(args.output / "exploratory-associations.csv")
    correlations.write_parquet(args.output / "exploratory-associations.parquet")
    brazil = panel.filter(pl.col("market_code") == "BR").sort("year")
    brazil.write_csv(args.output / "brazil-crossings.csv")
    manifest = json.loads((args.output / "manifest.json").read_text(encoding="utf-8"))
    lines = [
        "# Dados contextuais e cruzamentos exploratórios do artigo",
        "",
        f"Escopo: {len(manifest['markets'])} mercados, {panel.height} pares mercado/ano, "
        "2017–2021 e 2022 até 13 de março. Cada indicador só é unido ao seu próprio ano.",
        "",
        "| Cruzamento | Entrega e limite |",
        "|---|---|",
        "| Sexualidade × valores | WVS: acesso/download pendente; não há valores inventados. "
        "Composição de gêneros preservada por fonte em music-genre_variation. |",
        "| Objetificação/misoginia × gênero | GII anual e SIGI na edição histórica disponível; "
        "SIGI não vira série anual. |",
        "| Ostentação × economia | Gini, PIB per capita PPC constante e USD corrente, "
        "desemprego juvenil modelado pela OIT. Materialismo é a variável existente usada. |",
        "| Violência × indicadores | UNODC: homicídios totais, femininos e por parceiro/família "
        "onde publicados. Homicídio feminino não equivale a feminicídio. |",
        "| Pornografia × censura × sexualidade | Internet/banda larga e testes OONI históricos "
        "para pornhub.com, xvideos.com, xnxx.com. Sem métrica histórica de consumo/interesse: "
        "o cruzamento completo continua pendente. |",
        "| Viralização × longevidade | Persistência do corpus exportada; falta exposição TikTok "
        "por música e data. Presença no Viral 50 não comprova impulso TikTok. |",
        "",
        "## Cobertura de observações",
        "",
        "| Indicador | Pares observados / previstos | Mercados com observação |",
        "|---|---|---|",
    ]
    for r in summary.iter_rows(named=True):
        lines.append(
            f"| {r['indicator_code']} | {r['observed_country_years']} / "
            f"{r['expected_country_years']} | {r['observed_markets']} |"
        )
    lines += [
        "",
        "## Exemplos de associações disponíveis",
        "",
        "Coeficientes descritivos sem ajuste; não confirmam as hipóteses do artigo. "
        "SIGI usa 2019 e os demais exemplos usam 2021.",
        "",
        "| Cruzamento | Ano | Mercados | Spearman ρ |",
        "|---|---|---|---|",
    ]
    for r in correlations.iter_rows(named=True):
        if r["spearman_rho"] is None:
            continue
        if (r["year"] == 2021 and r["context_indicator"] != "sigi_2019") or (
            r["year"] == 2019 and r["context_indicator"] == "sigi_2019"
        ):
            lines.append(
                f"| {r['crossing']} | {r['year']} | {r['n_markets']} | {r['spearman_rho']:.3f} |"
            )
    lines += [
        "",
        "## Leitura dos arquivos",
        "",
        "country-context-observations contém dados longos, unidades, fonte, referência temporal, "
        "hash e arquivo bruto; coverage contém todas as células esperadas e seu status. "
        "country-year-crossings mantém os denominadores e prevalências do relatório original. "
        "Ausência é nula, nunca zero. Os arquivos possuem versões CSV e Parquet.",
        "",
        "music-genre_variation e music-persistence conservam fonte e plataforma; os gêneros "
        "podem ser multirrótulo, portanto suas participações não precisam somar 100%. "
        "Persistência é limitada pela janela e frequência nativa; primeiro aparecimento não "
        "é data de lançamento e último aparecimento no corte não prova saída definitiva.",
        "",
        "## Associações demonstrativas",
        "",
        "exploratory-associations traz Spearman separado por ano, sem juntar anos como "
        "observações independentes. Usa mercados com ao menos 300 músicas classificadas e "
        "10 pares válidos; relata mercados e cobertura. 2022 fica fora dessas associações "
        "por ter rankings parciais e indicadores posteriores ao corte. Não há valores-p "
        "ou afirmações confirmatórias; estas associações não ajustam gêneros, seleção do "
        "corpus ou compartilhamento de repertório entre mercados. São dados de circulação "
        "musical e indicadores agregados: não permitem inferência sobre indivíduos.",
        "",
        "As classificações usadas são o retrato exploratório já existente, intensidade ≥2 "
        "na escala 0–3. Letras incorretamente ligadas, seleção de letras disponíveis, "
        "diferenças culturais de anotação e mistura Spotify Top 200/Viral 50 podem afetar "
        "resultados. É preciso definir uma análise principal por fonte/família e validar "
        "as classificações antes de conclusões para publicação.",
        "",
        "OONI não é amostra representativa de pessoas ou redes. A fração de anomalias "
        "exclui testes que falharam e não representa bloqueio confirmado; confirmed e "
        "anomaly são contagens separadas. Sem testes retornados não significa acesso livre. "
        "A disponibilidade atual dos arquivos não faz de dados recentes medidas históricas.",
        "",
        "## Reprodução",
        "",
        "```powershell",
        "uv run python scripts/import_article_context.py",
        "uv run python scripts/report_article_context.py "
        "data/derived/article-country-context/20261011",
        "```",
        "",
        "Consultar manifest.json e sources-status.csv para fontes, bloqueios e falhas. "
        "Os dados brutos e hashes ficam em data/raw/country_context. "
        "Nenhum banco musical foi alterado.",
    ]
    (args.output / "LEIA-ME.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "country_years": panel.height,
                "associations": correlations.height,
                "brazil_years": brazil.height,
            }
        )
    )


if __name__ == "__main__":
    main()
