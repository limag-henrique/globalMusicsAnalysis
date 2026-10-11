# Indicadores contextuais coletados em 11/10/2026

Coleta concluída para os 68 mercados selecionados do corpus musical.

- **Google Trends:** 81 CSVs originais exportados automaticamente no Edge,
  em inglês e nos idiomas locais selecionados. São 36.115 amostras por termo,
  incluindo 8.323 valores censurados `<1`, preservados sem imputação numérica.
  A janela varia conforme o histórico do mercado, entre 2017 e 13/03/2022.
- **Cloudflare Radar:** consultas para pornhub.com, xvideos.com e xnxx.com,
  de 01/09/2026 00:00 UTC a 01/10/2026 00:00 UTC. Houve 202 valores publicados
  entre 204 combinações mercado/domínio. Andorra e Islândia não foram retornadas
  para xnxx.com; esses valores permanecem ausentes.

## Arquivos

- `indicators.csv`: 36.319 linhas, unindo as fontes com país, termo/idioma ou
  domínio, período, escala, status e proveniência. Os indicadores ficam separados;
  não foi calculado um índice de consumo combinado.
- `country-coverage.csv`: 68 linhas com cobertura Trends, idiomas consultados e
  as três participações DNS, sem somar percentuais de domínios.
- `manifest.json`: contagens, limitações e hashes dos arquivos de entrada e saída.
- `../trends-browser/raw-browser/`: os 81 CSVs originais do Google.
- `../trends-browser/browser-downloads.json`: origem, datas e SHA-256 dos originais.
- `../trends-browser/browser-status.json`: confirmação dos 81 lotes e 68 mercados.
- `../recent/raw/`: respostas JSON originais da Cloudflare, incluindo metadados.

## Como interpretar

Trends mede interesse relativo de busca. Cada lote compara até cinco termos na
janela histórica inteira de um país. Os índices 0–100 compartilham escala apenas
no mesmo `comparison_group`; não se pode ordenar países pela média desses
índices. `year` identifica o ano da amostra, não uma nova normalização anual.
O termo `porn` é repetido como âncora entre lotes de países multilíngues; essas
repetições não devem ser somadas. Zero pode refletir baixo volume de buscas.

`aggregation` distingue mês e semana. `boundary_bucket=true` identifica um
mês/semana nominal que cruza o fim da janela solicitada. Março de 2022 é parcial.
O vocabulário local é provisório e precisa de revisão linguística; os seis idiomas
ainda sem vocabulário ficam explícitos em `../trends-browser/plan/language-gaps.csv`.

Radar mede a participação geográfica das consultas DNS ao resolvedor 1.1.1.1
para cada domínio, não visitas, usuários únicos ou prevalência populacional.
Comparações entre países só são feitas dentro do mesmo domínio e janela. O
denominador é global, sem renormalizar os percentuais para estes 68 mercados.
O DNS recente fica com `scope=recent`; Trends fica com `scope=corpus_history`.
Não associar setembro de 2026 às músicas históricas como observações simultâneas.

## Reprodução

Os comandos de coleta e importação estão em
`docs/operations/country-context-indicators.md`. O token Radar é lido do `.env`
ou do ambiente e não aparece nos resultados. O acesso direto automatizado aos
endpoints da interface Trends respondeu HTTP 429; a rota concluída utilizou os
controles de exportação do navegador conectado, sem acesso à API alfa.

Para reconstruir o arquivo unificado usando os dados locais:

```powershell
uv run python scripts/materialize_country_context.py
```
