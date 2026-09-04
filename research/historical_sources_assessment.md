# Avaliação de fontes históricas para rankings musicais multinacionais

**Data de corte:** 2026-09-03  
**Escopo geográfico:** BR, US, GB, FR, DE, ES, PT, IT e SE  
**Janela pretendida:** 2021-presente  
**Objetivo:** identificar uma fonte tecnicamente utilizável e juridicamente contratável para um corpus científico longitudinal, sem comprar, cadastrar conta, raspar páginas ou chamar APIs autenticadas.

## Resumo executivo

Nenhuma API pública de plataforma examinada entrega, por si só, um arquivo histórico 2021-presente que esteja simultaneamente completo para os nove países, reproduzível, analisável e redistribuível.

- **Apple Music API Charts** é uma API de ranking corrente. O endpoint não aceita data e o limite correto é **200 por página**, não 100. O Apple Music Feed atualiza a cada 24 horas, mas a própria Apple proíbe expressamente usá-lo para análise ou sistemas internos.
- **YouTube Data API `videos.list?chart=mostPopular`** é um ranking corrente de vídeos, não o YouTube Music Top Songs. Desde 21-07-2025, ele reúne conteúdo dos charts de música, filmes e jogos. Não há parâmetro histórico.
- **YouTube Music Charts** é o produto semanticamente mais próximo de um ranking musical: Top Songs agrega visualizações das versões oficiais, lyric videos e UGC reconhecido. Porém, não há API/export oficial público nem garantia documental de retenção histórica integral.
- **Spotify Charts/Web API** não oferece API pública documentada de charts, garantia histórica ou exceção acadêmica; além disso, a política vigente proíbe analisar Spotify Content/Service e criar métricas derivadas.
- **Amazon Music Web API** continua em closed beta. Seu endpoint “Top Tracks” é personalizado pelo histórico do usuário, não um chart nacional, e não possui histórico documentado.
- **Soundcharts** e **Chartmetric** têm endpoints reais de datas e rankings históricos, mas a disponibilidade exata desde 2021 precisa ser verificada por plataforma, país e chart em uma prova contratual. Os termos públicos não concedem a redistribuição científica ampla necessária.
- **Luminate CONNECT/Music API/Data Share** é a evidência técnica mais forte para cobertura multinacional: documenta dados nacionais nos nove países desde 2019 W1 (US desde 2014), IDs/ISRC e integração por API/data share. Contudo, a própria documentação alerta para lacunas/rupturas entre 2019-2022, e os termos padrão vedam publicação de charts, benchmarking e divulgação ao público sem autorização contratual.
- **YouTube Researcher Program** é a única rota oficial examinada que concede claramente pesquisa acadêmica, métricas derivadas e publicação. Ela amplia a Data API, mas não transforma `mostPopular` em arquivo histórico de Top Songs e proíbe redistribuir os dados brutos do programa.

**Shortlist recomendada para diligência comercial, sem contratação automática:** (1) Luminate, (2) Soundcharts, (3) Chartmetric. Em paralelo, vale solicitar o YouTube Researcher Program como fonte complementar e rota jurídica específica para estudos sobre YouTube. A escolha final deve depender de uma amostra de cobertura e de cláusulas escritas sobre retenção, publicação agregada e replicação — não de material de marketing.

## Como ler esta avaliação

- **FATO DOCUMENTADO:** afirmação explícita em documentação, termos ou material oficial do fornecedor.
- **AUSÊNCIA DOCUMENTAL:** o item não foi localizado nas fontes oficiais públicas consultadas. Isso não prova que uma capacidade privada não exista.
- **INFERÊNCIA:** conclusão técnica ou de risco derivada dos fatos; não é declaração do fornecedor nem parecer jurídico.
- **PENDING:** requer consulta autenticada, amostra do fornecedor ou confirmação contratual.
- **UNKNOWN:** não há evidência pública suficiente nem base para presumir.

Preços são os publicados na data de corte, antes de impostos. “Não divulgado publicamente” não significa gratuito.

## Comparação normalizada

