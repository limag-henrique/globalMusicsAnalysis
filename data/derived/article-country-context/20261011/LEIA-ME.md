# Dados contextuais e cruzamentos exploratórios do artigo

Escopo: 68 mercados, 386 pares mercado/ano, 2017–2021 e 2022 até 13 de março. Cada indicador só é unido ao seu próprio ano.

| Cruzamento | Entrega e limite |
|---|---|
| Sexualidade × valores | WVS: acesso/download pendente; não há valores inventados. Composição de gêneros preservada por fonte em music-genre_variation. |
| Objetificação/misoginia × gênero | GII anual e SIGI na edição histórica disponível; SIGI não vira série anual. |
| Ostentação × economia | Gini, PIB per capita PPC constante e USD corrente, desemprego juvenil modelado pela OIT. Materialismo é a variável existente usada. |
| Violência × indicadores | UNODC: homicídios totais, femininos e por parceiro/família onde publicados. Homicídio feminino não equivale a feminicídio. |
| Pornografia × censura × sexualidade | Internet/banda larga e testes OONI históricos para pornhub.com, xvideos.com, xnxx.com. Sem métrica histórica de consumo/interesse: o cruzamento completo continua pendente. |
| Viralização × longevidade | Persistência do corpus exportada; falta exposição TikTok por música e data. Presença no Viral 50 não comprova impulso TikTok. |

## Cobertura de observações

| Indicador | Pares observados / previstos | Mercados com observação |
|---|---|---|
| fixed_broadband | 379 / 386 | 67 |
| gdp_pc_current_usd | 380 / 386 | 67 |
| gdp_pc_ppp_constant | 380 / 386 | 67 |
| gender_inequality_index | 372 / 386 | 65 |
| gini | 286 / 386 | 60 |
| homicide_unodc_female | 325 / 386 | 61 |
| homicide_unodc_female_intimate_partner | 206 / 386 | 42 |
| homicide_unodc_female_intimate_partner_family | 231 / 386 | 47 |
| homicide_unodc_total | 332 / 386 | 63 |
| homicide_wdi | 336 / 386 | 64 |
| internet_users | 380 / 386 | 67 |
| ooni_anomaly_count | 211 / 386 | 65 |
| ooni_anomaly_pct_valid_tests | 210 / 386 | 65 |
| ooni_confirmed_count | 211 / 386 | 65 |
| ooni_confirmed_pct_valid_tests | 210 / 386 | 65 |
| ooni_failure_count | 211 / 386 | 65 |
| ooni_measurement_count | 211 / 386 | 65 |
| ooni_ok_count | 211 / 386 | 65 |
| population | 380 / 386 | 67 |
| pornography_interest | 0 / 386 | 0 |
| sigi_2019 | 54 / 386 | 54 |
| tiktok_music_exposure | 0 / 386 | 0 |
| urban_population | 380 / 386 | 67 |
| wvs_sexual_values | 0 / 386 | 0 |
| youth_unemployment | 374 / 386 | 66 |

## Exemplos de associações disponíveis

Coeficientes descritivos sem ajuste; não confirmam as hipóteses do artigo. SIGI usa 2019 e os demais exemplos usam 2021.

| Cruzamento | Ano | Mercados | Spearman ρ |
|---|---|---|---|
| Objetificação × gênero | 2021 | 65 | 0.174 |
| Misoginia × gênero | 2021 | 65 | -0.326 |
| Objetificação × SIGI | 2019 | 54 | -0.067 |
| Misoginia × SIGI | 2019 | 54 | -0.429 |
| Ostentação × desigualdade | 2021 | 48 | -0.441 |
| Ostentação × renda | 2021 | 67 | 0.400 |
| Ostentação × desemprego | 2021 | 66 | 0.323 |
| Violência × homicídio | 2021 | 60 | -0.253 |
| Crime × homicídio | 2021 | 60 | -0.242 |
| Violência × homicídio feminino | 2021 | 59 | -0.228 |
| Violência × mortes por parceiro/família | 2021 | 39 | -0.110 |

## Leitura dos arquivos

country-context-observations contém dados longos, unidades, fonte, referência temporal, hash e arquivo bruto; coverage contém todas as células esperadas e seu status. country-year-crossings mantém os denominadores e prevalências do relatório original. Ausência é nula, nunca zero. Os arquivos possuem versões CSV e Parquet.

music-genre_variation e music-persistence conservam fonte e plataforma; os gêneros podem ser multirrótulo, portanto suas participações não precisam somar 100%. Persistência é limitada pela janela e frequência nativa; primeiro aparecimento não é data de lançamento e último aparecimento no corte não prova saída definitiva.

## Associações demonstrativas

exploratory-associations traz Spearman separado por ano, sem juntar anos como observações independentes. Usa mercados com ao menos 300 músicas classificadas e 10 pares válidos; relata mercados e cobertura. 2022 fica fora dessas associações por ter rankings parciais e indicadores posteriores ao corte. Não há valores-p ou afirmações confirmatórias; estas associações não ajustam gêneros, seleção do corpus ou compartilhamento de repertório entre mercados. São dados de circulação musical e indicadores agregados: não permitem inferência sobre indivíduos.

As classificações usadas são o retrato exploratório já existente, intensidade ≥2 na escala 0–3. Letras incorretamente ligadas, seleção de letras disponíveis, diferenças culturais de anotação e mistura Spotify Top 200/Viral 50 podem afetar resultados. É preciso definir uma análise principal por fonte/família e validar as classificações antes de conclusões para publicação.

OONI não é amostra representativa de pessoas ou redes. A fração de anomalias exclui testes que falharam e não representa bloqueio confirmado; confirmed e anomaly são contagens separadas. Sem testes retornados não significa acesso livre. A disponibilidade atual dos arquivos não faz de dados recentes medidas históricas.

## Reprodução

```powershell
uv run python scripts/import_article_context.py
uv run python scripts/report_article_context.py data/derived/article-country-context/20261011
```

Consultar manifest.json e sources-status.csv para fontes, bloqueios e falhas. Os dados brutos e hashes ficam em data/raw/country_context. Nenhum banco musical foi alterado.
