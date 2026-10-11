# Painel histórico para o artigo

68 mercados; 386 pares musicais país/ano; 2150 resumos anuais de termos/lotes.

country-year-music mantém uma linha e os denominadores por país/ano. country-year-trends mantém termos, idiomas e lotes separados, com períodos, cobertura, censura e hashes. Não há nota nacional de consumo.

Médias são ponderadas por dias dos buckets disponíveis. Semanas em dezembro são repartidas entre anos; buckets que excedem a janela são excluídos. <1 contribui apenas para limites [0,1); não se calcula média pontual nessas séries. Limites não cobrem dias ausentes. Zero não prova ausência de buscas.

## Associações exploratórias

Os modelos usam apenas porn/en do menor lote lexicográfico por país, 2017–2021 completos, ≥300 faixas, ≥80% cobertura temporal e ≥4 anos elegíveis por país. Índices são padronizados dentro da série local (média zero e desvio populacional um). A unidade é mudança na prevalência musical, em pontos percentuais, por um desvio local do Trends. A padronização não calibra níveis de consumo entre países.

OLS com efeitos fixos de país/ano e erros agrupados por país (intervalos t). baseline exige cobertura musical ≥50%; coverage70 ≥70%; adjusted exige ≥50% e controla log da renda PPC e usuários de internet do mesmo ano. Modelos exigem ≥20 países e matriz de desenho identificável. q é Benjamini–Hochberg para a família de todos os modelos estimados. Não há ponderação pelo tamanho da população ou número de músicas.

| Tema | Especificação | Países | Pares | Coeficiente | IC 95% | q BH | Estado |
|---|---|---:|---:|---:|---|---:|---|
| explicitness_pct | baseline | 60 | 295 | -0.683 | [-1.181, -0.186] | 0.032 | exploratory_country_year_fixed_effects |
| explicitness_pct | coverage70 | 0 | 0 | — | — | — | insufficient_countries |
| explicitness_pct | adjusted | 59 | 290 | -0.552 | [-1.072, -0.031] | 0.109 | exploratory_country_year_fixed_effects |
| objectification_pct | baseline | 60 | 295 | -0.292 | [-0.597, 0.012] | 0.148 | exploratory_country_year_fixed_effects |
| objectification_pct | coverage70 | 0 | 0 | — | — | — | insufficient_countries |
| objectification_pct | adjusted | 59 | 290 | -0.239 | [-0.567, 0.089] | 0.272 | exploratory_country_year_fixed_effects |
| misogyny_pct | baseline | 60 | 295 | -0.021 | [-0.215, 0.173] | 0.885 | exploratory_country_year_fixed_effects |
| misogyny_pct | coverage70 | 0 | 0 | — | — | — | insufficient_countries |
| misogyny_pct | adjusted | 59 | 290 | -0.015 | [-0.215, 0.186] | 0.885 | exploratory_country_year_fixed_effects |
| materialism_pct | baseline | 60 | 295 | -0.633 | [-1.069, -0.197] | 0.032 | exploratory_country_year_fixed_effects |
| materialism_pct | coverage70 | 0 | 0 | — | — | — | insufficient_countries |
| materialism_pct | adjusted | 59 | 290 | -0.670 | [-1.117, -0.223] | 0.032 | exploratory_country_year_fixed_effects |
| infidelity_pct | baseline | 60 | 295 | -0.115 | [-0.257, 0.028] | 0.226 | exploratory_country_year_fixed_effects |
| infidelity_pct | coverage70 | 0 | 0 | — | — | — | insufficient_countries |
| infidelity_pct | adjusted | 59 | 290 | -0.102 | [-0.264, 0.060] | 0.352 | exploratory_country_year_fixed_effects |
| casual_sex_pct | baseline | 60 | 295 | -0.578 | [-1.079, -0.076] | 0.082 | exploratory_country_year_fixed_effects |
| casual_sex_pct | coverage70 | 0 | 0 | — | — | — | insufficient_countries |
| casual_sex_pct | adjusted | 59 | 290 | -0.449 | [-1.000, 0.102] | 0.226 | exploratory_country_year_fixed_effects |
| transactional_sex_pct | baseline | 60 | 295 | -0.028 | [-0.087, 0.030] | 0.495 | exploratory_country_year_fixed_effects |
| transactional_sex_pct | coverage70 | 0 | 0 | — | — | — | insufficient_countries |
| transactional_sex_pct | adjusted | 59 | 290 | -0.031 | [-0.095, 0.034] | 0.495 | exploratory_country_year_fixed_effects |
| drugs_alcohol_pct | baseline | 60 | 295 | -0.648 | [-1.068, -0.227] | 0.032 | exploratory_country_year_fixed_effects |
| drugs_alcohol_pct | coverage70 | 0 | 0 | — | — | — | insufficient_countries |
| drugs_alcohol_pct | adjusted | 59 | 290 | -0.606 | [-1.048, -0.165] | 0.032 | exploratory_country_year_fixed_effects |
| violence_pct | baseline | 60 | 295 | -0.038 | [-0.435, 0.358] | 0.885 | exploratory_country_year_fixed_effects |
| violence_pct | coverage70 | 0 | 0 | — | — | — | insufficient_countries |
| violence_pct | adjusted | 59 | 290 | -0.089 | [-0.494, 0.316] | 0.778 | exploratory_country_year_fixed_effects |
| crime_pct | baseline | 60 | 295 | -0.123 | [-0.585, 0.340] | 0.746 | exploratory_country_year_fixed_effects |
| crime_pct | coverage70 | 0 | 0 | — | — | — | insufficient_countries |
| crime_pct | adjusted | 59 | 290 | -0.167 | [-0.629, 0.295] | 0.629 | exploratory_country_year_fixed_effects |

## Limitações

Resultados são associações agregadas exploratórias. Poucos anos, seleção de países pela cobertura, incerteza da classificação das letras, diferenças linguísticas e músicas compartilhadas entre mercados limitam a inferência. Erros agrupados por país não resolvem toda dependência entre mercados. Controlar renda e internet não estabelece causalidade. Consultar model-samples e model-exclusions antes de interpretar mudanças entre especificações. Só a âncora em inglês entra nos modelos: termos nativos ficam no painel para descrição e futura validação linguística.

2022 até 13/03 fica descritivo e fora dos modelos. Radar de setembro/2026 permanece separado. Não há visitas comerciais observadas: o piloto Semrush está em acesso pendente; nenhum valor foi substituído por zero.

## Reprodução

Consultar docs/operations/historical-trends-panel.md. Os arquivos anteriores do artigo e os downloads originais permanecem preservados. Este relatório atualiza o estado da coleta histórica do Trends; relatórios anteriores podem ainda descrevê-la como pendente.
