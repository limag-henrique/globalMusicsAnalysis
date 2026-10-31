# Importação pendente de letras no PostgreSQL

O primeiro snapshot foi importado em 31/10/2026, 10:34 BRT, no banco local
configurado pelo projeto. Run:
`a732463c0180192742e66b416401f128c8993ae52f7862ecd98bd5c55e40bba5`.

- 28.373 candidatas e seus vínculos país/ano.
- 17.273 candidatas com texto no snapshot lido do SQLite.
- 15.461 textos distintos, preservados integralmente por SHA256.
- Zero candidatas liberadas para classificação.

As tabelas são `quota_lyric_staging_runs`, `quota_lyric_staging_candidates` e
`quota_lyric_staging_blobs`. Cada snapshot é imutável e identificado por conteúdo.
Uma candidata tem uma referência ao blob, permitindo compartilhar bytes entre
IDs sem decidir que representam a mesma gravação. As fontes, respostas de
aquisição, flags e associações territoriais permanecem em JSON. Colisões de
texto entre títulos são marcadas para revisão.

Constraints conferidas no PostgreSQL mantêm `classification_ready`,
`identity_validated` e `completeness_validated` falsos e `rights_status=UNVERIFIED`.
Os resultados pendentes não são inseridos em `lyric_documents` nem em tabelas
de classificação. A conferência posterior confirmou os 159.111 documentos e
167.952 classificações históricas preservados.

O comando reproduzível é:

```powershell
.venv\Scripts\python.exe scripts/stage_quota_lyrics.py --base-root data/derived/annual_revision/reconciled-russia-2018-2026-20261031
```

O importador verifica os hashes dos arquivos imutáveis da seleção, reconstrói
os provisórios e aplica as provas nativas disponíveis em um snapshot de leitura.
Lê o SQLite em modo somente leitura, confere o hash dos blobs referenciados e
grava a transação PostgreSQL atomicamente. Corpo alterado sob hash existente
é recusado. Repetir a mesma entrada é idempotente; entradas posteriores preservam
o histórico e reaproveitam os blobs já armazenados.

Estado da importação: `data/runtime/postgres-lyric-staging-20261031/status.json`.
Uma correção no escritor do status final exigiu retomar a primeira verificação
antes de iniciar a transação; a evidência foi preservada em
`reporting-fix-handoff.json`. O teste correspondente cobre o retorno do repositório.

Um wrapper real aguarda o PID4012 e importará uma atualização após o v7:
`data/runtime/postgres-stage-after-v7-20261031/status.json`. A próxima versão
do trabalhador também chama o importador ao concluir a aquisição, antes de
liberar seu lock para a continuação. Falha de staging tem status distinto.

72 testes relevantes passaram, incluindo deduplicação, idempotência, preservação
de snapshots anteriores, recusa de blob alterado, atomicidade e a constraint
que impede promover pendentes diretamente. A coleta de letras e metadados
continuou ativa durante a importação. O snapshot não implica atribuição ou
transcrição correta de todas as letras.

## Atualização com recuperação local

Snapshot de 11:00:05 BRT:
`92649634bc84fcff6f28e652bed9889e92ddb093ce17efd1e55c4f6d01d4322d`.
Tem 28.373 candidatas, 17.561 com texto e 15.694 blobs distintos nesta versão.
Foram incorporadas 17 recuperações locais ainda ausentes no snapshot SQLite;
o manifesto registra `offline_cache_candidates=17` e zero conflitos entre
essas alternativas. As demais recuperações já tinham texto quando a leitura
foi feita. Nenhum texto existente foi substituído pelo overlay local.

O importador só aceita o replay para a mesma candidata, título e artista atuais,
com fonte suportada, texto não gerado por IA e auditoria de metadados sem flags.
Textos alternativos diferentes deixam a candidata em conflito, sem escolha
arbitrária. A importação local pode avançar sem escrever no SQLite que o
coletor principal mantém sob seu próprio lock.

As execuções de staging também compartilham um lock de processo antes da
verificação dos arquivos e a trava transacional PostgreSQL ao persistir. Isso
evita que duas importações disputem o arquivo de status. Os 15.825 blobs totais
do banco incluem os corpos preservados do snapshot anterior; cada SHA256 tem
uma única cópia física na área pendente. Todas as flags de liberação seguem falsas.

## Consulta de revisão

A página Streamlit `Importação por cotas` consulta os snapshots pendentes
diretamente no PostgreSQL, separada das análises do corpus histórico.
Para iniciar localmente:

