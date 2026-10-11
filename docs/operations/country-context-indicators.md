# Coleta contextual: Google Trends e Cloudflare Radar

## Resultado inicial

`data/derived/country_context/initial/` contém plano e matriz de cobertura para os
68 mercados do relatório musical, sem números de consumo inventados. O plano
seleciona anos efetivamente presentes no CSV anual. Termos locais são candidatos
que precisam de revisão linguística. `language-gaps.csv` registra idiomas ainda
sem vocabulário, em vez de apresentar a lista como cobertura de todos os idiomas.

O CSV `indicators.csv` contém uma linha por consulta pendente ou por amostra de
Trends importada; DNS contém uma linha por mercado/domínio/janela. Não é uma
tabela com uma única nota nacional. `query_id` relaciona as medições ao plano.
Campos `status`, `scale`, `raw_sha256`, `scope` e datas preservam a interpretação.

## Comandos

Gerar plano sem chamadas externas:

```powershell
uv run chart-observatory country-context export --annual data/derived/research_quality/country-all-history-20261011-022524/annual-country-metrics.csv --output data/derived/country_context/initial
```

Alternativa equivalente: `uv run python -m chart_observatory.analysis.country_context`.

### Google Trends

A API oficial está em alfa com acesso restrito. Autenticação Google Cloud para
Gemini não comprova acesso ao Trends. Não há contrato público suficiente para
implementar um cliente oficial verificável nesta sessão. A alternativa acordada
é importar CSVs originais da interface do Google, não pytrends ou outra API informal.

1. Abra `source_url` de uma linha de `query-plan.csv` e exporte **Interesse ao
   longo do tempo**, mantendo país, termo, período, categoria geral e busca web.
2. Registre o arquivo em um manifesto JSON. `date_column` e `value_column` devem
   ser os nomes exatos das colunas exportadas, inclusive em interfaces traduzidas.
3. Informe SHA-256 dos bytes originais (`Get-FileHash arquivo.csv -Algorithm SHA256`;
   converta a saída para minúsculas). `path` é relativo ao manifesto. Não edite o CSV.

Exemplo de estrutura; substitua os valores pelo registro real do plano:

```json
[
  {
    "query_id": "ID_DO_PLANO",
    "path": "trends-br-porn-2021.csv",
    "date_column": "Week",
    "value_column": "porn: (Brazil)",
    "sha256": "HASH_SHA256_EM_MINUSCULAS",
    "source_url": "URL_EXATA_DO_PLANO",
    "exported_at": "2026-10-10T20:00:00Z"
  }
]
```

```powershell
uv run chart-observatory country-context export --annual data/derived/research_quality/country-all-history-20261011-022524/annual-country-metrics.csv --output data/derived/country_context/imported --trends-manifest caminho/exports.json
```

Suporte inicial: séries temporais com datas ISO diárias ou semanais. Exportações
mensais, rankings regionais e comparações de várias consultas requerem adaptadores
próprios; não são reinterpretados silenciosamente. Cada arquivo deve corresponder
a uma consulta do plano. A URL declarada permite verificar metadados, mas não
comprova que o usuário deixou os filtros corretos na interface.

Índices preservam 0–100; `<1` fica censurado, sem imputação. Zero pode significar
baixo volume, não ausência de pesquisas. Não se faz média de termos, soma entre
idiomas nem comparação de médias de séries locais entre países. As amostras são
as fornecidas pelo exportador; ausência de semanas não é tratada como zero nem
como cobertura anual completa. Consultas antigas podem não ter dados disponíveis.

### Cloudflare Radar

Use um token com permissão de leitura do Radar em `CLOUDFLARE_API_TOKEN`, no
ambiente do processo ou no `.env` da raiz. Nenhum token é gravado nos resultados. O comando só usa o
token com `--collect-radar`. Exemplo de janela separada da análise histórica:

```powershell
uv run chart-observatory country-context export --annual data/derived/research_quality/country-all-history-20261011-022524/annual-country-metrics.csv --output data/derived/country_context/recent --collect-radar --radar-start 2026-09-01 --radar-end 2026-10-01
```

Datas DNS são UTC; `radar-end` é limite inclusivo, conforme o contrato da API. Janelas por domínio não excedem
31 dias. A resposta é validada quanto a sucesso, escala percentual, valores e
período retornado. Respostas brutas ficam em `raw/`. Erros HTTP interrompem a
coleta e exigem retomada explícita; não são convertidos em medidas zero.

