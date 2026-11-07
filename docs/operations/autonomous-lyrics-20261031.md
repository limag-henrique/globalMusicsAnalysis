# Recuperação autônoma ampliada — 31/10/2026

O pesquisador confirmou **2018–2026**, corte **15/10/2026**, e autorizou a
aquisição de letras também dos candidatos provisórios de calendários incompletos.
As cotas principais por país/ano foram mantidas, sem expansão. A meta comunicada
é recuperar as letras corretamente atribuídas; o usuário fará a análise posterior.

## Universo e significado

- Seleção de calendários elegíveis: 58.290 vínculos, 22.835 candidatos distintos.
- Adicional provisório: 16.445 vínculos país/ano.
- União para aquisição: **27.032 candidatos distintos**, 74.735 vínculos.
- Janela: 612 células país/ano. Cotas somam 9.980 por ano; lacunas não viram zero
  consumo, nem uma declaração de que todas as 89.820 posições desejadas existem.

"Top N" significa ordenação dos totais anuais de reproduções **observadas na
parada**, por país, dentro de uma fonte principal. Não são todas as reproduções
fora da parada. Uma mesma música pode ocupar posições diferentes em vários
países/anos. A união deduplica o trabalho sem eliminar esses vínculos.

O conjunto provisório representa apenas períodos observados; não é ranking anual
definitivo. É gravado em `provisional.jsonl`, separado de `selection/selected.jsonl`.
Os vínculos no payload SQLite recebem `selection_status`, plataforma, posição,
cota e cobertura. Não se completam cotas com posições inferiores por falta de letra.

## Implementação e execução

Comando implementado e iniciado em segundo plano com janela oculta:

```powershell
uv run --frozen python -u scripts/autonomous_lyrics.py --hours 8
```

O processo mantém um lock compartilhado com o executor anterior. Não executar
ambos ao mesmo tempo. O prazo é um limite de despacho; pedidos em andamento são
concluídos antes de sair. Há até três rodadas, com espera de 15 minutos quando a
rodada anterior teve falhas transitórias. Não existe promessa de completar todos
os textos em oito horas: acesso, cobertura e identidade podem permanecer pendentes.

Etapas: preparar seleção → indexar vínculos → reaproveitar documentos locais para
novos candidatos → auditar evidências salvas → recuperar ausentes/ambíguos →
registrar resultado e pendências. O processamento efetivo foi observado no estado
`recovering`, com seis trabalhadores e sem erros no log de inicialização.

Melhorias desta rodada:

- Fontes inválidas/conflitantes não superam uma fonte válida incompleta apenas
  por terem mais datas; não se usa fonte conflituosa nem para o recorte provisório.
- Busca textual LRCLIB com verificação exata do resultado, conservando qualificadores
  de versão e retendo casos com edições divergentes.
- Busca pública Genius para descobrir o URL real; exige título e artista exatos
  no resultado e na página, antes de extrair seus contêineres de letra.
- Chromium padrão como alternativa de renderização de páginas Genius já descobertas,
  até 200 páginas e duas renderizações simultâneas, sem login, stealth ou contorno
  de CAPTCHA/bloqueios. Conteúdo sem metadados verificáveis não é aceito.
- Registro SQLite de tentativas por identidade/método, com resultado anterior.
  Falhas de recuperação de um texto em quarentena não apagam o texto anterior.
- Reutilização dos blobs e caches anteriores. Tarefas interrompidas permanecem
  identificadas; não são apresentadas como processos ainda vivos.
- Auditorias offline registradas em `evidence_audits`, sem transformar casamento
  de metadados em certificação de integridade textual.

Resultados permanecem `identity_validated=false`, `completeness_validated=false`
e `classification_ready=false` até a evidência de gravação/versão/transcrição
requerida pelo protocolo. Isso evita repetir classificações de letras erradas.
Não há chamada Gemini ou habilitação de despesas nesta execução.

## Acompanhamento

```powershell
Get-Content data/runtime/autonomous-lyrics-20261031/status.json
Get-Content data/runtime/autonomous-lyrics-20261031/errors-resumed.log -Tail 20
```

Seleção e manifestos: `data/derived/annual_revision/autonomous-2018-2026-20261031/`.
Acervo e tentativas: `data/derived/lyrics/quota-20261030/acquisition.sqlite`.
Textos únicos: `data/derived/lyrics/quota-20261030/texts/<sha256>.txt`.

43 testes de ingestão/aquisição/descoberta passaram. Cobrem fronteiras de cotas,
separação provisório/definitivo, fonte conflituosa, descoberta de URL, rejeição de
outra versão, último verso, cache, hash e retomada sem repetir tarefas concluídas.
Ruff passou. Todo o material histórico foi preservado.

## Continuação e correção de pausas — 31/10, 11:41 BRT

O v7 encerrou às 11:37:26 BRT com `PermissionError` ao substituir somente
`status.json` (WinError 5). O processo terminou e o wrapper assumiu a fila
automaticamente: v9, PID 16768, verificado vivo e em recuperação. O staging
também terminou em snapshot `abba0728dfdc70140c4e5ab7732b5f3b4e1359822ae9aa6a8d75b4e3bc395d4f`.
Esse encerramento não apagou os textos duráveis do SQLite.

O código posterior ao início do v9 adiciona publicação de status atômica com
tentativas curtas para conflitos de compartilhamento no Windows. Uma falha
persistente de telemetria gera aviso no stderr e preserva o último JSON completo;
não interrompe aquisição nem staging. Falhas dos dados duráveis continuam fatais.

A mesma revisão evita três repetições imediatas internas após erro de fonte.
O agendador assume as retentativas e respeita `Retry-After` em segundos ou data
HTTP. Respostas concorrentes menos restritivas não encurtam pausas existentes.
Quando LRCLIB e Genius estão pausados, novas músicas aguardam sem reservar nem
consumir uma tentativa; resultados em andamento são drenados normalmente.
Caches já verificados continuam disponíveis na camada HTTP.

Essas mudanças não estavam carregadas no v9. O wrapper de
`data/runtime/identity-repair-v10-20261031` aguarda seu handle real e executará
o código atualizado por oito horas, com a seleção `reconciled-russia` e sem
concorrência de escritores. Nenhum processo de aquisição foi encerrado à força.
28 testes passaram para aquisição, descoberta, atualização nativa, staging e
publicação de status, incluindo preservação do status anterior e pausas.

## Genius sem JSON-LD e recuperação local