| Fonte | Plataforma/origem | Geografia documentada | Histórico nativo documentado | Frequência | Profundidade | Identidade | Métrica de ranking | Acesso/auth | Preço público | Quota/rate limit |
|---|---|---|---|---|---|---|---|---|---|---|
| Apple Music API Charts | Apple Music | Storefront dinâmico ISO alpha-2; os nove alvos aparecem no endpoint oficial de storefronts | **Não**; sem parâmetro de data | “Top 100” é atualizada diariamente; SLA geral não publicado | `limit` padrão 20, máximo **200**, paginação | Apple catalog ID; Song inclui ISRC | Ordem de “most-played”; sem plays | Developer JWT ES256; programa Apple | US$99/ano; waiver acadêmico possível; sem tarifa por chamada publicada | Valor não publicado; 429 temporário |
| Apple Music Feed | Apple Music, export bulk | Storefront nos objetos/feed | Apenas `/latest` é documentado; não há arquivo histórico contratado publicamente | refresh completo a cada 24h | bulk Parquet; profundidade contratual não publicada | IDs Apple; metadata de catálogo | `popularityTopChartSongs/Albums`, rank/storefront | Developer token + Media Services key | Incluído no programa, sem preço separado publicado | Não publicado |
| YouTube Data API `mostPopular` | YouTube vídeos | `regionCode` dinâmico via `i18nRegions.list` | **Não**; sem data/janela | Sem SLA/frequência publicada | `maxResults` 1-50; total máximo do chart não documentado | YouTube video ID; sem ISRC | algoritmo de popularidade; statistics opcionais não são a fórmula do rank | API key para público; OAuth para dados do usuário | Sem preço por unidade publicado | 1 unidade/chamada; 10.000 unidades/dia no bucket geral padrão |
| YouTube Music Charts | YouTube/YouTube Music | Help diz 61 países/regiões, mas enumera 68; todos os nove alvos estão enumerados | Datas podem ser vistas na experiência, mas extensão/retenção integral não é documentada | Songs/Videos diário e semanal; Artists semanal; Trending várias vezes/dia | 50 só para Shorts e 100 só para Artists; Songs/Videos não declarados na Help | Links/entidades YouTube; ISRC não documentado | views agregadas por song; views de vídeo; criações Shorts | site público; nenhuma API/export de charts documentada | Gratuito para consulta humana | Não aplicável/publicado |
| Spotify Charts + Web API | Spotify | charts globais/regionais/cidades; lista contratual de países não publicada | Cobertura/retenção histórica não garantida | diária/semanal | Top 200 não garantido na documentação atual | Web API: Spotify ID e ISRC | rank e streams filtrados quando exibidos | Charts exige login para acesso completo; Web API bearer token | Sem tarifa API; app em Development Mode exige proprietário Premium | janela móvel 30s com limite não publicado; quotas adicionais não publicadas |
| Amazon Music Web API | Amazon Music | `/markets` dinâmico; lista integral não pública sem acesso | **Não** | Não publicada | Top Tracks máximo 20/página; total não documentado | Amazon IDs/ASIN/DMID e ISRC | ordem personalizada por histórico do usuário; sem plays/rank numérico | closed beta; Login with Amazon OAuth + `x-api-key` + aprovação | Não divulgado publicamente | TPS não publicado; 429; aumento via contato |
| Soundcharts API | Amazon, Apple, Deezer, Spotify, YouTube e outras fontes | marketing: Apple 154 mercados, Spotify 74, YouTube 56; página pública YouTube diz 62; Amazon global | **Sim, interface/endpoints:** datas disponíveis + ranking por data; início exato por chart é PENDING | segue refresh da fonte; varia por chart | páginas de ranking até 100; paginação; profundidade depende do chart | UUID Soundcharts, ISRC e IDs de plataformas | rank; histórico: spins e Spotify streams; latest também documenta YouTube views/TikTok count | `x-app-id` + `x-api-key`; sandbox aberto e trial 1.000 requests | US$50/10k; 250/500k; 500/4M; 900/10M; 1.700/20M; 4.500/60M por mês; dump desde US$2.000 | 5.000 RPM nos planos públicos |
| Chartmetric API/Data Share | Spotify, Apple, Amazon, YouTube, Shazam, Deezer etc. | endpoints por país e endpoint de países disponíveis; cobertura exata autenticada é PENDING | **Sim:** endpoints aceitam `date`; há endpoint de datas; empresa iniciou em nov/2016, mas não retropreenche o que não rastreou | diária/semanal conforme chart; YouTube Top Track/Video semanal | paginação por offset; máximo total por chart não está claramente documentado | Chartmetric ID, ISRC e IDs cross-platform | rank; alguns charts trazem plays/views; Spotify plays após 02-06-2022 ficam nulos | refresh token -> bearer de 1h; Data Share por contato | dashboard US$40/117/150 por mês no anual; **API/Data Share não divulgados** | por plano, sliding window; marketing diz até 25 req/s |
| Luminate CONNECT/Music API/Data Share | dados first-party de mais de 500 DSPs/retailers/agências; Billboard/Luminate charts | mais de 60 países; os nove alvos documentados | US: CONNECT 2014; demais nove alvos: 2019 W1; possíveis gaps/partial 2019-22 | consumo e charts principalmente semanais; cadência exata varia | Ranking Report até 10.000; Data Share com profundidade ilimitada | Luminate Song ID, ISRC, Product/Release Group IDs | streams, vendas, airplay, equivalentes e charts | plataforma, API e data share sob assinatura; auth não pública | Não divulgado publicamente | Não divulgado publicamente |
| YouTube Researcher Program | corpus público da YouTube Data API | pesquisadores elegíveis nos nove países; dados globais públicos | Não fornece arquivo retroativo de `mostPopular`; permite congelar dados coletados para análise final | depende dos endpoints aprovados | quota ampliada conforme justificativa | IDs YouTube; sem ISRC nativo | metadata/estatísticas da Data API; derivados autorizados no projeto | candidatura institucional + Google Cloud/API project | Gratuito; aprovação discricionária | “quota suficiente” mediante justificativa/aprovação |

