# Expansão mundial e comparabilidade — 08/11/2026

**Atualização operacional:** a incorporação por população e o primeiro lote de
extração de posições estão em [expansion_20261108/README.md](expansion_20261108/README.md).
O texto abaixo documenta a investigação anterior à implementação; a liberação
atual é apenas para evidências de snapshots, sem promoção automática a anos.

## Resultado e limites

O inventário geográfico foi ampliado efetivamente para 250 entradas: 249 países e
territórios ISO, mais XK como exceção não ISO. São 2.250 células país/ano para
2018–2026. A referência oficial é a [tabela M49 da ONU](https://unstats.un.org/unsd/methodology/m49/overview/),
com as exceções documentadas no README. Há 27 fontes/rotas registradas e evidência
documental nacional/de plataforma para 71 mercados, dos quais 33 estão fora das
68 cotas atuais. Isso não significa 71 arquivos históricos completos: nenhuma
fonte nova foi liberada para ingestão.

| Região | Entradas no inventário | Mercados na política atual | Com seleção local | Com candidato documental nacional/de plataforma |
|---|---:|---:|---:|---:|
| África | 60 | 3 | 3 | 15 |
| Ásia | 51 | 14 | 14 | 19 |
| Américas | 57 | 19 | 19 | 20 |
| Europa | 52 | 30 | 29 | 13 |
| Oceania | 29 | 2 | 2 | 4 |
| Sem região M49 atribuída: Antártida | 1 | 0 | 0 | 0 |

Os denominadores incluem territórios; não são contagens de Estados soberanos.
Ásia inclui Taiwan pela política explícita; Europa inclui XK. A última coluna
mede esta revisão documental e não o total de charts existentes no mundo. Um
mercado antigo sem nova fonte revisada continua com seus dados locais preservados.

O baseline continua em 68 cotas, 67 mercados com seleção e 86.090 vínculos.
Andorra não foi eliminada do inventário por falta de seleção. Os 2.270 vínculos
provisórios continuam provisórios. A pesquisa atual não se torna mundialmente
representativa apenas pela criação das linhas geográficas.

## Fontes verificadas e a maneira correta de usá-las

| Fonte | Evidência observada | Incorporação proposta e limitação |
|---|---|---|
| TurnTable, Nigéria | [Metodologia do publicador](https://www.turntablecharts.com/news/480), Top 100 semanal desde lançamento em 2022; combina streaming e airplay, com recorrência e regras de versões | Forte candidato nacional para braço composto. Investigar o componente streaming, descrito desde julho de 2020, como série separada; continuidade atual/arquivo ainda não verificados |
| Mdundo | [Página primária de charts](https://play.mdundo.com/top-charts) e [Weekly Top 100 Kenya](https://mdundo.com/best/ke/64) exibem rótulos de países | Pilotar NG/GH/KE/TZ/UG e depois CM/MW/MZ/RW/ZM. Confirmar se o território mede audiência localizada, repertório ou outra segmentação, além de histórico/métrica. Não equivale ao consumo nacional inteiro |
| Apple Music | [Diretório oficial de Top 100 por país](https://music.apple.com/us/new/top-charts/daily-global-top-charts), complementado por três páginas primárias | Foram identificados 52 rótulos territoriais. O HTML mostra inicialmente 50 cards incluindo Global, portanto não se presume diretório completo. Útil para expansão prospectiva com mesma plataforma; não comprova arquivo anual anterior |
| IFPI Sudeste Asiático | [Anúncio de 23/01/2025](https://www.ifpi.org/ifpi-launches-official-southeast-asia-charts-hub-with-creation-of-new-charts-in-philippines-and-vietnam/) descreve seis charts nacionais semanais Top 20: ID/MY/PH/SG/TH/VN, com ponderação entre tiers | Bom braço multinacional com metodologia comum. PH/VN são novos no hub, quatro outros foram rebatizados; não atribuir 2018 como início de todas as séries |
| IFPI MENA nacional | [Anúncio de 27/09/2023](https://www.ifpi.org/ifpi-launches-four-new-music-charts-in-egypt-saudi-arabia-uae-and-north-africa/) distingue Egito, Arábia Saudita e Emirados | Três séries nacionais semanais para braço ponderado multiprovedor. Auditar datas, profundidade e agregação de versões |
| IFPI MENA/Norte da África regional | O mesmo anúncio distingue o agregado DZ/MA/TN; o [lançamento MENA](https://www.ifpi.org/the-official-mena-chart-launches-calm-down-by-rema-regions-first-ever-1/) cobre 13 mercados conjuntamente | Usar apenas contexto regional. Não copiar um Top 20 regional como se fosse ranking de cada um dos países |
| Circle, Coreia do Sul | [Publicador oficial](https://circlechart.co.kr/) separa Streaming, Digital e Global K-pop | Preferir Streaming para o braço de streaming; Digital entra no braço composto. Obter metodologia/versionamento e acesso específico; a página contém restrição a TDM não autorizado |
| Billboard Japan | [Método](https://www.billboard-japan.com/common/about/) e [Chart Insight](https://www.billboard-japan.com/chart_insight/) distinguem séries e arquivo | Streaming Songs e Hot 100 não são intercambiáveis. Conferir mudanças de componentes e acesso; dados de streaming não são necessariamente comparáveis aos totais de charts Spotify |
| IMI, Índia | [FAQ oficial](https://indianmi.org/faqs/) restringe o International Top 20 a músicas de idiomas não indianos | Não usar como ranking nacional geral nem preencher a cota de 440 com ele. Usar somente análise internacional separada; preservar repertório indiano/multilíngue no desenho principal |
| TME UNI, China | [Página primária e regras](https://www.tencentmusic.com/en-us/uni-chart.html) se referem a repertório chinês | Investigar geografia, plataformas, elegibilidade e componentes; não confundir música chinesa com consumo total na China. Manter separado de um chart Apple China |
| Reino Unido, Alemanha, Austrália, Nova Zelândia | [Official Charts](https://www.officialcharts.com/charts/singles-chart/), [Offizielle Charts](https://www.offiziellecharts.de/charts/single), [ARIA](https://www.aria.com.au/charts-faqs), [Aotearoa](https://aotearoamusiccharts.co.nz/) | Fontes de validação/triangulação por família, não substituição automática de Spotify. ARIA [alterou elegibilidade em setembro de 2025](https://www.aria.com.au/charts/news/the-aria-charts-are-changing); segmentar essa quebra |

Na África, as novas pistas nacionais/de plataforma fora das cotas atuais são
Botswana, Cabo Verde, Gâmbia, Camarões, Gana, Quênia, Malawi, Moçambique, Nigéria,
Ruanda, Tanzânia, Uganda e Zâmbia. A Nigéria tem metodologia nacional publicada;
vários outros dependem de charts específicos de plataforma e diligência adicional.

Na Ásia, documentei pistas fora das cotas para Armênia, Azerbaijão, Bahrein,
China, Chipre, Camboja, Cazaquistão, Nepal e Sri Lanka. Alguns desses mercados são
classificados na Ásia pela M49 embora sejam tratados como Europa em outros usos.
Há evidência primária de [Nepal](https://music.apple.com/ba/playlist/top-100-nepal/pl.9032e70a644e442688f120a829c636cd),
[Sri Lanka](https://music.apple.com/us/playlist/top-100-sri-lanka/pl.cd9b6c35086b43b193ecc3d32882a41e)
e [Cazaquistão](https://music.apple.com/do/playlist/top-100-kazakhstan/pl.27d3c4d63b0e41f29f79c98bb5a090e1?l=en-GB)
como charts Apple atuais. Não foi confirmado um chart nacional adequado para
Paquistão ou Bangladesh nesta revisão. A página Apple `/pk/` mostrou charts de
outros países; o código do storefront não demonstra um ranking do Paquistão.

## Fontes que permanecem em diligência

- O antigo domínio `theofficialsacharts.co.za` retornou conteúdo alheio à música
  em 08/11. Sua existência histórica não valida o endpoint atual. Ficou em hold;
  reverificar o publicador por [IFPI/RiSA](https://www.ifpi.org/about-us/local-associations/).
- Boomplay e KKBOX são rotas relevantes, mas a revisão não verificou uma série
  territorial completa. Mercado de atuação do serviço não prova chart local;
  cobertura anunciada por scraper externo não é evidência do publicador.
- [Last.fm geo.getTopTracks](https://www.last.fm/api/show/geo.getTopTracks) documenta
  a última semana por país e chave de API, sem janela anual arbitrária. Representa
  usuários Last.fm/scrobbles, não população ou streams de todas as plataformas.
- Spotify/YouTube Music/Apple e fornecedores licenciados continuam como rotas de
  descoberta por país. A documentação já existente de Soundcharts/Chartmetric no
  projeto não garante que todos os países tenham todos os anos. Os endpoints de
  documentação tentados não foram legíveis nesta revisão; nenhum teste autenticado,
  compra ou contato externo foi realizado.
- Não usar charts de artistas de um país, charts de gênero, playlists editoriais,
  votação de fãs, vendas de apps, cidades, totais mundiais de um artista ou
  views acumuladas globais como ranking nacional anual de músicas.

Cada território sem prova suficiente conserva status de investigação pendente.
Isso significa falta de evidência nesta revisão, não inexistência de atividade
musical ou impossibilidade permanente de obter dados.

## Comparabilidade: três braços, sem um total artificial de streams

**A — Painel principal por mesma plataforma/família.** Preservar Spotify Top Songs
como série própria e construir Apple e YouTube Music Songs em painéis separados,
com seus mercados e períodos observados. Ampliar o conjunto de países por fonte
sem trocar a fonte de uma série no meio do ano. Uma plataforma não representa
toda a população; reportar esse limite em cada painel.

**B — Charts nacionais multiprovedor.** IFPI SEA, IFPI MENA nacional e componentes
de streaming licenciados entram em grupo próprio. Ranks/índices ponderados são
observações válidas da fonte, mas não contagens brutas comparáveis entre países.
Métricas absolutas só são somadas dentro de definição/fonte/janela compatíveis.

**C — Popularidade composta e contexto.** TurnTable Top 100, Circle Digital,
Billboard Hot 100 e outros compostos ficam separados por versão metodológica.
Servem para testar a robustez das conclusões do braço de streaming. Agregados
MENA/Norte da África permanecem regionais e nunca viram réplicas nacionais.

Para comparar temas líricos entre fontes, usar prevalência no repertório
selecionado, com denominadores explícitos, e contrastes dentro de fonte/ano. Não
usar coeficiente de fonte ou normalização por rank como prova de que públicos e
mercados foram tornados equivalentes. Usar mercados com sobreposição de fontes
para medir concordância/diferenças e reportar resultados por braço.

### Janela e profundidade

1. Manter 2018–2026 e corte 15/10/2026 do freeze atual. Uma fonte lançada em 2025
   não preenche anos anteriores por extrapolação. Os novos anos ausentes ficam
   marcados, não recebem o chart corrente repetido.
2. Auditar calendário nativo completo e profundidade em todos os períodos; seguir
   o contrato atual de calendários completos para seleção principal. Uma sensibilidade
   de cobertura ≥95% pode ser proposta separadamente, sem mudar o critério vigente.
3. Para fontes com primeira semana no meio do ano, usar esse ano como parcial e
   começar a análise anual principal no primeiro ano integral auditado. Datas de
   lançamento não são garantia de arquivo recuperável.
4. Em 2026, comparar até a mesma fronteira de observação, respeitando semanas
   completas e timezone; armazenar publicação e início/fim de observação separados.
   Não somar charts diários e semanais sobrepostos.
   O anúncio SEA de 2025 cita publicação na terça, enquanto o hub atual anuncia
   quarta; esse detalhe deve ser versionado sem confundir publicação com janela
   de consumo. O título Top 100 da Apple declara a profundidade, mas não substitui
   a conferência efetiva de cada país/período.
5. O braço comum inicial pode usar **Top 20 semanal** nas fontes em que essa
   profundidade está completa, além de um Top 20 anual derivado comum. A seleção
   por cotas variáveis continua como análise principal/sensibilidade própria;
   Top 100/200 profundos ficam em painéis separados.

Um chart semanal Top 20 pode gerar mais de 20 músicas distintas no ano, mas
não revela o que ocorreu abaixo da posição 20. Essa união não passa a ter a
mesma cobertura de um Top 200 semanal. Déficits anuais permanecem explícitos.

### Quando a fonte fornece somente posições

Não inferir streams nem ordenar o ano pela soma das posições (que favoreceria
perversamente posições piores). Proposta para experimento, não método já adotado:

`S(i,c,y,f,K) = (1/T) × Σ_t I(i no Top K válido em t) × (K + 1 − r(i,t))/K`.

T é o número de períodos esperados da janela completa, K é a mesma profundidade
em todos os períodos comparados, r é a posição. O índice mede **exposição no
Top K**, não consumo. Contribuição zero fora do Top K é definição do índice,
não afirmação de zero streams; período faltante não vira zero e bloqueia o
calendário principal. Não aplicar T de 52 indistintamente a todos os anos ou
calendários semanais. Publicar também presença, pico e tamanho da união.

Comparar esse índice com posição mediana/recíproca e com o chart anual oficial
quando existir. A escolha precisa de sensibilidade e não pode substituir a
série de contagens observadas existente sem uma nova versão de protocolo.

### Cotas, identidade e validação

Não atribuí cotas de 100–500 aos 182 novos códigos simplesmente por criarem uma
linha. A soma dos pisos de 100 em 250 entradas já seria 25.000 vínculos/ano antes
de qualquer distribuição ou exclusão de áreas de referência; mostra por que
copiar a regra antiga sem recalibrar orçamento e estimando seria inadequado.

Antes de incorporar países, recalcular a alocação sobre o universo efetivamente
elegível, preservando ausentes no inventário. Simular raiz da população, piso/teto
e orçamento por **união global de edições/gravações**, com cenário de diversidade
e outro sem ela. Metas de quota não garantem precisão ou existência de posições.
Não preencher falta de letra avançando para músicas menos populares.

Registrar obra, gravação e item de chart separadamente. IFPI/TurnTable/Apple podem
agregar versões; um item agregado não identifica automaticamente uma gravação ou
letra. Guardar política da fonte, componentes conhecidos, IDs nativos e evidência
da edição. Ambiguidades permanecem em revisão. O gate de adjudicação por hash
continua obrigatório antes de qualquer inferência; não foi alterado.

Validação de incorporação: gold set local/multilíngue e dupla revisão em casos
ambíguos; conferir charts em períodos do início/meio/fim de cada ano, depois
auditar todo o calendário. Reportar missingness por país/ano, língua, fonte e
posição. Avaliar concordância Top K entre fontes sobrepostas e repetir resultados
com/sem novas fontes, países, índices de rank e fontes compostas. Não somar
observações de espelhos como eventos independentes.

## Implementação priorizada

| Ordem | Trabalho | Definição verificável de pronto |
|---|---|---|
| 1 — concluído | Universo ISO/M49 e exceções; tabela país/ano; registro de fontes e leads | 250 códigos únicos, 2.250 células, hashes dos inputs e testes offline; nenhum novo ready/import |
| 2 — piloto documental/técnico | NG streaming/composite; KE/GH/TZ/UG em Mdundo; LK/NP/KZ/KH em Apple | Confirmar audiência territorial, unit/versionamento, arquivo, profundidade e canal autorizado; nenhuma hipótese vendida como cobertura |
| 3 — séries comuns | IFPI SEA e MENA nacionais; comparação com plataforma no mesmo mercado | Calendarização completa por ano e família; agregados regionais não entram em observações nacionais |
| 4 — arquivo e acesso | Diligência de fonte nacional para África francófona, Sul/Centro da Ásia e pequenas ilhas; fontes licenciadas quando justificadas | Cada país com fonte verificável ou motivo/pendência; cotação e escopo antes de qualquer compra; histórico não demonstrado permanece ausente |
| 5 — adapters | Reutilizar `sources/`, `adapters/files/`, provenance e catálogo; acrescentar adapter apenas onde houver schema diferente | Fixtures de parsing, datas, paginação, rank/contagem, versão/fonte conflitante; reexecução idempotente; bruto/hash preservado quando permitido |
| 6 — desenho amostral | Recalibrar cotas e publicar três braços comparáveis | Orçamento sobre tarefas únicas, custos piloto reais e sensibilidade; diffs de seleção/cobertura revisáveis |
| 7 — coleta limitada | Somente após piloto documentado e escopo de fonte/período | Limites de requests/tempo/custo, retry/backoff, manifestos, zero promoção automática de identidade/letras |
| 8 — artigo | Atualizar frame geográfico, mapa de ausências, vieses e análises por braço | Claims ligados à versão do dataset; não afirmar representatividade mundial sem evidência |

O próximo piloto proposto tem nove mercados: NG/KE/GH/TZ/UG e NP/LK/KZ/KH,
com até três períodos de teste por fonte (início/meio/fim de um ano candidato),
no máximo duas páginas por período e três tentativas com backoff. Isso é um teto
de 27 combinações mercado/período por fonte escolhida, até 162 requests se todas
exigirem duas páginas e três tentativas; não constitui orçamento financeiro nem
prova de calendário. Não executar chamadas a fornecedor cobrado ou autenticação
sem antes documentar o canal e seu custo. Uma fonte sem arquivo temporal adequado
é encaminhada ao braço prospectivo, sem simular os anos faltantes.

Não modifiquei o `config/countries.yaml`, que serve à descoberta operacional, nem
o banco, ranking, cotas ou workers em andamento. O inventário fica separado em
`research/global_inventory/`; a integração no catálogo operacional é fase posterior.
`metadata/geography.py` ainda contém um mapa parcial e níveis regionais diferentes
da hierarquia publicada M49 (por exemplo, tratamento de MK/CY e níveis das Américas).
A nova referência corrige o inventário, mas não reclassifica silenciosamente
resultados históricos; migrar o enriquecimento exige versão e comparação de outputs.

## Autorização e encerramento

Preservo o relato de autorização mundial dado pelo responsável. Esta revisão
não o substitui nem o invalida. Para cada fonte, documentar separadamente o canal
técnico permitido, retenção, atribuição e publicação. Não foram enviados pedidos
a fornecedores, criadas contas, feitas compras, contornados bloqueios ou iniciadas
coletas históricas em massa/Vertex.

A investigação de páginas públicas e referências geográficas foi realizada em
08/11/2026. O gerador é offline e possui testes contra omissão geográfica,
confusão regional/nacional, repertório restrito, falsa prontidão e confusão entre
storefront e país do chart. Diligência documental não certifica a autenticidade
de cada linha histórica nem substitui o piloto de ingestão proposto.
