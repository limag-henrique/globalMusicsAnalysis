# Painel histórico e piloto comercial

## Reprodução do painel

```powershell
uv run chart-observatory country-context historical-panel --annual data/derived/research_quality/country-all-history-20261011-022524/annual-country-metrics.csv --trends data/derived/country_context/trends-browser/trends-browser-observations.csv --context data/derived/article-country-context/20261011/country-year-crossings.parquet --output data/derived/article-country-context/historical-trends-20261011
```

11/10/2026: 68 mercados, 386 pares musicais país/ano, 383 séries de
termo/idioma/lote e 2.150 resumos anuais. country-year-music preserva os
denominadores. country-year-trends mantém cada série local separada.
CSV e Parquet são equivalentes; manifest.json registra hashes de entradas/saídas.

Trinta especificações dos dez temas: baseline, cobertura ≥70% e ajuste por
renda/internet. Vinte modelos estimados: baseline tem 60 mercados/295 pares;
adjusted, 59/290. A sensibilidade ≥70% não deixa quatro anos elegíveis por
mercado: dez modelos insuficientes, sem coeficientes. Não comprova robustez.

Âncora porn/en do menor lote lexicográfico por país, escolhida sem resultados
musicais. Padronização local calculada nos anos elegíveis de cada especificação;
não calibra níveis internacionais de consumo. Termos nativos permanecem no
painel descritivo e requerem revisão linguística antes de ampliar os modelos.

Médias ponderadas pelos dias de cada bucket. Semanas atravessando anos são
repartidas; buckets que excedem a janela são excluídos. <1 produz limites [0,1)
para dias observados; nenhum valor é imputado. 2022 parcial fica fora dos modelos;
Radar/2026 permanece separado. Consultar LEIA-ME.md, historical-coverage,
historical-associations, model-samples e model-exclusions.

OLS exploratória com efeitos de país/ano, erros agrupados por país e correção
BH na família de modelos estimados. Controles não estabelecem causalidade.
Poucos anos, seleção pela cobertura, classificação incerta e músicas compartilhadas
limitam a inferência. Erros por país não resolvem toda dependência entre mercados.

## Piloto comercial preparado

O usuário informou não ter acesso comercial; nenhuma chamada paga foi feita.
Primeiro adaptador: Semrush Trends Summary. Similarweb exigirá outro adaptador.

```powershell
uv run chart-observatory country-context traffic-pilot --annual data/derived/research_quality/country-all-history-20261011-022524/annual-country-metrics.csv --output data/derived/country_context/traffic-pilot
```

Plano: BR/US/GB/DE/JP, três domínios, 310 pedidos históricos; teto de 930
unidades Summary para todas as linhas possíveis. Confirmar condições comerciais.
2022 inclui só janeiro/fevereiro completos: não equivale ao corpus até 13/03.

Com acesso à **Semrush Trends API**, configurar SEMRUSH_API_KEY no .env.
Acesso à API SEO não basta. Primeira chamada limitada:

```powershell
uv run chart-observatory country-context traffic-pilot --annual data/derived/research_quality/country-all-history-20261011-022524/annual-country-metrics.csv --output data/derived/country_context/traffic-pilot --collect --limit 1
```

Cada execução retoma até --limit pedidos novos; sem --collect reconstrói arquivos
locais sem rede. raw guarda respostas e metadados sem chave. País, mês, domínio,
dispositivo all e hashes são validados; erros interrompem a coleta. monthly-visits
preserva zero, ausência e acesso pendente. annual-visits só soma períodos com
todos os meses planejados observados. Não somar domínios como pessoas únicas.
Integração testada com transporte simulado; conta comercial real ainda não validada.

Fontes: [Semrush Summary e custo por linha](https://developer.semrush.com/api/v3/trends/api-reference/),
[normalização do Google Trends](https://support.google.com/trends/answer/4365533?hl=pt-BR).