A inspeção de respostas preservadas mostrou páginas com contêineres completos
de letras, mas sem JSON-LD. O extrator agora pode identificar a música principal
por `window.__PRELOADED_STATE__`, decodificando apenas o literal JSON sem executar
JavaScript. Exige `currentPage=songPage`, a referência explícita `songPage.song`,
o mesmo ID já aprovado na busca Genius, título exato, todos os artistas
participantes resolvidos e permitidos, além da igualdade entre URL da entidade
e `og:url` HTTPS do Genius. Não percorre músicas recomendadas para encontrar
um casamento. Outra versão, ID divergente, artista ausente/desconhecido ou URL
divergente continuam recusados.

O teste de regressão cobre essas recusas e preservação do último verso.
23 testes de aquisição e descoberta passaram. Uma resposta real previamente
recusada passou com o ID 5556181 e 2.330 caracteres, sem publicar a letra em logs.

O replay `data/runtime/offline-main-entity-replay-20261031` reexamina apenas
lacunas da seleção atual em caches locais, com transporte de rede proibido.
Resultados ficam em `offline-replay` e passam novamente pela auditoria de
identidade/metadados antes de preencher lacunas no staging. O wrapper
`data/runtime/postgres-stage-after-replay-20261031` aguarda o processo real do
replay antes de importar o snapshot. A coleta principal não é interrompida.

## Decodificação de strings e recusa de incompletas

A decodificação do estado Genius agora segue escapes de strings JavaScript
explicitamente, sem `eval` ou execução de código. A inspeção real encontrou
`\$`, que JavaScript decodifica como `$`; o decodificador anterior mantinha
uma barra incompatível com o JSON interno. O teste cobre esse caso, apóstrofos,
aspas, Unicode, escapes hexadecimais e rejeição de escapes inválidos.

O novo caminho de identidade recusa estados `lyricsState` declaradamente
incompletos. A descoberta também recusa `lyrics_state` incompleto na busca
ou no detalhe da API e preserva esse campo na prova de créditos. A auditoria
marca provas antigas que explicitamente declarem incompletude. Estado ausente
ou `complete` não é promovido a certificação de transcrição.

25 testes de aquisição/descoberta passaram. O replay
`data/runtime/offline-js-literal-replay-20261031` concluiu 10.515 candidatas
examinadas, mais cinco recuperadas, 89 já recuperadas e zero erros/requisições
de rede. O staging posterior está registrado em
`data/runtime/postgres-stage-after-js-replay-20261031`. A continuação v10
carregará essas mudanças ao assumir a fila; o processo v9 ativo não foi reiniciado.

## Atualização de metadados com a fila drenada

O código v11 verifica alterações no mapa de provas nativas a cada minuto,
quando não há futures ativos. Nesse ponto, sob o lock exclusivo já existente,
aplica as provas e reconstrói os payloads das candidatas ainda não despachadas
com os nomes atuais do SQLite. A fila conserva suas identidades e resultados
anteriores; não cria reservas nem reapresenta automaticamente tarefas já
concluídas na mesma rodada. Alterações dessas últimas seguem sinalizadas para
reconciliação na próxima rodada. Durante atividade ininterrupta, a atualização
aguarda uma fronteira sem tarefas em voo.

Isso evita que uma rodada longa, limitada por pausas das fontes, continue
consultando nomes antigos para toda a fila. As posições e cotas permanecem
inalteradas. O teste verifica os novos nomes na fila e a preservação do texto,
status, associações e idempotência. 17 testes de atualização/aquisição passaram.

O processo v10 PID4240 continuou vivo e não foi interrompido. O wrapper em
`data/runtime/identity-repair-v11-20261031` aguarda esse handle real para iniciar
a continuação por oito horas com o código atualizado; nenhum segundo escritor
foi iniciado em paralelo.

## Retomada após reinicialização — 31/10, 16:39 BRT

A máquina reiniciou às 16:36:29 BRT. A inspeção CIM confirmou ausência de
todos os processos anteriores antes de qualquer retomada. O SQLite passou
em `PRAGMA quick_check` (`ok`), com 33.247 tarefas históricas preservadas.
Não havia tentativa v11 previamente reservada. O PostgreSQL recuperou o WAL
e declarou disponibilidade às 16:39:07; `SELECT 1` confirmou o acesso.

A primeira tentativa de retomada da aquisição, PID6408, tentou preparar a
seleção antes de o banco terminar a recuperação e encerrou sem entrar na fila.
Depois de verificar seu término e a disponibilidade SQL, foi iniciada a v11
PID6168. Logs anteriores foram preservados; a execução válida usa
`resume-ready.log` e `resume-ready-errors.log`. O coletor nativo PID2580 retomou
6.561 respostas em cache (6.539 resolvidas na primeira publicação), sem
reconsultar IDs já armazenados. Não há aquisição concorrente escrevendo no SQLite.

O novo código de inicialização aguarda a disponibilidade SQL por até dois
minutos antes de preparar a seleção. Os testes cobrem recuperação temporária,
expiração e fechamento do engine de sondagem. 29 testes relevantes passaram.
O script PowerShell passou na análise sintática e, nas próximas inicializações,
gravará o log PostgreSQL fora do diretório de dados, evitando o conflito de
compartilhamento observado durante a recuperação. O log antigo foi preservado.

O replay local adicional em
`data/runtime/offline-reboot-metadata-replay-20261031` examinou 10.386 lacunas,
recuperou mais uma letra e terminou com zero erros e zero requisições de rede.
Uma nova importação PostgreSQL e a interface local de revisão foram iniciadas
depois de confirmar a recuperação do banco.

## Importação de reparos pelo próprio coletor — v12

O coletor agora agrupa propostas locais por candidata e hash antes de importar.
Admite preenchimentos de lacuna e reparos estritos do hash anterior sinalizado,
usando as mesmas verificações de nomes/fontes do staging. Textos divergentes
mantêm conflito; resultados atuais sem flags ficam protegidos. A importação
recusa qualquer fila com tarefas `running` e não usa transporte de rede.

Cada troca conserva o resultado anterior em `recovery_attempts.previous_result`
e em `replaced_unverified_result`, verifica o hash anterior e reutiliza o blob
novo pelo SHA256. As flags de gravação/transcrição/classificação continuam
falsas. A execução repetida não reimporta candidatas já reconciliadas. O manifesto
de staging também informa `repaired_candidates`, distinguindo reparos já presentes
na fila de alternativas aplicadas apenas pelo overlay do banco.