## Direitos, retenção e publicabilidade

| Fonte | Retenção | Análise acadêmica | Publicação agregada | Redistribuição/raw | Risco para este projeto |
|---|---|---|---|---|---|
| Apple Music API/Feed | API não promete histórico; Feed apenas latest | Feed **proíbe expressamente análise**; MusicKit é limitado a facilitar acesso à assinatura; nenhuma exceção acadêmica encontrada | Não autorizada pelos termos públicos para este uso | Feed proíbe compartilhamento; conteúdo MusicKit é restrito | **Muito alto / bloqueado sem permissão escrita** |
| YouTube Data API padrão | Non-Authorized Data: apagar ou atualizar em até 30 dias; estatística pública não pode ficar >30 dias sem autorização | Derivados e agregação são restringidos por padrão | PENDING de auditoria/emenda; histórico contextualizado pode ser exibido | conteúdo/raw não pode ser redistribuído livremente | **Alto**, mitigável por auditoria e permissão específica |
| YouTube Music Charts (site) | Sem garantia pública de retenção | Nenhuma licença específica encontrada | UNKNOWN | Nenhuma licença de dataset/export encontrada; scraping proibido | **Alto** sem Researcher Program/permissão |
| Spotify | não indefinida; caching temporário/necessário; manter conteúdo atual | política proíbe análise “for any purpose” e métricas derivadas | Não há exceção acadêmica documentada | bases, agregação e transferência são restringidas | **Muito alto / bloqueado sem permissão escrita** |
| Amazon Music Web API | caching somente como autorizado/intervalo indicado pela Amazon | closed beta/restricted materials; nenhuma exceção encontrada | requer aprovação | confidencialidade e distribuição controlada | **Muito alto / inadequado** |
| Soundcharts | prazo de retenção após export/API não está claro nos termos públicos | serviço suporta análise profissional, mas uso acadêmico/publicação não é expressamente licenciado | exploração pública é proibida sem autorização; tolerância é ocasional, não sistemática, com atribuição | copiar/distribuir dados requer consentimento; termos upstream continuam aplicáveis | **Alto até contrato específico** |
| Chartmetric | API/bulk têm contrato separado; regra pública de retenção não localizada | termos do dashboard permitem “research, analysis” para trabalho próprio/interno | insights podem aparecer em documentos/apresentações; extensão para artigo/tabelas completas deve ser negociada | raw standalone e redistribuição proibidos; API não é coberta pelos termos do dashboard | **Médio-alto até contrato/API addendum** |
| Luminate | conforme order form; não público | análises internas são permitidas no padrão; licença acadêmica não documentada | termos padrão proíbem charts/listas, benchmarking/publicação e divulgação ao público | transferência/exportação a terceiros proibida salvo contrato | **Alto até licença acadêmica/publicação negociada** |
| YouTube Researcher Program | refrescar a cada 30 dias até o ponto em que seja necessário congelar para concluir análise/publicação | **Sim, projeto aprovado e não comercial** | **Sim; derivados e publicação são previstos** | Program Data bruto não pode ser divulgado/reproduzido/transferido | **Médio**, condicionado à aprovação e desenho de replicação sem raw |

## Avaliação detalhada por fonte

### 1. Apple Music API Charts e Apple Music Feed

