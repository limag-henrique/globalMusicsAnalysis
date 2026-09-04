# Diligência de provedores — Milestone 1C

**Data de corte:** 2026-09-04  
**Escopo:** Luminate, Soundcharts e Chartmetric; BR, US, GB, FR, DE, ES, PT, IT e SE; janela pretendida 2021-presente.  
**Método:** somente documentação, termos, preços e canais mantidos pelos próprios provedores. Não houve compra, login autenticado, chamada de API, recebimento de amostra ou contato comercial. Portanto, ausência abaixo significa **PENDING** (não presumir inexistência nem cobertura).

## Decisão provisória

Nenhum provedor passa o gate 1C. **Luminate** tem a evidência pública mais forte de catálogo de charts, histórico e campos para diligência; **Soundcharts** tem a interface histórica e bulk de preço público mais diretamente documentados; **Chartmetric** oferece API/Data Share, mas as condições comerciais e a matriz histórica continuam não públicas. Em todos, direitos para retenção permanente, análise acadêmica, acesso de coautores/revisores, publicação agregada e replicação permanecem **PENDING de aditivo/ordem assinada**.

| Critério de saída 1C | Luminate | Soundcharts | Chartmetric |
|---|---|---|---|
| Cobertura comprovada para cada `plataforma × país × data × família` 2021+ | **PENDING** | **PENDING** | **PENDING** |
| API ou bulk documentado | API + Snowflake Data Share | API + data dump/feed | REST API + Data Share |
| Preço público do caminho apropriado | **PENDING** | Sim, inclusive bulk “from US$2.000/mês” | Dashboard sim; API/Data Share **PENDING** |
| Quota/rate limit público | **PENDING** | 5.000 RPM nos planos públicos | “até 25 req/s”; limite efetivo por plano **PENDING** |
| SLA público | **PENDING** | **PENDING** | **PENDING** |
| Licença para raw/retenção/backup pós-término | **PENDING** | **PENDING** | **PENDING** |
| Coautores, orientador, revisores, processadores cloud | **PENDING** | **PENDING** | **PENDING** |
| Tabelas/figuras/listas agregadas em artigo | **PENDING** | **PENDING** | **PENDING** |
| Pacote de replicação (dados, IDs, manifests/código) | **PENDING** | **PENDING** | **PENDING** |

## 1. Luminate — CONNECT, Music API e Music Data Share

### Fatos técnicos documentados