Painel inicial: pornhub.com, xvideos.com e xnxx.com. Não representa a indústria
inteira nem captura todos os domínios regionais. País não retornado fica
`not_returned`, pois a lista top pode ser truncada ou não publicar o país.
Comparação permitida: participação entre países **do mesmo domínio e janela**.
`cross_country_comparable=true` tem exclusivamente esse significado para DNS,
não comparabilidade de consumo per capita. Não somar as parcelas dos domínios.

## Automação do Google Trends (11/10/2026)

Foi autorizada a automação em inglês e nos idiomas locais. Há duas rotas:

```powershell
uv run chart-observatory country-context collect-trends --annual data/derived/research_quality/country-all-history-20261011-022524/annual-country-metrics.csv --output data/derived/country_context/trends-direct --interval 8
```

Essa rota usa os endpoints da interface pública, não a API alfa oficial. A origem
é `google_trends_web_unofficial`. Checkpoints permitem retomar sem repetir consultas
concluídas. Um erro HTTP interrompe a rodada. Na execução desta sessão, houve HTTP
429 na primeira consulta; não foram utilizados proxies, cookies extraídos do
navegador ou tentativas de contornar CAPTCHA.

A rota que funcionou nesta sessão foi exportação automatizada de CSVs originais
no Edge conectado. Prepare ou consolide a fila com:

```powershell
uv run chart-observatory country-context trends-browser --annual data/derived/research_quality/country-all-history-20261011-022524/annual-country-metrics.csv --output data/derived/country_context/trends-browser
```

`browser-queue.json` contém 81 lotes para 68 mercados, até cinco termos por lote.
O lote cobre a janela histórica inteira daquele mercado e repete `porn` como
âncora. Exportações são realizadas pelos controles de download do gráfico na
sessão conectada do navegador, com intervalo entre navegações. O comando acima
prepara/importa arquivos; a interação do navegador é feita pelo agente via CUA.
Não afirmar que o comando CLI sozinho realiza downloads de navegador.

Para importar novos downloads, passe `--downloads arquivo.json`, onde o arquivo
contém uma lista de objetos `{"batch_id": "ID_DA_FILA", "path": "CAMINHO_DO_CSV"}`.
`browser-downloads.json` mantém a proveniência e SHA-256 dos originais copiados.
`browser-status.json` registra a cobertura. Reexecutar sem `--downloads` reconstrói
o consolidado utilizando os arquivos já registrados, sem acessar a rede.

`trends-browser-observations.csv` preserva termos em inglês/idiomas locais,
censura `<1`, país, ano da amostra, datas da janela completa, agregação e
`comparison_group`. Índices compartilham escala apenas dentro do mesmo lote.
Não misturar essa escala com séries anuais individuais nem somar as âncoras
repetidas. Meses/semanas próximos ao fim de março de 2022 requerem atenção ao
período parcial; não interpretar esse trecho como o ano inteiro.

## Resultado da execução

A coleta pelo navegador concluiu os 81 lotes dos 68 mercados, com 36.115
amostras, incluindo 8.323 valores `<1`. Radar retornou 202 das 204 combinações;
Andorra e Islândia não foram publicadas para xnxx.com. O token do `.env` foi
utilizado com sucesso. Os dados completos estão em
`data/derived/country_context/collected/indicators.csv`, e a cobertura por mercado
em `data/derived/country_context/collected/country-coverage.csv`.

Reconstrua o consolidado local sem acessar as APIs:

```powershell
uv run python scripts/materialize_country_context.py
```

### Reprodução e análise musical

`manifest.json` registra hashes da entrada anual, do manifesto Trends e dos CSVs
gerados. Arquivos originais importados são copiados para `raw/`. Dados recentes
têm `scope=recent`, enquanto o Trends planejado tem `scope=corpus_history`.
Mantenha a janela parcial de 2022 (até 13/03) visível. Para uma futura correlação,
use períodos realmente compatíveis e um método de calibração validado; este
pipeline não calcula prevalência, visitas por habitante ou correlação causal.

Documentação primária:

- https://developers.google.com/search/apis/trends
- https://support.google.com/trends/answer/4365533?hl=pt-BR
- https://developers.cloudflare.com/radar/investigate/dns/
- https://developers.cloudflare.com/api/resources/radar/subresources/dns/subresources/top/methods/locations/