**FATOS DOCUMENTADOS.** `GET /v1/catalog/{storefront}/charts` retorna songs, albums, playlists e music videos ordenados por popularidade. Aceita storefront, tipo, gênero, chart, `limit`, `offset` e modificadores de coleções globais/cidades. O limite é padrão 20 e máximo **200**. A resposta de Song pode conter Apple catalog ID, artista, álbum, data de lançamento e ISRC. [Get Catalog Charts](https://developer.apple.com/documentation/applemusicapi/charts), [Get songs by ISRC](https://developer.apple.com/documentation/applemusicapi/get-multiple-catalog-songs-by-isrc)

O endpoint de storefronts é a autoridade dinâmica. A resposta oficial inclui BR, US, GB, FR, DE, ES, PT, IT e SE. Todas as requisições precisam de developer token JWT ES256; o token pode durar no máximo seis meses. O Apple Developer Program custa US$99/ano, embora instituições educacionais elegíveis possam pedir waiver. O rate limit numérico não é publicado; excesso retorna 429. [Storefronts](https://developer.apple.com/documentation/applemusicapi/get-all-storefronts), [developer token](https://developer.apple.com/documentation/applemusicapi/generating-developer-tokens), [membership](https://developer.apple.com/support/compare-memberships/)

O Feed é uma exportação bulk Parquet, contém charts de popularidade e faz refresh completo a cada 24 horas. Contudo, só `/latest` é documentado e a Apple declara que o Feed só pode promover conteúdo Apple Music em um app; análise, ferramentas internas e compartilhamento com terceiros são estritamente proibidos. [Apple Music Feed](https://developer.apple.com/documentation/applemusicfeed)

**AUSÊNCIAS DOCUMENTAIS.** O Charts endpoint não tem parâmetro de data/período, não promete arquivo retroativo, não informa contagem de plays e não concede licença acadêmica. “History” em MusicKit diz respeito ao histórico recente do usuário, não ao histórico do chart.

**INFERÊNCIA.** Tecnicamente seria possível coletar snapshots correntes diariamente, mas isso não recupera 2021-presente e não resolve a licença. Não usar Apple API/Feed como corpus sem autorização escrita específica.

### 2. YouTube Data API — `videos.list?chart=mostPopular`

**FATOS DOCUMENTADOS.** O único valor de `chart` é `mostPopular`; `regionCode` é ISO alpha-2 e os valores aceitos são descobertos por `i18nRegions.list`. `videoCategoryId` é opcional. `maxResults` vai de 1 a 50; o endpoint custa uma unidade. A quota geral padrão é 10.000 unidades/dia. API key atende dados públicos; OAuth é necessário para dados/ações de usuário. [videos.list](https://developers.google.com/youtube/v3/docs/videos/list), [Getting started](https://developers.google.com/youtube/v3/getting-started)

Desde 21-07-2025, `mostPopular` não representa mais a antiga página Trending: combina vídeos dos charts Trending Music, Movies e Gaming. O guia também diz que o algoritmo usa múltiplos sinais. Isso não é semanticamente equivalente ao YouTube Music Top Songs. [revision history](https://developers.google.com/youtube/v3/revision_history), [implementation guide](https://developers.google.com/youtube/v3/guides/implementation/videos)

O recurso traz video ID e, se solicitadas, statistics como views, likes e comentários; não traz ISRC. A definição de `viewCount` mudou em 24-08-2026 para contar inícios/replays em todos os formatos, inclusive Shorts, criando potencial quebra de série. [Video resource](https://developers.google.com/youtube/v3/docs/videos)

**AUSÊNCIAS DOCUMENTAIS.** Não existem parâmetros de data, janela histórica ou frequência de atualização, nem máximo total específico do chart. O limite de 1.000 mencionado na página pertence ao filtro `myRating`, não deve ser atribuído a `mostPopular`.

**RISCOS.** Non-Authorized Data só pode permanecer 30 dias antes de ser apagado ou atualizado; a política padrão proíbe novos/derived metrics e agregação ampla. A partir de 01-06-2026, desenvolvedores auditados podem solicitar permissão adicional para derivados e retenção estatística; a decisão é individual. [Developer Policies §III.E/L](https://developers.google.com/youtube/terms/developer-policies), [audit form](https://support.google.com/youtube/contact/yt_api_form)

### 3. YouTube Music Charts

**FATOS DOCUMENTADOS.** Top Songs agrega views da música oficial em vídeo oficial, lyric video e UGC reconhecido; Top Music Videos considera o vídeo oficial; Top Artists soma a discografia; Top Songs on Shorts usa o número de Shorts criados. Paid-ad views não contam. Há versões diária e semanal de Songs/Videos, semanal de Artists, diária/semanal de Shorts e Trending várias vezes ao dia. [YouTube Charts & Insights](https://support.google.com/youtube/answer/9014376?hl=en)

A mesma Help page afirma “61 countries or regions”, porém enumera **68 nomes** na captura atual. Os nove alvos aparecem na enumeração. A integração dos charts globais ao YouTube Music foi anunciada em 05-10-2020 para 57 países, o que não prova a data inicial de cada série. [anúncio oficial](https://blog.youtube/news-and-events/introducing-global-charts-youtube-music/)

**AUSÊNCIAS DOCUMENTAIS.** A profundidade só é explícita para Shorts (50) e Artists (100), não para Songs/Videos. Não foi localizada API/export CSV, ISRC, garantia de retenção ou extensão histórica completa. Datas visíveis na UI não constituem SLA de arquivo.

**INFERÊNCIA.** Este é o constructo correto para “música mais ouvida no YouTube”, mas o acesso programático precisa vir do Researcher Program, de fornecedor licenciado ou de autorização direta. Não raspar a UI nem endpoints privados.

### 4. Spotify Charts e Web API

**FATOS DOCUMENTADOS.** Spotify descreve charts diários/semanais, regionais/globais, virais e de cidades, com rank, peak/streak e streams filtrados quando mostrados. A página exige login para todos os charts. A Web API pesquisa e recupera metadata de uma faixa, inclusive Spotify ID e ISRC, mas não fornece chart history. [Understanding Spotify Charts](https://support.spotify.com/us/artists/article/understanding-spotify-charts/), [Spotify Charts](https://charts.spotify.com/home), [Get Track](https://developer.spotify.com/documentation/web-api/reference/get-track)

O Web API usa bearer token; a quota é uma janela móvel de 30 segundos com threshold não publicado, mais quotas de Development Mode não publicadas. Não há tarifa API pública. [rate limits](https://developer.spotify.com/documentation/web-api/concepts/rate-limits), [quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)

**AUSÊNCIAS DOCUMENTAIS.** Não há Charts API pública, schema/export estável, lista contratual de países, garantia Top 200, cobertura histórica ou retenção garantida.

**RISCO BLOQUEADOR.** A Developer Policy III.13 proíbe analisar Spotify Content/Service “for any purpose”, incluindo métricas derivadas, benchmarks e estatísticas; III.14 proíbe ML/AI. Os Developer Terms também restringem armazenamento, banco, agregação e redistribuição. Não foi encontrada exceção acadêmica. [Developer Policy](https://developer.spotify.com/policy), [Developer Terms](https://developer.spotify.com/terms). A análise completa já está registrada em `research/spotify_official_capabilities_2026-09-03.md`.

### 5. Amazon Music Web API

**FATOS DOCUMENTADOS.** A API e seus documentos permanecem **closed beta/preview**. `/v1/markets` retorna mercados dinamicamente. `/browse/tracks/top` retorna no máximo 20 itens por página e é definido como “based on analysis of the current user's listening history”; portanto, é personalizado. Track pode incluir Amazon IDs/ASIN/DMID, ISRC, market e availableMarkets. [Program overview](https://developer.amazon.com/docs/music/get_started_program-overview.html), [Browse](https://developer.amazon.com/docs/music/API_web_browse.html), [schema](https://www.developer.amazon.com/docs/music/API_web_schema.html)

O acesso exige aprovação Amazon, Login with Amazon OAuth bearer e `x-api-key` associado ao Security Profile. Os limites TPS não são publicados; 429 orienta contato para aumento. Preço público não foi localizado. [Web API overview](https://developer.amazon.com/docs/music/API_web_overview.html), [errors](https://developer.amazon.com/docs/music/API_web_errors.html)

**AUSÊNCIAS DOCUMENTAIS.** Não há chart territorial público, date/history, rank numérico, plays, cadência ou profundidade total documentados.

**RISCO.** Produtos precisam ser validados; territórios são habilitados individualmente. Como beta, há regras de Restricted Program Materials, confidencialidade e aprovação de distribuição. Não há exceção acadêmica. [Program Requirements](https://www.developer.amazon.com/docs/music/requ_AM-Program-Requirements.html), [Program Materials License](https://www.developer.amazon.com/support/legal/pml)

### 6. Soundcharts

**FATOS DOCUMENTADOS.** A Soundcharts agrega charts de Amazon, Apple, Deezer, Spotify, YouTube e várias outras plataformas. A página de cobertura declara Apple em 154 mercados, Spotify em 74 e YouTube em 56; uma página pública atual de YouTube declara 62. Essa inconsistência deve ser resolvida por consulta ao referencial da API, não por escolha arbitrária. [data sources](https://soundcharts.com/en/datasources), [charts methodology](https://help.soundcharts.com/en/articles/3666608-how-do-charts-work-on-soundcharts), [YouTube chart](https://soundcharts.com/en/charts/youtube/global)

A API expõe:

- lista de charts por plataforma/país;
- datas disponíveis: `GET /api/v2/chart/song/{slug}/available-rankings`;
- ranking por data: `GET /api/v2.14/chart/song/{slug}/ranking/{datetime}`;
- latest ranking;
- lookup de song por ISRC e links/IDs de plataformas.

As coleções de entries têm até 100 itens por chamada e paginação. A documentação do ranking histórico afirma métrica explícita para Airplay (spins) e Spotify (streams); a página latest também lista YouTube (views) e TikTok (video count). [ranking dates](https://developers.soundcharts.com/documentation/reference/charts/get-song-ranking-dates), [ranking by date](https://developers.soundcharts.com/documentation/reference/charts/get-song-ranking-for-a-date), [latest](https://developers.soundcharts.com/documentation/reference/charts/get-song-ranking-latest), [ISRC lookup](https://developers.soundcharts.com/documentation/reference/song/get-song-by-isrc)

Auth usa `x-app-id` e `x-api-key`. Há sandbox sem registro, trial de produção de 1.000 chamadas e planos mensais: US$50/10k, US$250/500k, US$500/4M, US$900/10M, US$1.700/20M e US$4.500/60M; todos exibem 5.000 RPM. Bulk dump/feed começa em US$2.000/mês. [access](https://help.soundcharts.com/en/articles/10091349-how-can-i-get-access-to-soundcharts-api), [pricing](https://developers.soundcharts.com/pricing)

**AUSÊNCIAS DOCUMENTAIS.** Não há tabela pública que prove a primeira data de cada chart×país, completude 2021-presente, ausência de gaps, retenção contratual após export, ou que toda plataforma cubra os nove alvos. “A empresa existe desde 2015” não comprova histórico de cada chart.

**RISCOS.** Os termos públicos proíbem scraping, exploração pública sistemática e comunicação a terceiros, salvo ferramentas/permissão específica; terceiros, inclusive YouTube, mantêm suas próprias regras. Comunicação derivada tolerada é ocasional, gratuita, atribuída e não incorporada a oferta. Uma tese/artigo e pacote de replicação precisam constar explicitamente no contrato. [Soundcharts Terms, arts. 5 e 7](https://soundcharts.com/en/terms)

### 7. Chartmetric

**FATOS DOCUMENTADOS.** A API pública documenta charts de Spotify, Apple Music, Amazon e YouTube, entre outros. Há endpoints de time-slice por `date`, `latest=true`, listagem de países e `GET /api/charts/{streamingType}/dates?fromDaysAgo=...`. YouTube Top Track/Video é semanal; track/artist chart history aceita ranges, frequentemente limitados a janelas de até 365 dias por chamada. [charts reference](https://apidocs.chartmetric.com/reference/tag/charts), [chart dates](https://apidocs.chartmetric.com/reference/tag/charts/get/api/charts/streamingType/dates), [YouTube Top Track](https://apidocs.chartmetric.com/reference/tag/charts/get/api/charts/youtube/tracks), [track chart appearances](https://apidocs.chartmetric.com/reference/tag/track/get/api/track/id/type/charts)

O modelo retorna Chartmetric ID, ISRC e IDs cross-platform. O endpoint Spotify documenta que `current_plays`/plays são nulos após 02-06-2022, detalhe importante para não confundir rank history com exposure history. [Spotify charts](https://apidocs.chartmetric.com/reference/tag/charts/get/api/charts/spotify)

Auth troca refresh token por bearer de uma hora. Rate limiting é sliding-window por plano, observado em headers; a página comercial diz “até 25 req/sec”. O preço público de dashboard é US$40/117/150 por mês no anual, mas API e Data Share exigem contato e não têm preço público. [quickstart](https://apidocs.chartmetric.com/), [rate limits](https://apidocs.chartmetric.com/guides/rate-limits), [developer tools](https://chartmetric.com/features/developer-api), [pricing](https://chartmetric.com/pricing)

**HISTÓRICO.** A empresa declara dados desde novembro de 2016, mas também afirma que, se algo não estava sendo rastreado, não pode ser retropreenchido. Logo, início corporativo não equivale a completude de cada país/chart. [backfill](https://help.chartmetric.com/en/articles/81)

**RISCOS.** Os termos atuais do dashboard permitem pesquisa/análise para trabalho próprio/interno e incluir insights em documentos, mas proíbem raw standalone/redistribuição e bulk automation do dashboard. Eles declaram explicitamente que API, bulk e team plans são regidos por contrato separado. A licença científica precisa estar no acordo da API/Data Share. [Chartmetric terms §§3.5, 10](https://chartmetric.com/terms-of-service)

### 8. Luminate CONNECT, Music API e Data Share

**FATOS DOCUMENTADOS.** Luminate recebe dados diretamente de mais de 500 provedores e oferece consumo, Billboard/Luminate charts, reports, Music API e Data Share. O CONNECT permite histórico de charts e números por trás do ranking; Ranking Reports exportam até 10.000 itens, e Data Share anuncia profundidade ilimitada. [CONNECT overview](https://support.luminatedata.com/portal/en/kb/articles/welcome-to-connect), [finance/API use cases](https://support.luminatedata.com/portal/en/kb/articles/music-finance-playbook)

A lista oficial marca BR, GB, FR, DE, ES, PT, IT e SE desde 2019 W1 e US desde 2014 W1. Também alerta: 2019-2022 pode ter gaps, cobertura parcial e trend breaks; a maior parte fica completa/consistente a partir de 2022 W1. [country list](https://support.luminatedata.com/portal/en/kb/articles/country-list), [methodology FAQ](https://support.luminatedata.com/portal/en/kb/articles/methodology-faqs)

O ecossistema usa Luminate Song ID, ISRC e IDs de produtos/releases. Métricas abrangem streams, song/product sales, airplay e equivalentes. API/Data Share precisam de assinatura separada. Preço, auth, quotas e SLA não são publicados.

**RISCOS.** Os termos padrão permitem outputs analíticos internos, mas proíbem distribuir/exportar conteúdo, criar/publicar charts ou rankings, benchmarking/comparações destinados à publicação e divulgação ao público, salvo order form. Portanto, Luminate é o melhor candidato técnico, mas somente se um contrato acadêmico autorizar paper, tabelas/figuras agregadas, retenção, revisão por pares e replicação controlada. [Luminate Terms §2](https://luminatedata.com/terms-of-use/)

### 9. YouTube Researcher Program

**FATOS DOCUMENTADOS.** Pesquisadores de instituição superior acreditada, degree-granting e sem fins lucrativos podem se candidatar; o programa está disponível para pesquisadores nos nove países-alvo e concede acesso escalado ao corpus público da Data API. O projeto deve ser não comercial e pretende publicação. [How it works](https://research.youtube/how-it-works/), [policies](https://research.youtube/policies/)

Os termos permitem métricas derivadas e recomendam open access; exigem refresh a cada 30 dias até ser necessário congelar o ponto temporal para finalizar análise/conclusões. A publicação é permitida, mas Program Data bruto não pode ser divulgado, reproduzido ou transferido. [Program Terms §§5-7](https://research.youtube/policies/terms/)

**LIMITAÇÃO.** O programa amplia quota e ajusta permissões; não cria uma API histórica do YouTube Music Top Songs. Serve bem para metadata/estatísticas e estudos próprios sobre YouTube, ou como complemento de um chart provider, mas não substitui automaticamente o corpus histórico solicitado.

## Matriz de viabilidade de cobertura: nove países, 2021-presente

Esta matriz avalia **prova pública suficiente para construir o corpus histórico requerido**, não mera disponibilidade atual do serviço no país.

Legenda: `CURRENT` = somente snapshot corrente documentado; `DOC*` = país/início documentados, mas com alerta de gaps/contrato; `PENDING` = fornecedor possui mecanismo dinâmico/histórico, porém requer consulta autenticada/amostra; `UNKNOWN` = sem evidência pública suficiente; `NO` = interface documentada não oferece histórico; `BLOCKED` = política pública inviabiliza análise sem permissão.

| Fonte | BR | US | GB | FR | DE | ES | PT | IT | SE | 2021-presente integral |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Apple Music API Charts | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | **NO / BLOCKED** |
| Apple Music Feed | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | **NO / BLOCKED** |
| YouTube Data API `mostPopular` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **NO** |
| YouTube Music Charts | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | **UNKNOWN** |
| Spotify Charts/Web API | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | **UNKNOWN / BLOCKED** |
| Amazon Music Web API | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **NO / BLOCKED** |
| Soundcharts | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING contrato + amostra** |
| Chartmetric | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING contrato + endpoint dates** |
| Luminate | DOC* | DOC* | DOC* | DOC* | DOC* | DOC* | DOC* | DOC* | DOC* | **PENDING: gaps 2021; melhor a partir de 2022** |
| YouTube Researcher Program | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **NO para chart retroativo; PENDING para pesquisa Data API** |

Conclusão da matriz: **não declarar cobertura 2021-presente como aprovada para nenhum fornecedor antes de receber um coverage extract** com todas as datas esperadas por `source × chart × country`, incluindo ausências e mudanças de metodologia. Luminate prova presença de dados nos nove países, mas reconhece que 2021 pode ser parcial. Soundcharts e Chartmetric têm as interfaces históricas mais diretas para charts de plataforma, mas não provam publicamente cada célula.

## Shortlist e estratégia de aquisição

### 1. Luminate — primeiro contato

Melhor evidência de cobertura nacional e métricas de consumo, com 2021 presente nos nove alvos. Pedir uma proposta de **Music API ou Data Share acadêmico**, não apenas dashboard. O ponto decisivo é obter permissão escrita para publicação científica e esclarecer as lacunas de 2021.

### 2. Soundcharts — segundo contato

Melhor documentação pública de endpoints de “datas disponíveis” e “ranking por data”, preços transparentes e forte cobertura cross-platform. Solicitar prova de cobertura exata para Apple/Spotify/YouTube por país e data, além de licença acadêmica que prevaleça sobre as restrições padrão de exploração pública.

### 3. Chartmetric — terceiro contato

API madura, endpoints específicos por data e fornecedor, ISRC/cross-platform IDs. Exigir proposta API/Data Share e contrato separado; não presumir que a permissão de “research” do dashboard cobre arquivo bulk, paper e replication package.

### 4. YouTube Researcher Program — trilha paralela

Solicitar acesso se o pesquisador/instituição forem elegíveis. Pode autorizar derivados e congelamento analítico, mas o plano de replicação terá de excluir raw Program Data e o projeto precisará definir como obtém o Top Songs histórico.

### Não priorizar

- Apple Music API/Feed: sem histórico 2021 e termos incompatíveis com análise.
- Spotify direto: ausência de Charts API/garantia e proibição explícita de análise.
- Amazon direto: beta fechado e sem chart territorial histórico.
- YouTube `mostPopular`: corrente, video-centric e semanticamente diferente do Top Songs.

## Perguntas obrigatórias de procurement

Solicitar respostas incorporadas ao order form/licença, não apenas por e-mail comercial:

1. Quais combinações exatas `platform × chart family × country × date` existem entre 2021-01-01 e a data atual? Fornecer coverage matrix e missing-date manifest.
2. Qual é a primeira/última data por célula e quais gaps, backfills, correções e trend breaks existem?
3. Qual é a frequência nativa (diária/semanal), timezone, boundary da semana e atraso normal/máximo?
4. Qual é a profundidade real de cada chart? Paginação entrega o chart inteiro ou somente os primeiros N?
5. Rank é oficial da plataforma, reconstruído pelo fornecedor ou proprietário? Qual metodologia/versão?
6. Qual métrica acompanha o rank (streams, views, units, creations)? É observada, estimada ou modelada? Como `NULL` deve ser interpretado?
7. Song/recording IDs incluem ISRC? Como versões, remasters, clean/explicit, UGC rollups e múltiplos ISRCs são tratados?
8. O contrato autoriza armazenamento permanente de raw, snapshots imutáveis, checksums, backups, cold storage e retenção após o fim da assinatura?
9. Autoriza análises acadêmicas, métricas derivadas, regressões, benchmarking cross-country e combinação com lyrics/metadata de terceiros?
10. Autoriza compartilhar raw/derived data com coautores, orientadores, anotadores, revisores, repositório institucional e processadores cloud? Em quais territórios?
11. Autoriza publicar tabelas, figuras, estatísticas agregadas, pequenas amostras, listas de faixas e IDs? Há threshold mínimo de agregação?
12. O pacote de replicação pode conter rank por música/data/país, ISRC/IDs, ou apenas código/manifests? Existe data enclave ou licença para replicadores?
13. Quais termos upstream (Spotify, YouTube, Apple, Amazon etc.) continuam aplicáveis ao cliente? O fornecedor garante direitos de sublicenciar análise/publicação?
14. Há obrigação de refresh/delete de YouTube Data API, takedown handling, auditoria ou remoção retroativa? Quem executa e como afeta snapshots científicos?
15. Quais limites API, quotas mensais, RPM/RPS, custos de overage, limites de range, tamanho de página e SLA de suporte?
16. Existe bulk delivery inicial 2021-presente seguido de deltas? Formatos (Parquet/CSV), schema registry, changelog e versionamento?
17. Como correções históricas são entregues? É possível reconstruir “as originally published” e “latest corrected” separadamente?
18. O fornecedor aceita DPA, segurança institucional, subprocessor list, data residency e notificação de incidente?
19. Qual preço acadêmico total para nove países, 2021-presente, todas as faixas até a profundidade requerida, incluindo API/dump e direitos de publicação?
20. Em caso de término, quais dados e derivados precisam ser apagados, em quanto tempo, e quais podem permanecer em papers, backups, registros de auditoria e repositórios?

## Critério de aprovação de uma fonte

Uma fonte só deve passar de `PENDING` para operacional quando houver:

1. coverage extract verificável para os nove países e todas as datas de 2021-presente;
2. dicionário de dados e metodologia, incluindo quebras de série;
3. amostra contendo IDs/ISRC, ranks, métricas e nullability;
4. contrato que autorize armazenamento, análise, publicação agregada e colaboração;
5. regra explícita para replication package;
6. tratamento contratual dos termos upstream;
7. preço/quota/SLA compatíveis;
8. revisão jurídica/institucional documentada.

Até lá, a arquitetura deve manter os adapters desativados e trabalhar apenas com fixtures sintéticas.

## Fontes primárias principais

### Apple

- [Get Catalog Charts](https://developer.apple.com/documentation/applemusicapi/charts)
- [Get All Storefronts](https://developer.apple.com/documentation/applemusicapi/get-all-storefronts)
- [Generating Developer Tokens](https://developer.apple.com/documentation/applemusicapi/generating-developer-tokens)
- [Apple Music Feed](https://developer.apple.com/documentation/applemusicfeed)
- [Apple Developer Program License Agreement](https://developer.apple.com/support/terms/apple-developer-program-license-agreement/)

### YouTube

- [videos.list](https://developers.google.com/youtube/v3/docs/videos/list)
- [Video resource](https://developers.google.com/youtube/v3/docs/videos)
- [YouTube Charts & Insights](https://support.google.com/youtube/answer/9014376?hl=en)
- [Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
- [YouTube Researcher Program](https://research.youtube/how-it-works/)
- [Researcher Program Terms](https://research.youtube/policies/terms/)

### Spotify

- [Understanding Spotify Charts](https://support.spotify.com/us/artists/article/understanding-spotify-charts/)
- [Spotify Developer Policy](https://developer.spotify.com/policy)
- [Spotify Developer Terms](https://developer.spotify.com/terms)

### Amazon

- [Amazon Music Web API overview](https://developer.amazon.com/docs/music/API_web_overview.html)
- [Browse API](https://developer.amazon.com/docs/music/API_web_browse.html)
- [Amazon Music Program Requirements](https://www.developer.amazon.com/docs/music/requ_AM-Program-Requirements.html)

### Agregadores/licenciadores

- [Soundcharts API docs](https://developers.soundcharts.com/llms.txt)
- [Soundcharts pricing](https://developers.soundcharts.com/pricing)
- [Soundcharts Terms](https://soundcharts.com/en/terms)
- [Chartmetric API docs](https://apidocs.chartmetric.com/)
- [Chartmetric terms](https://chartmetric.com/terms-of-service)
- [Luminate country list](https://support.luminatedata.com/portal/en/kb/articles/country-list)
- [Luminate methodology](https://support.luminatedata.com/portal/en/kb/articles/methodology-faqs)
- [Luminate Terms](https://luminatedata.com/terms-of-use/)

---

Esta é uma avaliação técnica/documental, não parecer jurídico. Capacidade técnica não implica licença de uso.