```powershell
.venv\Scripts\python.exe -m streamlit run src/chart_observatory/ui/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

Abra `http://127.0.0.1:8501/quota_import`. A consulta permite escolher snapshot,
país, ano, disponibilidade de texto e buscar título, artista ou ID. País e ano
precisam corresponder à mesma associação. Com ambos preenchidos, a paginação
segue a posição observada. As linhas identificam seleções provisórias; as
evidências detalhadas conservam todas as associações da candidata.

O detalhe confere SHA256 antes de mostrar o corpo completo, sem truncar a letra,
e oferece os links de fonte disponíveis. A interface não promove letras nem
inicia classificações. O hash certifica integridade de armazenamento, sem
certificar atribuição ou completude da transcrição.

A API também fornece somente GET em `/quota-staging/snapshots`,
`/quota-staging/candidates` e `/quota-staging/candidates/{candidate_id}`.
Listagens paginadas não transportam o corpo das letras; o detalhe é solicitado
separadamente e aceita `run_id` para manter o snapshot escolhido.

A página foi executada contra o PostgreSQL real com `Streamlit AppTest`, sem
exceções. Os testes cobrem o vínculo conjunto país/ano, ordem por posição,
paginação, integridade do texto, ausência de escrita e limites da API.

## Recuperação adicional por identidade da página

Em 31/10 às 11:44:39 BRT o replay local concluiu 10.541 lacunas examinadas,
89 textos recuperados (87 Genius e dois LRCLIB), zero erros e zero requisições
de rede. A auditoria individual dos 89 resultados não encontrou flags de
metadados/qualidade; isso ainda não certifica gravação ou transcrição.

O staging posterior terminou às 11:45:18 BRT, com retorno zero do processo:
`6df9a819544cd3ea2cfe5e7c60f99ee646f45e883520c5b197a81d4e8d6d299e`.
São 28.373 candidatas, 17.931 com texto, 16.064 textos distintos neste snapshot
e 89 preenchimentos provenientes do cache offline. Os demais avanços em relação
ao snapshot anterior vieram da coleta principal durante o intervalo.
Foram acrescentados 110 blobs ao histórico; flags de liberação continuam falsas.
O fluxo não modifica os documentos e classificações do corpus histórico.

Às 11:49:14 BRT, o staging seguinte terminou sem erro:
`83eb2209492119b3c8080fd9abf66eb0cd99823642d9706f255e925e293e5157`.
São 17.951 candidatas com texto, 16.078 textos distintos neste snapshot e
94 preenchimentos do replay offline. A correção da string JavaScript recuperou
mais cinco letras Genius sem flags na auditoria; o restante do avanço veio
da aquisição principal. Nenhum desses números certifica a transcrição.

## Cobertura de posições por país/ano

`python scripts/report_quota_staging_coverage.py` exporta a cobertura de um
snapshot PostgreSQL fixado em
`data/derived/lyrics/quota-20261030/review-inventory/staging-coverage.json`.
O relatório separa posições sem ranking de posições selecionadas sem letra e
preserva a indicação provisória. Detecta identidades distintas na mesma posição
e recusa associações fora da cota, do país ou do período configurado.

No snapshot `83eb2209...`, há 89.820 posições esperadas, 86.090 selecionadas
(2.270 provisórias), 66.300 com texto e 19.790 selecionadas sem texto.
Faltam 3.730 posições de ranking em 25 células país/ano sem seleção. Não foram
encontrados conflitos de identidade na mesma posição. São contagens de posições;
uma música compartilhada entre países/anos aparece em mais de uma posição.
Texto disponível não significa transcrição validada.

A prioridade da próxima aquisição preserva primeiro reparos suspeitos e mudanças
de metadados; dentro do grupo restante, coloca menores posições antes das maiores
e desempata pela quantidade de células atendidas. Não altera cotas, músicas
selecionadas ou posições. A versão v9 ativa mantém seu código carregado; a
continuação v10 usará essa prioridade ao iniciar.

## Snapshot após recuperação da máquina — 16:42 BRT

O PostgreSQL recuperou o WAL após a reinicialização de 31/10 e a fila SQLite
passou no quick-check. O novo snapshot foi confirmado no banco às 16:42:48:
`3191f32816e81c949312bc4b99bf88fcf4948f99f08438d866c1bb1a27e96309`.
São 28.373 candidatas, 17.985 com texto e 16.098 textos distintos nesta versão.
Houve um preenchimento adicional por replay sem rede; os replays anteriores
já estavam incorporados à fila principal. Foram acrescentados 60 hashes ao
histórico. A consulta posterior confirmou o manifesto persistido e zero
candidatas liberadas para classificação paga.