- O Music API declara acesso a **63 territórios**, usa `x-api-key` e `authorization`, e oferece endpoints para gravações, músicas, produtos, grupos de lançamento e artistas. Uma gravação pode ser consultada por **Luminate ID ou ISRC**, com agregação por `start_date`, `end_date`, `location` ISO-3166-1 alpha-2 e intervalo `day`, `week` ou `chart_week`. [Music API — getting started](https://docs.luminatedata.com/docs/getting-started), [Musical recordings](https://docs.luminatedata.com/reference/get-musical-recordings)
- O catálogo de charts permite filtrar por localização e proprietário (Luminate/Billboard). A consulta de chart aceita `chart_week` ISO `YYYY-Www`; a documentação define a semana como período de sete dias **sexta–quinta**. [Chart catalog](https://docs.luminatedata.com/reference/get-charts), [Chart data](https://docs.luminatedata.com/reference/get-chart-by-id)
- No Data Share, `VW_CHART_DS` expõe `CHART_ID`, proprietário, frequência, entidade, país, profundidade e início/fim efetivo; a tabela de rankings expõe semana, entidade, rank e histórico. Isso é uma base verificável para produzir a matriz solicitada **depois de contratado**. [Charts data dictionary](https://docs.luminatedata.com/docs/charts)
- O Data Share é Snowflake com views somente-leitura; cobre metadata, consumo, referência e mapeamento. A documentação diz que a maior parte das views atualiza diariamente e orienta solicitar acesso por `datasupport@luminatedata.com`. [Music Data Share](https://docs.luminatedata.com/docs/onboarding-documentation)
- Identidade/métricas: `MR_ID`/ISRC e `EXTERNAL_IDS` existem na metadata; ISRC pode faltar por nuances de entrega. Os fatos por provedor incluem território, modalidade comercial/serviço, categoria stream/venda, `QUANTITY`, `EQUIVALENT_QUANTITY`, data reportada e `MODIFIED_AT`. [Metadata](https://docs.luminatedata.com/docs/metadata), [Provider consumption](https://docs.luminatedata.com/docs/consumption-data-provider)

### Cobertura, metodologia e lacunas

CONNECT informa história de charts desde 2014-W01 ou a primeira semana de publicação do chart. A lista/metodologia territorial é mais específica: produto US desde 1991, Canadá desde 1995, streams US/CA desde 2007, song sales desde 2008, airplay desde 2014 e agregado mundial desde 2019-W01; os breakouts fora de US/CA são majoritariamente consistentes só desde 2022-W01. Esses marcos não provam cada combinação de plataforma/chart. Para semanas antigas, alguns breakouts podem não existir: só a unidade total usada no ranking é garantida. A atualização do UI/API/Data Share ocorre após processamento noturno, normalmente cedo; isto **não é SLA**. [Methodology FAQs](https://support.luminatedata.com/portal/en/kb/articles/methodology-faqs), [country list](https://support.luminatedata.com/portal/en/kb/articles/country-list), [Charts FAQ](https://support.luminatedata.com/portal/en/kb/articles/charts)

O catálogo autenticado contém `COUNTRY_CODE`, `START_EFFECTIVE_DATE`, profundidade e frequência por chart, mas a lista pública não prova quais charts de cada DSP/família existem nos nove países, a primeira/última data, ausência de gaps ou a equivalência metodológica entre territórios. Assim, todas as nove células e a completude 2021-presente ficam **PENDING**, inclusive qualquer alegação de cobertura específica de Spotify/Apple/YouTube/Amazon.

**Metodologia.** Luminate/Billboard usam critérios de elegibilidade e equivalentes para converter consumo em unidades; a documentação alerta que regras e colunas históricas podem diferir. Metodologia, provider panel, revisões/backfills, timezone, atraso e definição de cada chart do corpus são **PENDING de coverage extract + metodologia versionada**. [Eligibility and review](https://support.luminatedata.com/portal/en/kb/articles/eligibility)

### Comercial, limites e direitos

- Não foi localizado preço público, quota/rate-limit numérico ou SLA para CONNECT/Music API/Data Share: **PENDING de proposta/order form**.
- Os termos (atualizados em março de 2026) permitem apenas uso interno confidencial, salvo autorização escrita. Vedam cópia/transferência a terceiros, derivados além de relatórios internos, publicar/republicar rankings ou comparações para distribuição e divulgar conteúdo ao público. Logo, retenção, corpus acadêmico, coautoria/revisão, publicação agregada e replicação não podem ser inferidos do termo padrão: todos são **PENDING de licença que prevaleça expressamente**. [Luminate Terms §2.3](https://luminatedata.com/terms-of-use/)
- **Canal oficial/procurement:** [sales/contact](https://luminatedata.com/contact-us-sales/), `help@luminatedata.com`, e `datasupport@luminatedata.com` para Data Share/API. Solicitar Music API ou Data Share acadêmico, não somente dashboard. Academic pricing/program e rota formal de revisão por pares: **PENDING**.

## 2. Soundcharts API e Enterprise Data Dump/Data Feed

### Fatos técnicos documentados

- A API lista charts por plataforma e tem endpoints explícitos para datas disponíveis e ranking de song/album por data: `available-rankings` e `ranking/{datetime}`. A resposta de datas inclui plataforma, frequência, país, `maxResultsCount` e paginação. [Charts endpoints](https://developers.soundcharts.com/api/reference/charts/summary), [ranking-date schema](https://developers.soundcharts.com/documentation/reference/definition/availablerankingcollectionresponse)
- O ranking histórico aceita data ATOM e paginação `offset`/`limit`, com máximo 100 itens por requisição. A documentação só promete métrica explícita para charts Airplay (spins) e Spotify (streams), além de DOC/WOC; não extrapolar métrica para outras plataformas. [Ranking for a date](https://developers.soundcharts.com/api/reference/charts/get-song-ranking-for-a-date)
- Identificadores: há UUID Soundcharts, busca por ISRC, busca por ID de plataforma e endpoint de IDs. A sandbox é limitada, embora enumere exemplos de UUID, ISRC e Spotify ID; não é evidência de cobertura de produção. [Song endpoints](https://developers.soundcharts.com/api/reference/song/summary), [Sandbox](https://developers.soundcharts.com/documentation/sandbox-data)
- Autenticação atual pode usar access token via client credentials; chaves legadas `x-app-id`/`x-api-key` ainda são suportadas. Sandbox é aberto; trial de produção é de 1.000 chamadas. [Getting started](https://developers.soundcharts.com/api/reference/radio/get-radios-by-country-deprecated)

### Cobertura, metodologia e lacunas

A interface permite obter, **por chart**, as datas disponíveis antes de baixar rankings. Ela não publica uma matriz pré-contrato que prove, para cada plataforma/família e os nove países, início, fim, profundidade completa, gaps, revisões ou cobertura contínua desde 2021. Portanto, BR/US/GB/FR/DE/ES/PT/IT/SE = **PENDING**; também é **PENDING** a origem exata do rank (oficial, calculado ou normalizado) e a metodologia/versão por chart.

Os termos dizem que fontes de terceiros podem mudar ou ser removidas e que o provedor não controla os dados de terceiros. Para dados de YouTube, reconhecem expressamente a sujeição aos termos/políticas YouTube e não garantem disponibilidade contínua. [Soundcharts Terms §§2.3–2.4](https://soundcharts.com/en/terms)

### Preço, limites, SLA e direitos

- API mensal pública: Starter US$50/10k; Developer US$250/500k; Startup US$500/4M; Business US$900/10M; Scale US$1.700/20M; Enterprise US$4.500/60M. Todos indicam **5.000 RPM**. Data dump/data feed enterprise começa em **US$2.000/mês**, entregue a S3/GCS/ClickHouse/Databricks. [Pricing](https://developers.soundcharts.com/pricing)
- A página também diz que suporte varia de FAQ a email/Slack, mas não publica SLA, tempo de retenção, disponibilidade contratual ou garantia de refresh: **PENDING**. A oferta [Soundcharts for Education](https://soundcharts.com/en/soundcharts-for-education) declara dashboard gratuito para estudantes/docentes e desconto de 30% na API com validação acadêmica; ela não substitui licença de publicação/redistribuição nem prova elegibilidade/preço final para este corpus.
- Os termos vedam copiar/modificar/distribuir sem consentimento e comunicar a terceiros, salvo ferramenta/autorização. A tolerância a comunicação derivada é ocasional, gratuita, atribuída, não sistemática e não incorporada a um serviço; exportação, cache e reutilização de dados de plataformas de terceiros continuam sujeitos aos termos upstream. Assim, raw, retenção/backup pós-término, coautores/revisores, artigo e pacote de replicação são **PENDING de cláusula expressa**. [Soundcharts Terms](https://soundcharts.com/en/terms)
- **Canal oficial/procurement:** [formulário Contact](https://soundcharts.typeform.com/to/IFQ4MvtU), `contact@soundcharts.com`, `help@soundcharts.com` (mencionado pela documentação do endpoint para acesso), e [pricing/data dump contact](https://developers.soundcharts.com/pricing).

## 3. Chartmetric REST API e Data Shares

### Fatos técnicos documentados

- Chartmetric anuncia REST API para seus data points, Data Shares por Snowflake/S3/GCS com refresh programado, e rate limit de **até 25 requisições/s**. Isto é teto de marketing; a quota efetiva por plano e os headers/erros precisam ser conferidos no contrato e no ambiente autenticado. [Developer tools](https://chartmetric.com/features/developer-api)
- O Help Center identifica a documentação oficial da API e informa que offsets acima de 10k não são permitidos. A documentação e os endpoints autenticados devem ser a fonte de schema/limites finais, não a interface dashboard. [Chartmetric API collection](https://help.chartmetric.com/en/collections/Chartmetric%20API)
- O Data Share é explicitamente posicionado para análise agregada, com Snowflake, BigQuery e Databricks, e preço baseado no volume — sem tabela pública. [Data Shares request](https://chartmetric.com/contact-us/data-shares)

### Cobertura, método e identificadores

A página pública afirma dados históricos e contemporâneos, mas nenhuma fonte pública aberta nesta diligência fornece uma matriz verificável de `plataforma × chart × país × data`, primeira data ou gaps para o intervalo pretendido. A página de Developer Tools pergunta se história está disponível, mas não responde publicamente com tal matriz. Logo, todos os nove países, cada chart/plataforma, profundidade, cadência, timezone, metodologia/revisões e identificação ISRC/cross-platform **do corpus contratado** são **PENDING de sample + documentação autenticada/contrato**. Não se deve deduzir cobertura da existência de REST API ou Data Share.

### Preço, limite, SLA e licença

- Preços públicos de **dashboard**, no anual: Manager US$40/mês, Premium US$117/mês e Ultra US$150/mês. Eles não são preço de API/Data Share. [Pricing](https://chartmetric.com/pricing)
- Os termos de dashboard efetivos em 03-09-2026 afirmam que API, bulk delivery e planos de equipe não estão cobertos por eles; exigem acordo de serviços para bulk, SLA, cobrança faturada ou produto para terceiros. Portanto preço API/Data Share, SLA, quota contratual e retenção: **PENDING**. [Terms §§1.6, 3.5](https://chartmetric.com/terms-of-service)
- Para dashboard/MCP, os termos permitem pesquisa/análise para trabalho próprio/interno e insights em documentos/apresentações, mas vedam redistribuir/publicar raw standalone, extrair em massa do dashboard, disponibilizar dados a terceiros e compartilhar login. Isso não concede, por si, direitos à API/Data Share, nem permissão para coautores/revisores externos, artigo com tabelas/listas, storage permanente ou replicação: **PENDING de Chartmetric Services Agreement**. [Terms §10](https://chartmetric.com/terms-of-service)
- **Canal oficial/procurement:** [Developer API request](https://chartmetric.com/contact-us/developer-api), [Data Share request](https://chartmetric.com/contact-us/data-shares), `hi@chartmetric.com` e `sales@chartmetric.com`. Desconto acadêmico, elegibilidade, inclusão de API/Data Share e rota formal de revisão/replicação: **PENDING**.

## Evidência que o fornecedor deve entregar antes de qualquer ativação

1. Extrato ou amostra descartável e checksum com catálogo de charts e matriz de presença/ausência para as nove geografias, cada plataforma/família e todas as datas desde 2021-01-01.
2. Manifesto de gaps, backfills, restatements, mudanças metodológicas, timezone, calendário e profundidade; schema/data dictionary contendo IDs, ISRC, origem e unidade/rank.
3. Preço total (API/bulk/storage/egress), quota, rate-limit, SLA e política para retry/backfill, todos incorporados ao order form.
4. Licença inequívoca para armazenar raw/snapshots/checksums/backups, inclusive após expiração; analisar e derivar métricas; acesso de instituição, coautores, orientador, revisores e processadores cloud; publicar agregados/tabelas/figuras/listas permitidas; e reproduzir via dados, enclave ou código+manifests.
5. Confirmação de quais obrigações upstream (particularmente YouTube) chegam ao cliente e de que o fornecedor tem direito de sublicenciar os usos pretendidos.

Sem esses itens assinados e verificados, a decisão permanece **PENDING** e o adapter deve ficar desabilitado, conforme o gate do Milestone 1C.