33 testes passaram, incluindo preenchimento e reparo, histórico completo,
idempotência, conflito, fila ativa e arquivo anterior corrompido. A troca para
v12 foi feita numa pausa confirmada do v11 PID6168, com zero tarefas em execução,
identidade/tempo de criação do processo conferidos e término confirmado antes
de abrir o novo escritor. A primeira checagem de troca foi recusada antes de
qualquer parada; a verificação seguinte confirmou a fronteira ociosa.
Evidência: `data/runtime/identity-repair-v12-20261031/idle-handoff.json`.

A v12 PID3660 iniciou às 17:10:13 BRT e importou 6.234 candidatas locais:
5.851 reparos e 383 lacunas. Houve um conflito e zero arquivos de replay inválidos.
A verificação dos 6.234 registros históricos encontrou zero divergências de
proveniência e zero liberações indevidas; o SQLite passou em `quick_check`.
Resumo e verificação em `offline-import.json` e `offline-import-verification.json`
no diretório dessa execução. O coletor nativo PID2580 permaneceu ativo.

## Pausas persistentes entre processos

O novo `PacedHTTP` grava prazos de pausa por domínio em
`http-cache/provider-cooldowns.sqlite`. Usa timestamps de época para atravessar
reinicializações e converte o prazo restante para relógio monotônico ao iniciar.
O UPSERT transacional conserva o maior prazo, de modo que uma resposta 5xx
atrasada não encurta uma pausa de rate limit já gravada. Cache verificado
continua utilizável durante a pausa, sem acesso à rede.

Estado corrompido não é ignorado silenciosamente. Não são guardados tokens,
letras ou credenciais nessa tabela. O diagnóstico de espera passa a informar
`provider_retry_in_seconds`, além do menor prazo usado pelo agendador.
35 testes passaram, cobrindo retomada de processo sem novo acesso antecipado,
cache durante pausa, expiração, resposta concorrente menos restritiva e estado
corrompido. A alteração está no código em disco e será carregada na próxima
inicialização; a v12 PID3660 já estava carregada e continuou ativa.

## Créditos de produção e intérpretes na recuperação LRCLIB

A inspeção de respostas locais encontrou créditos de Spotify contendo autores
e produtores junto dos intérpretes. O novo caminho de recuperação só admite
um nome LRCLIB diferente da lista integral se uma prova Genius identificar
todos os nomes solicitados por seus papéis e o nome observado corresponder
exatamente à lista completa de intérpretes principais/participantes dessa prova.
Exige ID numérico e URL Genius, título correspondente e preservação de versão.
Não presume aliases, formação de bandas ou ausência de convidados.

O resultado guarda `credit_binding_provider`, `credit_binding_url`,
`credit_binding_title` e `provider_credit_evidence`, além dos nomes LRCLIB
observados e da lista solicitada. A auditoria reexecuta a verificação; mudar
o título, retirar um produtor necessário ou introduzir convidado invalida
o casamento. A reconciliação limpa apenas a divergência de nomes, sem aprovar
gravação, transcrição ou classificação. Textos LRCLIB divergentes são recusados.

A tentativa ocorre após falha de extração direta, aproveita linhas já lidas e
limita consultas estruturadas adicionais. 36 testes passaram para aquisição,
descoberta e importação local, incluindo papéis completos, outra versão,
intérprete ausente, convidado extra, grupo distinto e múltiplos textos.
O replay sem rede está em `data/runtime/offline-credit-role-replay-20261031`;
o staging aguarda seu processo em `data/runtime/postgres-stage-after-credit-role-20261031`.
O coletor v12 e o coletor de metadados continuam em suas execuções carregadas.

## Sondagens limitadas de APIs já configuradas — 31/10, 17:47–17:55 BRT

Foi conferida somente a presença de credenciais existentes, sem expor valores.
O fluxo Spotify Client Credentials e a consulta individual do catálogo retornaram
200 com URI nativa exata. Uma única consulta de teste em lote retornou 403;
o lote não foi repetido. O [guia de migração oficial](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide)
documenta a retirada de `GET /tracks` no modo de desenvolvimento e a substituição
por consultas individuais. Não foi inferido o modo da aplicação apenas pelo 403.

A credencial legada `GENIUS` também foi localizada, mas uma única consulta à API
oficial retornou 401. A autenticação não foi repetida. Nenhum token, segredo
ou resposta de autenticação foi persistido; os registros contêm apenas status
e metadados públicos filtrados. Evidências em `spotify-api-probe-20261031` e
`genius-api-probe-20261031`, sob `data/runtime`.