A interface em `http://127.0.0.1:8501/quota_import` foi reaberta e o endpoint
de saúde retornou HTTP200. O coletor de letras v11 e o coletor de metadados
continuaram vivos durante a gravação do snapshot. Evidência da retomada em
`data/runtime/identity-repair-v11-20261031/reboot-recovery.json`.

## Alternativas de cache para textos sinalizados

O replay aceita `--include-flagged` para examinar também candidatas com texto
cuja auditoria indique fonte em quarentena ou flags de qualidade/atribuição.
Cada proposta desse tipo registra `replay_kind=flagged_repair` e
`replaces_text_sha256`, além da identidade e dos nomes atuais. Não escreve
na fila SQLite que o coletor principal mantém sob lock.

O staging só admite uma alternativa se o resultado anterior ainda tiver o
mesmo hash e continuar sinalizado; a proposta precisa passar pela mesma
verificação estrita de candidata, título, artista, fonte suportada, ausência
de geração por IA e auditoria sem flags usada para preencher lacunas.
Resultados atuais sem flags são protegidos. Propostas com textos diferentes
para a mesma candidata produzem conflito e conservam o resultado anterior.

Antes de selecionar uma alternativa, o importador confere também o arquivo
anterior contra seu hash. A nova linha guarda `replaced_unverified_result`
com a proveniência anterior; os arquivos, SQLite e snapshots históricos não
são alterados. A interface identifica a alternativa e informa fonte/hash
anteriores. As flags de validação e classificação permanecem falsas.

O replay está em `data/runtime/offline-flagged-repair-20261031` e o wrapper de
importação em `data/runtime/postgres-stage-after-flagged-repair-20261031`.
14 testes passaram para descoberta e staging, incluindo recusa de proposta
obsoleta, outra gravação/versão, resultado atual sem flags e texto gerado por IA.

O replay terminou às 16:51:02 BRT: 26.875 examinadas, 2.982 alternativas,
zero erros/requisições de rede. Destas, 2.981 eram propostas de reparo:
240 com corpo diferente e 2.741 com o mesmo corpo e nova evidência de origem.

O snapshot `845da73dd80d371a29f12a9f164a36a99dd2f8bd1f337a948a8a9c46c1e45979`
foi confirmado às 16:52:40 BRT. Tem 17.988 candidatas com texto, 15.987 textos
distintos atuais, 2.975 reparos selecionados e zero conflitos de alternativas.
As 240 mudanças de corpo foram selecionadas; os demais 2.735 reparos melhoram
a evidência sem mudar o texto. A verificação posterior encontrou os 2.975 hashes
anteriores preservados no histórico de blobs, além da proveniência anterior
em cada linha reparada. Algumas propostas ficaram inelegíveis porque a coleta
principal ou os metadados avançaram entre os snapshots de leitura.

A verificação desses resultados lê o JSON integral em Python, preservando
caracteres de controle existentes em metadados legados. Extrações SQL de texto
de certos resultados anteriores podem falhar em `\u0000`; não se altera a
proveniência histórica para produzir uma contagem. Evidência consolidada em
`data/runtime/offline-flagged-repair-20261031/staging-verification.json`.
Todos os resultados continuam pendentes de atribuição/transcrição e sem liberação paga.

## Fontes HTML adicionais no replay

A recuperação offline também consulta as respostas de AZLyrics e Musixmatch já
salvas, quando a descoberta Genius/LRCLIB falha ou produz texto sinalizado. O
transporte continua proibindo requisições de rede. A tentativa de HTML pode
ser limitada a essas fontes, sem parar antes em uma alternativa Genius sem prova.

Os resultados HTML agora registram título/artista observados e o escopo exato
de identidade da página. A auditoria exige nomes atuais e escopo adequado:
`exact_page_title` para AZLyrics e `main_entity_only` para Musixmatch. Resultados
antigos sem essa evidência deixam de parecer suficientes após alteração dos
metadados. Artistas com vírgula no próprio nome só passam quando a página
evidencia o nome inteiro; não se presume colaboração pelo caractere isolado.

32 testes passaram para aquisição, descoberta e staging, cobrindo mudança de
versão/artista, escopo ausente, nome artístico com vírgula e último verso.
O replay está em `data/runtime/offline-html-cache-replay-20261031`; sua importação
aguarda o processo real em `data/runtime/postgres-stage-after-html-cache-20261031`.

