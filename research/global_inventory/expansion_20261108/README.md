# Incorporação operacional mundial — 08/11/2026

**Etapa histórica posterior:** [incorporação anual no PostgreSQL](../../../docs/operations/global-annual-incorporation-20261108.md).
Ela registra todas as 2.250 células e 92.000 vínculos observados, com as lacunas
explícitas. O lote de snapshots descrito abaixo permanece separado dos anos.

O inventário tem 250 países/territórios (249 ISO e XK como exceção documentada).
Foram calculadas **242 cotas**, somando **30.850 posições por ano**. Os oito
territórios sem população adequadamente documentada permanecem no inventário,
com cota nula e bloqueio explícito: AQ, BV, GS, HM, IO, SJ, TF e UM. Nulo não
significa população zero. SJ requer resolver a abrangência Svalbard/Jan Mayen.

As **68 cotas anteriores foram preservadas exatamente**. A extensão usa o mesmo
coeficiente 7,470872933481587, raiz quadrada da população em milhões, multiplicador
histórico de diversidade, piso de 100, teto de 500 e passos de dez:

`min(500, 100 + 10 × floor(7,470872933481587 × sqrt(população/1.000.000) × (1 + 0,5 × diversidade) / 10))`

O coeficiente não foi recalibrado para diminuir artificialmente os novos países.
Diversidade ausente recebe multiplicador neutro explicitamente marcado; não é
registrada como diversidade observada igual a zero. O indicador histórico de
Alesina não descreve a composição demográfica atual. Não foram transferidos
valores de países extintos a seus sucessores, nem combinadas Gaza e Cisjordânia.

A base prioritária é a [população 2024 do Banco Mundial](https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?date=2024&format=json&per_page=400),
com suplemento da [WPP 2024 da ONU](https://population.un.org/wpp/downloads).
Na WPP, o valor de 2024 está identificado como projeção, em milhares, convertido
para habitantes. As exceções censitárias de 2021 e a contagem de Pitcairn de 2022
mantêm seus anos reais. Taiwan mantém a referência oficial anterior de fim de
2024. As fontes específicas e os valores estão em `population_evidence.json`.
Os insumos congelados estão em `../inputs_20261108`, com hashes em
`input_integrity.json`. A diversidade vem do XLS histórico já existente em
`research/annual_allocation_alesina_original_20261030.xls`, SHA-256
`50f08c149be7d9c53d41bc02278ba88b0fb5a5aa25582bcc0982bb1a0f6905d0`.

Exemplos de cotas anuais: Índia 440, China 400, Nigéria 260, Brasil 230,
Etiópia 210, Quênia 180 e Egito 180. São quantidades de posições desejadas,
nunca uma afirmação de disponibilidade de rankings completos.

## Extração iniciada e primeiro lote concluído

Foram extraídos **5.400 registros de posições em 54 países/territórios**:
52 Top 100 nacionais diários da Apple, o Top 100 composto da TurnTable na
Nigéria e o Top 100 semanal da Mdundo no Quênia. Há sete mercados africanos
neste lote. A contagem inclui a mesma gravação em países diferentes; não é
uma contagem de músicas distintas. As 54 capturas foram reprocessadas a partir
dos HTMLs originais, com verificação de hashes e 5.400 posições aprovadas.

`ranked_titles.jsonl` contém país, fonte, período, posição ordinal explícita,
nome, artista e identificador/URL da fonte. `extraction_results.json` contém
as capturas, datas, hashes, cotas e diferenças de profundidade. O primeiro lote
tem déficit agregado de **2.290 posições** contra suas cotas: essas fontes
publicam somente 100 posições por mercado. Não se inventaram posições 101–440.

O número `position` é a posição publicada no ranking nacional da fonte. Não é
uma posição global, posição de similaridade, nem posição recalculada depois da
seleção. Títulos e identificadores são evidências de identidade do provedor;
não autorizam fusão automática de gravações ou classificação de letras.

Capturas diárias e semanais permanecem separadas. A TurnTable combina streaming
e rádio; a geografia da audiência Mdundo ainda requer revisão. A semana da
Mdundo não tem intervalo de datas certificado na página. A data de criação da
TurnTable é preservada como publicada, sem inferir começo/fim da semana.
**Nenhuma captura atual foi promovida a ranking anual de 2018–2026.**

`annual_admission_queue.json` registra as 2.250 células país/ano e a necessidade
de calendário anual completo, métrica comparável e adjudicação de identidade.
2026 continua parcial. `source_admission_plan.json` incorpora as 27 rotas
investigadas e distingue adaptadores atuais das fontes pendentes. Rankings
regionais não são replicados como nacionais. Circle, fontes restritas e rotas
sem acesso/calendário verificado continuam bloqueadas para importação automática.

## Execução e armazenamento

Na raiz do repositório, usando o ambiente Python do projeto:

```powershell
.venv/Scripts/python.exe scripts/incorporate_global_rankings.py
.venv/Scripts/python.exe scripts/incorporate_global_rankings.py --collect
.venv/Scripts/python.exe scripts/incorporate_global_rankings.py --collect --retry-held
.venv/Scripts/python.exe scripts/incorporate_global_rankings.py --verify-cached
```

O primeiro comando recompõe os arquivos demográficos e a política sem rede.
O segundo faz requisições HTTP públicas, sequenciais, com intervalo mínimo de
um segundo, sem áudio ou letras. O terceiro retoma somente capturas pendentes.
O último revalida os arquivos brutos sem rede.

Os HTMLs e a base SQLite de evidências ficam em
`data/runtime/global-expansion-20261108/`. A tabela `captures_v2` é aditiva;
a captura inicial foi preservada, inclusive antes da correção de normalização
da URL absoluta da Mdundo. A política e os resultados revisáveis estão nesta
pasta. O corpus canônico e o PostgreSQL real não foram modificados. Os workers
antigos não foram redirecionados para uma campanha expirada ou para evidências
atuais sem calendário anual certificado.

Não houve chamadas pagas ou classificação. A extensão de cotas não equivale a
aprovar novo orçamento: o limite anterior de 30 mil músicas únicas não pode ser
presumido válido para a expansão. Aquisição de letras e classificação permanecem
sujeitas ao gate, à deduplicação global e à revisão do orçamento.

Validação: 95 testes de fontes, cotas e fronteira de importação aprovados;
Ruff nos arquivos novos e Mypy no módulo de extração; revalidação offline das
54 capturas e integridade SQLite registrada em `cached_verification.json`.