A [consulta individual Spotify](https://developer.spotify.com/documentation/web-api/reference/get-track)
foi aplicada a dois casos prioritários. `2me5SocGcxPzFwPe03my19` retornou a URI
exata, mas sem título, duração ou ISRC disponíveis; a música continua sem nome,
sem inferir um título pelo artista. RR 9.1 retornou duração de 200.506 ms,
ISRC e álbum L' Affranchi. A alternativa LRCLIB preservada tem o mesmo álbum,
mas duração nula. Isso não resolve a diferença entre as duas letras: o conflito
permanece. A comparação está em `spotify-api-probe-20261031/conflict-duration-comparison.json`.

As sondagens não alteraram rankings, cotas, letras selecionadas ou despesas.
Os processos de coleta existentes permaneceram ativos enquanto se avaliava
essa possibilidade de acesso autenticado.

## Identificadores nativos de artistas preservados nas fontes

O extrator `scripts/extract_native_artist_identities.py` lê somente os dicionários
de músicas dos pacotes brutos Spotify já baixados, após conferir o SHA256 de cada
arquivo ZIP. Une registros apenas pela URI exata da faixa selecionada e exige
alinhamento completo entre nomes e URIs de artistas. Vetores incompletos,
identificadores inválidos e dicionários truncados são recusados. As linhas de
ranking não precisam ser lidas novamente e não são alteradas.

O resultado imutável está em
`data/derived/annual_revision/native-artist-identities-20261031`: 18.500 das
27.156 candidatas Spotify têm evidência de IDs dos artistas, cobrindo 8.638
artistas. Não houve conjuntos conflitantes de IDs nem grafias alternativas
observadas para o mesmo artista nessa fonte. Permanecem 8.656 candidatas sem
essa evidência nos pacotes. Três testes passaram para URI exata, isolamento
das linhas de ranking, vetores incompletos, truncamento e conflitos.

A comparação com os metadados oficiais disponíveis naquele momento encontrou
8.196 faixas em comum: 7.869 concordaram em título e lista ordenada de artistas
após a normalização já usada no projeto; 327 tiveram alguma divergência nominal.
Há casos de título localizado em outro idioma e inclusão de participação no
título atual. A comparação está em `public-metadata-comparison.json` nesse
diretório. Esses casos não foram convertidos em aliases de letras automaticamente.
Não houve consulta de rede, mudança de cota/ranking ou liberação para classificação.


### Proteção do cliente legado Genius

O cliente legado passa a exigir título/versão e créditos exatos na busca e identidade estruturada na página antes da extração. Nomes com vírgulas são preservados; respostas 401/403 desativam o token nessa instância. JSON-LD com múltiplas músicas distintas é recusado por ambiguidade, inclusive quando uma recomendação corresponde ao pedido. Os coletores já iniciados não recarregam essas alterações. Validação: 40 testes focados passaram; processos de letras e metadados permaneceram ativos, sem reinício. Esta alteração não certifica retroativamente os textos existentes nem libera classificação.


### Retomada com histórico preservado

A reindexação agora usa reconcile_reindexed_task: mantém revisões anteriores de título/artista, acrescenta a identidade substituída quando há mudança e atualiza os vínculos da seleção sem apagar a necessidade de reconciliação. Reaplicar a mesma seleção é idempotente. Validação: 19 testes de atualização de metadados/aquisição passaram e Ruff passou. Os coletores ativos não foram reiniciados. Iniciada uma nova recuperação exclusivamente local em data/runtime/offline-post-identity-guard-20261031, PID real 20080, 20.651 candidatos examináveis; transporte sem rede e propostas separadas da base escrita pelo coletor. Não representa validação definitiva das letras.


### Resolução explícita da entidade principal e nova recuperação local

JSON-LD com mainEntity explícita agora resolve a referência @id entre os nós do documento; referências ausentes ou múltiplas músicas sem vínculo inequívoco são recusadas. Uma música recomendada não substitui a entidade principal. Validação: 37 testes focados passaram e Ruff passou. A recuperação local PID 20080 terminou em 2026-10-31T21:26:48Z: 20.651 candidatos processados, 115 novas propostas, 62 propostas previamente existentes, zero erros, zero rede. O snapshot PostgreSQL 8a53d07deac816f1e388bc9daf49959da8c918c2337a55a066e9332ec9e96ee4 foi persistido e conferido: 28.373 candidatos, 16.363 textos distintos atuais, 108 novos blobs e 19.467 blobs históricos deduplicados. Nenhum candidato liberado para classificação paga. Novas propostas podem representar reparos, não apenas preenchimento de lacunas. Os coletores originais permaneceram ativos.


### Auditoria de conteúdo parcial na revisão

A versão lyrics-text-quality-v3 sinaliza avisos explícitos de prévia em inglês, português e espanhol. A aquisição recusa esses textos; a preparação PostgreSQL recalcula flags a partir do blob verificado, incluindo registros antigos, preservando originais. Ausência de aviso não certifica completude. Validação: 28 testes focados e Ruff passaram. Snapshot 68332c8cd60217169f750fffb09c795cec2bc74f2e231b5525bf9ff8dd43a7fb persistido e conferido em 2026-10-31T21:28:32Z: 28.373 candidatos, 16.363 textos distintos, zero novos blobs, zero candidatos liberados para classificação paga.


### Inventário deduplicado das lacunas

O relatório staging-coverage.json agora distingue candidatos únicos de posições por país/ano e exporta missing_text_candidates, ordenados por quantidade de vínculos e melhor posição, sem duplicar músicas compartilhadas. Snapshot 68332c8c: 28.373 candidatos, 18.436 com texto e 9.937 sem texto; 67.267 posições com texto, 18.823 posições selecionadas sem texto, 3.730 lacunas de ranking e 25 células vazias. Contagem de texto não significa letra validada. Três testes passaram e Ruff passou. Os coletores de letras PID 3660 e metadados PID 2580 foram confirmados ativos.


### Verificação integral dos blobs armazenados

Em 2026-10-31T21:29:47Z foram conferidos hashes SHA-256 e UTF-8 de 17.642 blobs locais distintos referenciados por 20.035 tarefas históricas e de 19.467 blobs históricos PostgreSQL (incluindo comprimento armazenado), sem erros. Evidência: data/runtime/lyric-storage-integrity-20261031.json. Não é prova de correspondência/completude. A revisão atual 68332c8c tem 20 candidatos/32 vínculos com indicadores de texto curto, muito curto, início potencialmente ausente ou aviso de prévia; inventário de recuperação em data/runtime/current-short-lyrics-review-20261031.json. Texto original preservado, nenhuma chamada de rede ou paga nesta verificação.


### Recuperação local com auditoria de qualidade atualizada

O replay agora verifica o hash e recalcula flags dos blobs antigos antes de selecionar reparos, apenas em memória e sem escrever na SQLite do coletor. Propostas novas só são salvas quando a auditoria final não indica quarentena nem flags; o fallback malsucedido não transforma a proposta anterior sinalizada em recuperação aceita. Ruff e 23 testes relacionados passaram. Execução data/runtime/offline-quality-v3-replay-20261031, PID 4244, encerrada em 2026-10-31T21:32:08Z: 20.656 candidatos processados, seis novas propostas, 177 existentes, zero erros, zero rede. Seis propostas aguardam incorporação sob as mesmas verificações de identidade/hash; não certificam completude. Coletores principais confirmados ativos durante a execução.


### Incorporação de propostas e reparo com flags recentes

usable_cached_repair agora reavalia a qualidade do blob antigo quando os metadados históricos ainda não possuem flags: exige SHA-256 correspondente, UTF-8 válido e indicador atual de qualidade, preservando o resultado anterior. Blob alterado ou inacessível não habilita substituição. Dezesseis testes focados passaram e Ruff passou. Snapshot PostgreSQL 2ed750f1790f02463422642c44d431a5480e5913020185e7ea25aec9cee4a4bb conferido em 2026-10-31T21:33:13Z: 28.373 candidatos, 16.366 textos distintos, cinco novos blobs históricos (19.472 no total), zero liberações para classificação paga. Seis propostas não equivalem a seis blobs novos devido a deduplicação/conflitos/eligibilidade. Metadados nativos alcançaram 13.144 resolvidos; coletores principais confirmados ativos.


### Continuação v13 com alternativas nas retentativas

recover_with_fallback tenta AZLyrics e Musixmatch após descoberta LRCLIB/Genius malsucedida mesmo em candidatos já tentados; usa o mesmo HTTP com cache/limites e exige auditoria de identidade/qualidade. Dezesseis testes focados e Ruff passaram. A versão atual v12 não foi reiniciada. Foi iniciada uma espera Windows por handle do PID real 3660: wrapper real PID 9752 (launcher 13468), criado às 18:36:39 BRT, estado waiting_for_previous_owner confirmado em data/runtime/identity-repair-v13-20261031/dependency/status.json. Após encerramento do proprietário, executará autonomous_lyrics.py por oito horas com prefixo exact-discovery-v13 e mesma seleção. O lock exclusivo continua obrigatório. Nenhum segundo coletor de letras foi iniciado em paralelo.


### Pausa por disponibilidade das quatro fontes

search_retry_delay aceita conjunto explícito de provedores; a fila agora usa LRCLIB, Genius, AZLyrics e Musixmatch, permitindo trabalho quando qualquer uma dessas fontes está disponível. Bloqueio por domínio e Retry-After continuam respeitados. Trinta e quatro testes passaram e Ruff passou. O worker v13 já enfileirado carregará essa versão ao iniciar; v12 PID 3660, metadados PID 2580 e espera PID 9752 foram confirmados vivos às 20:18 BRT. Metadados: 19.313 resolvidos; v12: 18.996 itens restantes na primeira rodada, sem chamadas pagas. Novo replay exclusivamente local iniciado em data/runtime/offline-native-19k-replay-20261031, processo real 3112, launcher 17440.


### Replay após 19 mil metadados confirmados

A execução offline-native-19k-replay-20261031 (PID 3112) terminou em 2026-10-31T23:22:54Z: 20.489 candidatos examinados, 341 novas propostas, 173 propostas já existentes, zero erros e zero requisições de rede. O processo foi acompanhado por identidade Windows e avanço de leituras durante a preparação antes de seu primeiro contador, sem reinício. A preparação de próximas execuções agora publica status antes de verificar seleção/metadados e a cada 500 tarefas na revisão de qualidade, usando publish_status com retentativas de compartilhamento; Ruff e compilação passaram. Iniciada preparação de novo snapshot PostgreSQL; as propostas permanecem pendentes de incorporação e revisão até confirmação do snapshot.

Snapshot confirmado: 30e9d86d7f5ba812cc0d0666615a1d587174c099af885b674ea1239bc5ece7f4, persistido em 2026-10-31T23:24:06Z, 28.373 candidatos, 16.507 textos distintos atuais, 320 novos blobs históricos (19.792 totais), zero candidatos liberados para classificação paga. Inventário atualizado: 18.631 candidatos com texto, 9.742 sem texto; 68.342 posições com texto e 17.748 posições selecionadas sem texto. As 3.730 lacunas de ranking permanecem. Não confundir esses contadores com letras corretamente atribuídas/completas certificadas.


### Textos compartilhados por identidades diferentes

Nova auditoria identity_collisions verifica título e intérpretes normalizados para cada SHA-256. A análise do snapshot 30e9d86d encontrou 106 grupos/238 candidatos: 51 grupos com títulos diferentes e 73 com intérpretes diferentes (há sobreposição). São sinais de revisão, não prova automática de erro: covers, versões e nomes alternativos podem explicar alguns casos. Inventário em data/runtime/shared-text-identity-review-20261031.json. Cinco testes de colisão/staging passaram; Ruff passou. Snapshot 7900e3d462c12fb1a57229aacedf745d340552e3e2e6f39a082d0bff11a0a7f3 persistido, 28.373 candidatos, 16.507 textos distintos, zero blobs novos, alertas incluídos e zero liberação para classificação. Alvos atomizados em identity-audit/shared-text-repair-targets.jsonl, com candidato/hash/run_id; v13 os incorpora à prioridade apenas enquanto o hash suspeito corresponder ao resultado atual, preservando a lista antiga de reparos. Quatro testes de atualização/colisão passaram após integrar a prioridade. Nenhum texto foi escolhido ou substituído por essa auditoria.


### Preservação de versos no cliente legado Genius

Removidas limpezas genéricas que podiam apagar uma primeira linha terminada em Lyrics, a expressão You might also like dentro de um verso ou Embed no final da música. O cliente agora remove apenas uma linha inicial exatamente N Contributors e um cabeçalho exatamente igual ao título confirmado seguido de Lyrics. Versos com palavras semelhantes permanecem íntegros. Vinte e três testes de qualidade/identidade passaram, incluindo regressões para esses casos. A alteração protege futuras chamadas do cliente legado e não reconstrói automaticamente versos eventualmente perdidos em documentos antigos. O coletor moderno já usa extração integral dos contêineres.


### Validação conjunta do módulo de letras na máquina destino

Suíte tests/unit/lyrics: 374 testes passaram em 28,07 s, com --basetemp novo dentro de data/runtime no disco D:. A primeira execução encontrou cinco falhas ambientais porque tmp_path padrão ficava no C: e o BatchClassificationService exige o disco do projeto; a proteção de produção foi preservada. Dois testes de recovery_web foram atualizados para páginas simuladas com MusicRecording/título/artista exigidos pela nova conferência e para a versão v3 do derivador. A repetição expôs dois testes que liam manifesto UTF-8 com encoding padrão Windows e corrompiam Repositórios no caminho SQLite; leitura explicitamente UTF-8 corrigida nos testes. A execução final passou integralmente. Os adaptadores de classificação nesses testes são simulados, sem chamadas pagas. Isso verifica integração de software, não certifica todas as letras ou rankings. Coletores reais 3660/2580 e espera 9752 confirmados ativos durante a verificação.


### Evidência auxiliar de duração

Uma consulta pública controlada ao embed Spotify de 28fP6qcMGPfYOjrx8AOWFn retornou HTTP200, URI exata e duration=200506 ms (igual ao valor da consulta oficial anterior). spotify_entity passa a preservar duration_ms positivo inteiro sem tokens; apply_native_display_metadata o leva à resolução vinculada por hash/URI. Candidatos LRCLIB preservam duration_seconds quando presente. A auditoria sinaliza recording_duration_mismatch quando a diferença supera max(3 s, 2% da duração Spotify); ausência ou proximidade não valida gravação/letra/completude. O coletor já iniciado não recarrega o parser e registros antigos não ganharam duração por inferência. Trinta e sete testes focados passaram antes da regra comparativa, e 21 passaram após integrá-la, incluindo mismatch, aproximação e valor não finito. Nenhuma coleta ampla adicional de duração foi iniciada.


### Duração integrada à busca de alternativas

recover_with_fallback recebe metadata_resolution do candidato selecionado, mantendo título/artista originais na auditoria; uma divergência de duração passa a impedir aceitação antecipada e permite a tentativa AZLyrics/Musixmatch. A obtenção LRCLIB vinculada por créditos Genius também preserva a duração do registro. Dezoito testes focados passaram e Ruff passou, incluindo o cenário de duração divergente seguido de fonte alternativa. O resultado divergente continua disponível para revisão caso nenhuma alternativa passe. A execução v13 em espera carregará essa lógica ao iniciar, sem reiniciar v12. Processos 3660/2580/9752 confirmados vivos nesta etapa. Durações antigas ausentes continuam desconhecidas.


### Recuperação incremental sem reexaminar toda a seleção

replay_cached_quota_lyrics.py aceita --candidate-ids-file (JSONL candidate_id), exige lista não vazia e inteiramente contida na seleção atual, filtra a resolução de metadados e a leitura de blobs ao escopo solicitado, e publica SHA-256 da lista. Nenhuma cota/posição é alterada. Lista derivada de provas nativas verificadas por hash com retrieved_at posterior a 2026-10-31T23:18:56Z: 1.459 candidatos. Execução offline-native-incremental-20261031 terminou às 23:43:37Z em aproximadamente sete segundos: 568 elegíveis processados, 47 novas propostas, uma existente, zero erros/rede. Auditoria independente das 47 propostas confirmou pertença ao filtro e ausência de flags/quarentena; evidência proposal-verification.json. Ruff passou.

Snapshot 07d8a8324ef9bfce759fcaed73ad4a9830e763be7981a8ab875e8c78c198d4fc gravado e conferido às 23:44:20Z, incorporando também o avanço do coletor principal: 28.373 candidatos, 16.598 textos distintos, 176 novos blobs históricos (19.968 totais). Não atribuir todos os 176 blobs às 47 propostas incrementais. Cobertura atual: 18.715 candidatos com texto, 9.658 sem texto, 68.642 posições com texto e 17.448 posições selecionadas sem texto. Permanecem 3.730 lacunas de ranking; nenhum candidato liberado para classificação paga.


### Coleta limitada de duração para identidades suspeitas

O coletor nativo aceita --candidate-ids-file e --refresh-missing-duration; só consulta IDs da seleção Spotify e preserva provas anteriores em lotes imutáveis antes de atualizar a SQLite. Uma falha HTTP não substitui metadados positivos. Publica resolved_in_scope e duration_in_scope além do total global. Nove testes passaram, incluindo atualização restrita bem-sucedida e HTTP404 preservando a prova anterior; Ruff passou.

Lista de 228 IDs Spotify derivada dos 238 candidatos com texto compartilhado por identidades diferentes: data/runtime/priority-native-durations-20261031/candidate-ids.jsonl. Wrapper real PID24432 (launcher24640), criado às 20:47:50 BRT, espera o handle real2580 encerrar. Após isso tentará durações por até uma hora, com --skip-if-previous-provider-pause: não inicia se a execução anterior terminou em provider_access_paused/waiting_provider_cooldown. Estado waiting_for_previous_owner confirmado. Não há segundo coletor nativo paralelo nem novo download de letras nessa tarefa; a aquisição de durações ainda não começou. O lock nativo continua exclusivo.


### Duração considerada antes de encerrar a aquisição

A verificação recording_duration_mismatch foi centralizada em text_quality. fetch_candidate recebe expected_duration_ms e filtra versões LRCLIB divergentes antes de escolher texto/encerrar a busca. Isso evita que o fallback volte a retornar a mesma versão divergente antes de alcançar AZLyrics/Musixmatch e permite distinguir duas edições com título/artista iguais quando só uma duração é compatível. recover_with_fallback repassa a duração vinculada; o replay local também o faz. Chaves de propostas agora usam main-entity-native-display-v3 e a duração, preservando os artefatos antigos. Trinta e nove testes focados passaram e Ruff passou; cobrem alternativa HTML após duração divergente e versões LRCLIB indistinguíveis sem duração. Ausência de duração continua desconhecida; uma aproximação não certifica identidade/completude. A versão em execução não foi reiniciada.


### Planejamento verificável do replay incremental

Novo replay_new_native_metadata.py seleciona apenas IDs presentes na seleção e provas públicas Spotify recentes, com SHA-256/URI/nomes conferidos e timestamps com fuso. Plano guarda hashes da seleção, mapa e filtro; lista vazia encerra sem iniciar uma busca global. Três testes passaram (escopo, corte temporal, bytes alterados, URI errada e exigência de fuso) e Ruff passou. Execução offline-native-incremental-v3-20261031 terminou em 2026-11-01T00:01:21Z: 955 IDs recentes, 684 elegíveis processados, 49 propostas, zero erros/rede. As propostas são candidatas, não letras certificadas.

Novo wrapper real24684/launcher23428, criado às21:01:46 BRT de31/10, espera o handle real24432 (tarefa de durações) e então executa replay_new_native_metadata.py com o mesmo limite inferior23:43Z, incorporando os novos metadados publicados; waiting_for_previous_owner confirmado. Não há coleta paralela de letras por esse wrapper.

Snapshot5c5897c0fd39ff867b80261e4c30ff16de9adc12e93b2e1723d11d28e8a5ca76 conferido às00:02:08Z (21:02 BRT): 28.373 candidatos, 16.711 textos distintos e 215 novos blobs históricos (20.183 totais), incluindo progresso do coletor principal. Cobertura: 18.834 candidatos com texto, 9.539 sem texto; 68.978 posições com texto, 17.112 selecionadas sem texto e 3.730 faltas de ranking. Zero candidatos liberados para classificação paga.


### Créditos e qualificadores de versão no mesmo parêntese

A normalização Genius agora separa apenas sufixos explícitos conhecidos após " - " dentro de créditos: Song (feat. Guest - Live) pode corresponder a Song (Live) com Guest comprovado, sem corresponder a Song de estúdio. O sufixo completo é preservado (incluindo local/ano), e a busca usa esse título com versão. Termos desconhecidos não são apagados. A verificação anterior já recusava a versão de estúdio nesse caso, mas também não recuperava a versão correta. Trinta e três testes de descoberta/importação/identidade passaram e Ruff passou; regressões cobrem Live, Ao Vivo, 2018 Remaster, Radio Edit, local de show e Remix, mantendo a recusa de artista participante diferente. Entradas sem título/artista retornam falso. A mudança será carregada pela próxima execução, sem reinício do coletor atual.


### Participações ausentes não equivalem a lista vazia

A auditoria local dos últimos100 resultados Genius identificou113 ocorrências de hits correspondentes em respostas de busca em cache; todas tinham featured_artists explicitamente presente como lista. Evidência agregada em data/runtime/genius-credit-field-audit-20261031.json (não são113 respostas únicas nem prova sobre toda a base). O matcher agora recusa campo ausente/nulo/malformado e participantes sem nome. Busca resumida consulta api/songs/{id} antes de aceitar a identidade, inclusive para pedido aparentemente solo; detalhes com convidado não solicitado são recusados antes de baixar letra. Novas provas registram performer_credit_fields_explicit=true. O cliente legado também consulta detalhes para esses resultados resumidos. Cinquenta e sete testes focados passaram e Ruff passou, incluindo detalhe que revela um convidado desconhecido versus participação solicitada correta. Nenhuma promoção científica automática nem chamada paga; os testes HTTP usam transporte simulado.

Replay incremental-next (desde00:01Z): 1.340 IDs recentes, 983 elegíveis examinados, 51 propostas, zero erros/rede. Snapshot6dcb9999232a44c038d8fd56eb461ccaae5a9422c275b14475c47eb75b9fc5ed concluído e conferido: 28.373 candidatos, 16.715 textos distintos atuais, 24 novos blobs históricos, classification_ready=false. A sessão89852/PID372 foi acompanhada até saída0; nenhuma reinicialização por demora. As propostas incluem reparos e evidências não elegíveis, não51 músicas novas validadas.

### Continuidade local e retomada no logon — 31/10/2026, 22:00 BRT

Conferidos PID, criação e comando: 3660 (v12), 2580 (metadados), 9752
(v13 em espera), 24432 (durações em espera) e 24684 (replay em espera).
Nenhum desses processos foi interrompido ou duplicado.

Adicionado `scripts/supervise_quota_recovery.py`, com lock exclusivo,
inventário CIM de comandos/criação a cada 60 segundos, checkpoints e logs em
`data/runtime/quota-supervisor-20261031`. Adota trabalhadores existentes;
retoma os ausentes após perda de processos; preserva pausas/bloqueios nativos;
encadeia metadados, 228 durações, replay local, staging verificado e cobertura.
Após as janelas existentes de letras, inicia janelas de oito horas usando a
mesma aquisição/cache e estados separados. Erros de trabalhadores interrompem
o supervisor com `attention-required.json`, sem retentativas rápidas. Não usa
IA, classificação paga, substituição de posições ou alterações de cotas.

Retomada instalada na pasta Startup do usuário como
`PromiscuidadeMusical - Retomada.lnk`, apontando para
`scripts/start_quota_supervisor.ps1` com janela oculta e Python da `.venv`.
O teste real pelo atalho alcançou o lock do supervisor já ativo (segunda
instância recusada). O Agendador foi testado mas o launcher da `.venv` falhou
nesse contexto com saída 103; a tarefa experimental foi removida. Não alegar
execução antes do logon nem teste de reinício físico do Windows. O supervisor
atual foi recarregado para incluir registro de saída das próximas janelas;
apenas os processos do próprio supervisor foram encerrados nessa recarga.

Quatro testes focados passaram e Ruff passou: adoção de wrapper sem duplicar,
retomada sem processo, pausa terminal do provedor e falha de dependência.
Último inventário de revisão preservado: 18.852 com texto, 9.521 sem texto;
3.730 lacunas de ranking em 25 células. Nada disso certifica letras. Nenhuma
nova auditoria integral ou snapshot foi iniciado nesta passagem.

### Campanha autônoma de 24 horas — 01/11/2026, 20:16 BRT

Solicitação explícita: processamento de fundo por 24 horas sem depender do
chat/créditos de IA. Janela persistida em `campaign.json`: início
2026-11-01T23:16:49.951710Z, fim 2026-11-02T23:16:49.951710Z
(02/11 às 20:16:49 BRT). O supervisor deixa de abrir novas janelas ao terminar
o prazo, drena o trabalho em voo e grava cobertura/auditoria finais. Novas
janelas têm duração limitada pelo restante da campanha, inclusive após reboot.

Tarefa Windows `PromiscuidadeMusical-24h-Recovery`: verificação a cada cinco
minutos por 24 horas e gatilho de logon, instâncias duplicadas ignoradas,
execução oculta e permitida em bateria. Teste real de uma invocação teve saída
0; após recarregar somente o supervisor, o Agendador iniciou o proprietário
real13416/launcher19344 às20:16:51. O coletor real2168, criado às17:32:44,
foi adotado sem interrupção. A tarefa permanece Running enquanto seu supervisor
está ativo; gatilhos repetidos não abrem outro proprietário. Não há heartbeat
Codex nem consumo de IA para monitoramento.

Corrigida a causa de diferenças entre app/Agendador: os executáveis e o cluster
estão no cache físico do pacote Codex. A `.venv/pyvenv.cfg` agora aponta para o
Python físico existente; configuração anterior preservada em
`pyvenv-before-watchdog.cfg`. O launcher usa o LOCALAPPDATA físico registrado
na campanha, remove overrides Python herdados e usa logs por PID, evitando
compartilhamento exclusivo de stdout. O cluster16 existente é retomado pelo
`research_environment.ps1`; não se cria cluster vazio nem se acessa o material
PostgreSQL18 da máquina antiga. Credenciais não foram expostas.

Tentativa de tarefa S4U para executar antes do logon recebeu Acesso negado.
Logo, a retomada suportada é na sessão aberta e no próximo logon. Não prometer
execução com Windows desligado/antes de login. O supervisor mantém um pedido
processual ES_SYSTEM_REQUIRED para impedir suspensão automática por ociosidade,
sem alterar permanentemente o plano de energia.

Integridade: hashes dos arquivos fonte/cotas/seleção ficam congelados na
campanha e são conferidos antes de novas janelas. Todos os86.090 vínculos
atuais em arquivo e staging foram comparados com a candidata nativa no mesmo
país/ano/plataforma/posição do Parquet de origem, sem divergências. A trava é
executada também antes da fila e do staging; não certifica a fonte externa ou
o texto por si só. Rankings provisórios, identidade e completude pendentes
seguem bloqueados; nenhuma promoção científica ou classificação paga.

Falhas transitórias fatais de worker têm retomada limitada a três tentativas,
com intervalo mínimo de cinco minutos. Falhas de integridade entram em
`safety-hold.json` e não são contornadas pelo watchdog. Erros individuais de
rede continuam usando os limites/cooldowns dos provedores. A descoberta de
charts repete somente TimeoutError, no máximo duas rodadas com seis horas
entre rodadas; os registros originais vão para timeout-retry-history.json.
Não repete automaticamente rejeições de identidade/conteúdo nem bloqueios
401/403/429. Retentativa real iniciada como17424/launcher2208 às20:16:52.

Cobertura e auditoria de escopo são atualizadas após cada snapshot bem-sucedido
e ao encerrar a campanha, em vez de repetir snapshots completos por minuto.
38 testes focados passaram e Ruff passou: prazo persistente/fuso/expiração,
alteração de fonte congelada, proteção de caminho, candidata/país/ano/posição,
limites de cota, adoção/duplicação de processos e preservação de timeouts.
O último inventário consolidado mantém21.538 com texto e6.835 sem texto;
3.730 posições anuais permanecem pendentes. Não confundir automação operacional
com conclusão científica ou garantia de letras ainda não validadas.

### Rodada direcionada executada — 03/11/2026, 20:19 BRT

A campanha ampla de24h não foi repetida. Novo runner
`scripts/run_targeted_revision.py`, com proprietário exclusivo, checkpoints
por fase e logs em `data/runtime/targeted-revision-20261103`. O launcher local
foi direcionado pelo campaign.mode=targeted_revision e o watchdog existente
foi atualizado para uma janela de seis horas (até04/11 às02:19 BRT). A fase de
rede é uma única rodada de até duas horas, limitada a500 candidatos já
selecionados nas cotas. Não há novas posições, alteração de cotas ou IA paga.
A campanha anterior foi preservada em campaign-24h-20261101-ended.json.

1. Alternativas de ranking: arquivada a página primária Apple Music
https://music.apple.com/in/playlist/top-100-songs-2018-india/pl.7df4aa48d58c4689bad274bfe7c54cce.
JSON-LD contém99 faixas com URLs/IDs nativos e datePublished=2018-11-29.
Profundidade inferior à cota440, publicação antes do encerramento do ano e
ordem atual sem comprovação das posições históricas impedem uso como ranking
anual definitivo. Observações em alternative-ranking-evidence.json, sempre
DISCOVERY_QUARANTINE; zero posições anuais adicionadas. O ranking anual Circle
para KR/2018 foi localizado, mas a fonte proíbe TDM não autorizado; não foi
iniciada coleta em massa. Totais cumulativos Kworb não foram aceitos como
métrica anual de IL. Decisões em ranking-source-decisions.json.

2. Verificação dos textos: streaming do snapshot PostgreSQL
 ee52f67a92080f2c266b3c600c5fe63bf3ac94154b7e9b6966ac6323a926c9a3.
22.250 candidatas examinadas por hash, regras atuais de qualidade e provas de
atribuição:2.529 com sinais de reparo/quarentena,19.721 sem essas flags, mas
SEM certificação de gravação/completude.112 grupos de texto compartilhado
entre identidades diferentes foram preservados como sinais de conflito, sem
escolha automática. Principais sinais:1.893 sem prova completa de intérpretes
Genius,1.798 com escopo de página não comprovado,1.479 sem prova de origem da
identidade e1.186 com créditos de colaboração não comprovados (há sobreposição).
Relatórios text-evidence-audit.jsonl, text-audit-summary.json,
shared-text-conflicts.json e repair-candidates.jsonl. Zero validações
científicas automáticas e zero liberação para classificação.

3. Recuperação de letras:500 candidatos sem texto priorizados por quantidade
de vínculos e melhor posição, afetando3.954 posições já existentes nas cotas.
Plano preserva os sinais de falha anteriores. Replay offline conferiu os500,
com zero propostas novas, zero erros e zero rede. Aquisição real8576, iniciada
às20:21, confirmou escopo500 e uma rodada. Às20:23 já tinha seis candidatas
com texto pendente de validação; o ganho consolidado só deve ser contado após
o staging. O runner fará staging, cobertura e conferência exata de país/ano/
plataforma/posição/identificador ao concluir, sem intervenção do chat.

Correção de aquisição: um httpx.RequestError na descoberta podia encerrar a
tentativa antes das fontes alternativas. recover_with_fallback agora preserva
o tipo do erro e continua a próxima etapa, com o mesmo HTTP/cache/cooldowns e
as mesmas verificações de identidade e qualidade. Teste simula ReadTimeout
seguido de AZLyrics com identidade exata; não libera classificação.

A primeira chamada do novo auditor omitiu o argumento source exigido pelo
derivador e foi corrigida antes da execução concluída; diagnóstico original
preservado em corrected-initial-audit-call.json. Corrigido também o hash do
plano JSONL no Windows: o hash inicial considerava LF antes da tradução para
CRLF; o coletor já usava o hash real correto. O plano atual confere SHA256
1214cbee5a9218e421d292054b533e80ee9f799aeedc6fdd2f68d75d7c0717a7,
com o valor inicial preservado. Novos planos são gravados como bytes UTF-8.

54 testes focados passaram e Ruff passou, incluindo timeout/fonte alternativa,
recusa de escopo vazio/fora da seleção, preservação de versão/posição e hash
exato dos bytes escritos no Windows. Mantêm-se3.730 lacunas anuais; nenhuma
fonte parcial ou ambígua foi usada para declarar o esquema completo.

### Inicialização silenciosa do Windows — 03/11/2026, 23:19 BRT

Corrigida a janela de mensagens pg_ctl no logon. O atalho Startup e a tarefa
Windows agora usam `wscript.exe` com `start_quota_supervisor.vbs` (host GUI,
filho oculto e retorno de saída preservado). O bootstrap usa
`research_environment.ps1 -Quiet`; detalhes ficam em postgres-bootstrap.log.
O launcher verifica o marcador finished/safety-hold da rodada direcionada
antes de preparar o banco, evitando retomar PostgreSQL para trabalho concluído.

O ambiente ganhou mutex por cluster para serializar status/start concorrentes.
O processo pg_ctl é criado sem console, com código de saída obtido por handle
do próprio processo, leitura assíncrona limitada e prazo de60s no start. Não
se aguarda a vida inteira do servidor descendente. O script PowerShell com
mensagens em português foi gravado como UTF-8 com BOM para Windows PowerShell5.
Não há exclusão manual de postmaster.pid nem alteração de dados/cotas.

Verificações reais: duas chamadas -Quiet simultâneas tiveram código0 e stdout/
stderr vazios; chamada manual exibiu disponível/sessão corretamente; o atalho
real retornou0 e a tarefa agendada também retornou0. PostgreSQL PID8952
permaneceu o mesmo durante as verificações finais. Nos testes iniciais foram
corrigidos bloqueio de pipes herdados e código de saída nulo de Start-Process;
a versão final usa Process.Start/WaitForExit e captura assíncrona. Reinício
físico do computador não foi necessário para testar o caminho de logon.