O replay terminou às 17:00:40 BRT: 26.877 examinadas, 3.303 alternativas,
2.945 propostas anteriores reaproveitadas, zero erros e zero rede. As novas
alternativas vieram de consultas estruturadas LRCLIB já preservadas (3.267),
Genius (34) e AZLyrics (duas). Havia 382 propostas para lacunas e 2.921 reparos.

O snapshot `7e23267969c45af3e1654c48ac2a31b82d2883645fdcdc052ce96d5d9fdf29f3`
foi confirmado às 17:01:10 BRT: 18.372 candidatas com texto, 16.317 textos
distintos atuais, 5.857 reparos selecionados e 384 preenchimentos de lacunas
provenientes dos replays acumulados. Nos reparos, 2.959 corpos diferem do
candidato anterior; todos os 5.857 hashes anteriores foram encontrados no
histórico de blobs. O retorno do importador foi zero e a coleta principal
continuou ativa. A evidência está em
`data/runtime/offline-html-cache-replay-20261031/staging-verification.json`.

Uma candidata permaneceu em conflito: `SPOTIFY:28fP6qcMGPfYOjrx8AOWFn`,
RR 9.1, Koba LaD e Niska. Há alternativas LRCLIB/Genius com 3.415/4.136
caracteres e 646/735 palavras; não são equivalentes por espaços. Nenhuma foi
escolhida arbitrariamente. A candidata permanece sinalizada e as alternativas
completas continuam nos arquivos de replay, com suas fontes e evidências.
Essas contagens não certificam a gravação ou a transcrição de nenhuma candidata.

## Passagem com verificação adicional de papéis

O replay `offline-credit-role-replay-20261031` terminou às 17:28:41 BRT:
20.646 examinadas, 61 alternativas, seis propostas anteriores reaproveitadas,
zero erros e zero rede. O snapshot confirmado às 17:29:10 BRT é
`c1c34fe7a131e987d2365d5cc263422ac2b84cf4183fb731073034f73b4e7625`.
São 18.390 candidatas com texto e 16.327 textos distintos atuais. O overlay
selecionou 50 reparos e 11 preenchimentos; o total de candidatas com histórico
de reparo é 5.888. Permanece um conflito entre alternativas.

A verificação encontrou zero linhas usando `credit_binding_provider=GENIUS`:
os ganhos desta passagem vieram das consultas e dos metadados atualizados que
já estavam no cache. O novo caminho de papéis permaneceu sem candidato elegível
nessa passagem. As verificações de intérpretes completos e texto único foram
mantidas. Evidência em
`data/runtime/offline-credit-role-replay-20261031/staging-verification.json`.
O coletor principal e o coletor nativo continuaram ativos durante a importação.

## Revisão de alternativas conflitantes

O detalhe da importação passa a mostrar as letras completas das alternativas
conflitantes, mantendo a candidata anterior e a sinalização de revisão. O staging
registra hash do corpo, fonte, candidata e hash do arquivo de evidência de cada
alternativa elegível, sem selecionar uma delas.

O leitor usa somente arquivos com nome SHA256 no diretório configurado de
replays locais. Confere o hash do arquivo, a identidade/metadados atuais do
snapshot e o hash do texto antes de devolvê-lo. Prefixos de caminho de outra
máquina não autorizam leitura fora desse diretório. Arquivo alterado, ausente
ou pertencente a outra candidata produz erro de evidência e não mostra texto.
API e interface continuam somente leitura; não há promoção para classificação.

10 testes passaram para detalhe, integridade, rejeição de outra candidata,
isolamento do diretório, staging e API. A inspeção do conflito RR 9.1 encontrou
diferenças de palavras mesmo após retirar rótulos conhecidos de seções; ele
permanece em revisão. A nova importação de evidências está registrada em
`data/runtime/postgres-conflict-review-20261031`.

O snapshot `902a0d1f5b6768088643a62f59fc088b38f2f51a4203369f7b9c253cb9bccf22`
foi confirmado às 17:39:11 BRT, com 18.391 candidatas com texto. No caso RR 9.1,
o leitor recuperou as duas alternativas completas (LRCLIB: 3.415 caracteres;
Genius: 4.136), ambas com hashes de evidência e texto conferidos. A execução real
do Streamlit AppTest abriu os dois painéis sem exceções e exibiu três blocos
de texto: candidato anterior e duas alternativas. A liberação permaneceu falsa.
