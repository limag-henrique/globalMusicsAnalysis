# Correções de calendário e identidade — 31/10/2026

Objetivo preservado: cotas principais por país/ano, 2018–2026, corte 15/10/2026,
letras correspondentes às gravações e versões, sem repetir aquisição desnecessária.
O pesquisador autorizou candidatos provisórios, separados do ranking anual elegível.

## Falha encontrada e corrigida

`annual_ranks` invalidava a célula país/ano inteira quando uma observação tinha
título ou artista ausente, mesmo com ID nativo e streams válidos. Exemplo auditado:
Emirados Árabes Unidos em 2023, 73.000 observações e 365 dias: 85 títulos vazios,
zero IDs/valores de streams inválidos. Isso excluía indevidamente o ranking inteiro.

Agora são estados separados:

- ID ausente, métrica inválida ou conflito de reproduções continuam impedindo a
  seleção daquela fonte/célula.
- Metadados de exibição ausentes são contados em `metadata_missing_observations`;
  não alteram a soma por ID nativo nem a cobertura de calendário.
- Título/artista podem ser recuperados de outras observações do mesmo ID; não se
  tenta identificar a música por uma letra, por similaridade ou pela posição.
- Uma faixa ainda sem identificação conserva a posição e a pendência. A próxima
  música não é promovida para encobrir sua ausência.

Uma verificação independente com dicionários Python reproduziu os mesmos IDs,
ordem e streams do Top 130 AE/2023, a partir dos 73.000 registros originais.

## Novo snapshot materializado

Raiz: `data/derived/annual_revision/audited-calendars-2018-2026-20261031/`.
Importação PostgreSQL imutável:
`4bc1285aaeb0dbab17ca212c319d563e2d0d1cf966608cb980ed95cc99a65bbb`.

- 83.300 vínculos em calendários elegíveis; 27.437 identidades candidatas.
- 504 células anuais e 67 células parciais de 2026 com calendário elegível.
- 41 células ainda sem calendário completo.
- 2.790 vínculos provisórios adicionais.
- União para aquisição: **28.220 candidatos**, 86.090 vínculos país/ano.
- Cotas principais somam 9.980 por ano, até 89.820 vínculos em nove anos.
  Os 3.730 vínculos restantes não foram fabricados.

Todos os snapshots anteriores foram preservados. O banco e os arquivos ainda
distinguem seleção de calendário elegível, seleção provisória e validação de letras.

## Identidade textual

`scripts/audit_lyric_identities.py` encontrou 12 grupos com texto idêntico e
títulos diferentes, afetando 29 vínculos de candidatos. Alguns podem ser versões,
transliterações ou créditos equivalentes, mas outros exigem correção. Todos são
alvos de revisão/recuperação, nunca validações automáticas.

Artefatos em `data/derived/lyrics/quota-20261030/identity-audit/`:
`collisions.jsonl`, `repair-targets.jsonl`, `missing-metadata.jsonl`, `summary.json`.

Havia 94 candidatos sem título/artista suficiente no snapshot ampliado.
`scripts/enrich_rank_metadata.py` recuperou metadados de **63 IDs Spotify exatos**
nos Parquet MGD/Kaggle locais. Um caso tem metadados divergentes e os demais
continuam pendentes. Evidências em `metadata-enrichment.json`; os campos originais
ausentes e a proveniência são preservados. Isso não valida a edição textual.

Títulos publicados constituídos só por símbolos (`+`, `!`, `@`) agora permanecem
distintos; não são tratados como metadados vazios.

## Descoberta corrigida

Genius separa frequentemente a participação musical do campo de título. Exemplo:
um título Spotify com `(feat. Quavo)` pode aparecer como `Intentions`, com Quavo
nos créditos. A regra nova aceita essa diferença somente com evidência explícita
dos participantes. Remix, ao vivo, clean/explicit e tradução não são removidos.
Resultados `top_hit` e `song` são examinados, descartando traduções/artistas distintos.

Teste real recuperou o candidato antes pendente, com título/artista conferidos
nos metadados de busca e página, preservando os contêineres completos. O texto
não é reproduzido neste relatório. Não há declaração fictícia de integralidade
ou de confirmação de gravação por áudio.

O serviço Genius rejeitou `per_page=10` no teste; o contrato implementado usa
`per_page=5`. LRCLIB teve respostas 503/429; os erros de serviço agora recebem
pausa por domínio, além das pausas por bloqueio. Não se contorna acesso negado.

## Continuidade e estado real

A rodada inicial PID 11944 foi confirmada viva e continua executando seu acervo.
A recuperação corrigida foi encadeada por `scripts/run_after_process.py`, que
aguarda o **handle real do processo**, sem reiniciar apenas por um status desatualizado.
Quando ele termina, o wrapper carrega o código atualizado de aquisição:

```powershell
uv run --frozen python -u scripts/autonomous_lyrics.py --hours 8 --method-prefix exact-discovery-v4 --state-root data/runtime/identity-repair-v4-20261031 --base-root data/derived/annual_revision/audited-calendars-2018-2026-20261031
```

Não executar esse comando enquanto outro proprietário mantiver o lock do acervo.
O agendamento serial já foi iniciado e observado em `waiting_for_previous_owner`.
Estado da próxima rodada: `data/runtime/identity-repair-v4-20261031/status.json`.
Log: `bootstrap.log`; erros: `bootstrap-errors.log`.

Na rodada corrigida, contagens são restritas à seleção atual via tabela temporária
`task_scope`. Textos de seleções anteriores permanecem no acervo, mas não inflam
os contadores de progresso do snapshot novo.

47 testes relevantes passaram, incluindo ranking com metadados ausentes,
versões/participações, símbolos, cache, último verso, cotas e contagem por seleção.
Ruff passou. A meta continua em andamento; não foram acionados Gemini, despesas
novas ou validações humanas fictícias.

## Atualização de execução e metadados — 31/10, 08:42 UTC

A rodada v4 efetivamente iniciou às 08:10:59 UTC, PID 9076. O proprietário
anterior foi encerrado em um ponto sem tarefas em voo, com evidência de
transferência preservada em `data/runtime/identity-repair-v4-20261031/handoff-evidence.json`.
O estado operacional atual é `data/runtime/identity-repair-v4-20261031/status.json`.

Foram recuperados metadados ausentes de 92 candidatos Spotify usando IDs
nativos e arquivos locais/páginas públicas. Um candidato YouTube adicional,
SEMPERO (Super Slowed), teve os endpoints das 13 semanas conferidos e o crédito
explícito QMIIR recuperado da descrição do vídeo vinculado. O artista não foi
inferido do nome do canal. Um título Spotify permanece desconhecido; não foi
inventado nem substituído por outra posição.

O coletor `scripts/collect_chart_video_evidence.py` está recapturando 230 páginas
históricas dos cinco pares país/ano selecionados do YouTube, abrangendo 1.017
candidatos. Confere país, data, posição, métrica e identidade textual antes de
registrar o endpoint. Divergências ficam registradas como conflitos. Os links
identificam vídeos representativos de rankings que podem agregar versões;
não certificam sozinhos uma gravação ou uma letra.

A próxima rodada v5 foi encadeada ao handle real do PID 9076, com estado em
`data/runtime/identity-repair-v5-20261031/status.json`. Carregará os metadados
novos e consultas sem separadores de créditos, além de até três artistas
individuais. A aceitação continua exigindo o título/versão e todos os créditos
originais. O lock compartilhado impede dois escritores no acervo.

52 testes relevantes passaram após essa alteração; Ruff passou nos arquivos
alterados. Nenhum desses testes certifica a correção de todas as letras.

## Inventário de revisão

`scripts/export_quota_lyric_review.py` lê um snapshot SQLite em modo somente
leitura e exporta `data/derived/lyrics/quota-20261030/review-inventory/candidates.jsonl`.
Há uma linha por candidato da seleção atual, com todos os vínculos país/ano,
evidência disponível, referência ao texto, conferência SHA-256 e pendências.
As letras não são copiadas nem aprovadas por esse exportador. A leitura não
inclui gravações posteriores do coletor; a data e os totais ficam no summary.

Primeiro inventário, 08:43:33 UTC: 28.220 candidatos, 86.090 vínculos,
14.390 referências a textos com hash íntegro, 38 vínculos com textos iguais
entre títulos diferentes e um artista atualizado ainda não reconciliado
na rodada em execução. Hash íntegro demonstra integridade do arquivo,
não atribuição correta nem transcrição completa.

O exportador será executado novamente após o encerramento real do coletor
de endpoints YouTube PID 22504, por `scripts/run_after_process.py`.
Estado: `data/runtime/review-export-20261031/status.json`.
A rodada v5 também carregará a referência e o hash do mapa nativo concluído,
preservando seu escopo de vídeo representativo, sem adjudicar gravações.

A auditoria de colisões foi atualizada às 08:43:57 UTC: 15 grupos, 38 vínculos
priorizados para recuperação. Resultados anteriores continuam preservados
na tabela de tentativas e nos blobs; igualdade de texto não autoriza fusão
de músicas ou descarte automático de uma versão.

## Conclusão da coleta de endpoints — 08:45:23 UTC

O processo PID 22504 concluiu as 230 páginas: 15.302 linhas verificadas e
533 conflitos de linha preservados. O mapa contém os 1.017 candidatos:
967 com algum vídeo representativo, 941 com todas as aparições de origem
verificadas, 50 sem endpoint confirmado e quatro com múltiplos vídeos.
Esses números não são contagens de gravações validadas.

O exportador encadeado terminou com código 0 às 08:45:31 UTC e incorporou
o mapa no inventário. Snapshot: 14.392 textos com hash íntegro, 675 referências
a fontes em quarentena, 38 vínculos com colisões entre títulos. A próxima
rodada prioriza colisões, metadados a reconciliar e candidatos ainda pendentes,
antes de revisar outros textos já disponíveis. As consultas Genius passarão
a preservar os créditos estruturados e o identificador de música que
sustentaram a correspondência; não apenas um indicador booleano.

## Créditos alterados nas páginas históricas — 08:48 UTC

A investigação de uma página indiana confirmou que os mesmos título, rank e
reproduções agora aparecem com créditos abreviados ou expandidos, por exemplo
Shashaa Tirupati → Shashaa e inclusão de Laxmikant-Pyarelal em outra faixa.
Não foi aplicada equivalência de artistas por aproximação textual.

`scripts/recapture_changed_youtube_credits.py` escolheu 14 páginas para cobrir
as 50 candidatas sem endpoint. Preservou 58 evidências de linhas referentes a
36 candidatas, comparando país/data, título exato, posição e reproduções.
Os arquivos ficam em `youtube-changed-credits` dentro do snapshot auditado,
incluindo `pending-credit-review.jsonl`. Cada vínculo guarda as duas versões
de créditos, ID de vídeo e hash do arquivo de evidência, com identidade de
artista/gravação/letra ainda não validada. O mapa estrito original não foi
alterado. Restam 14 candidatas sem endpoint recuperado nessa investigação.

Inventário reexportado às 08:48:07 UTC, incluindo essas evidências separadas:
14.402 candidatas com textos e hash íntegro. Os processos de aquisição e da
continuação serial v5 permanecem vivos; mudanças no código só entram na
rodada que o carregar após o proprietário atual terminar.

## Recuperação de letras sincronizadas e novas tentativas

O adaptador LRCLIB agora usa `syncedLyrics` quando não há `plainLyrics`, somente
se todas as linhas não vazias possuem timestamp LRC reconhecido. Remove apenas
os timestamps e preserva todas as linhas, inclusive refrões repetidos e a última
linha. Conteúdo não interpretado faz a conversão falhar, em vez de descartar
versos. Respostas brutas continuam no cache; o resultado registra qual
representação foi usada. Título/versão e artista completo ainda devem coincidir.

Foi corrigido também o registro do artista solicitado na evidência LRCLIB,
para que a auditoria compare o crédito completo que realmente foi solicitado.
A próxima rodada consultará novamente os adaptadores alternativos quando
a candidata continuar sem blob, além da descoberta Genius/LRCLIB. Usa o cache
e as pausas por domínio; um resultado positivo anterior permanece preservado
se a nova recuperação falhar. A rodada atual não foi interrompida.

53 testes relevantes passaram, incluindo LRC sem perda de repetições/último
verso e rejeição de linhas não interpretadas. Ruff passou nos arquivos alterados.

## Cache durante pausas do provedor

Foi identificado que `PacedHTTP` devolvia 429 durante a pausa por domínio antes
de tentar a resposta local. Isso fazia uma indisponibilidade remota impedir
também o reaproveitamento de respostas já adquiridas. Na próxima rodada, a
pausa permite replay exclusivamente local quando os bytes têm o hash esperado;
conteúdo ausente ou corrompido continua retornando pausa sem solicitar a rede.
Respostas antigas descobertas nos caches anteriores também podem ser usadas.

O teste de regressão cobre resposta salva, bloqueio subsequente, replay local,
URL nova sem rede e cache corrompido sem rede. Os 15 testes de aquisição e
descoberta passaram; Ruff passou. O processo atual permanece com o código
que carregou ao iniciar; essa correção entra na continuação serial v5.

## Recuperação exclusivamente local — 08:52:34 UTC

`scripts/replay_cached_quota_lyrics.py` terminou o exame de 13.808 candidatas
sem texto no snapshot inicial. Encontrou 17 resultados adicionais: 15 Genius
e dois LRCLIB em texto simples, sem flags de qualidade automática. Todos os
17 continuavam sem texto no banco principal na conferência subsequente.
Não houve requisições de rede nem erros nessa execução. O transporte HTTP
lança erro se houver tentativa de rede; o leitor só reproduz bytes com hash
verificado. Não se usou navegador nem acesso remoto nessa etapa.

Resultados completos, créditos e referências às respostas ficam em
`data/derived/lyrics/quota-20261030/offline-replay/*.json`. O estado terminal está
em `data/runtime/offline-lyrics-replay-20261031/status.json`.
Esse processo leu o SQLite principal em modo somente leitura. A rodada v5
importará os resultados apenas se a candidata continuar sem texto e os
metadados solicitados corresponderem à seleção atual. A tentativa anterior
será preservada na tabela de histórico. Importação usa o lock do proprietário
e o mesmo armazenamento de blobs por hash; não cria um segundo escritor.

Os 17 resultados ainda exigem validação de atribuição/completude. Os 54 testes
relevantes passaram, e Ruff passou nos arquivos alterados.

## Correção das contagens decimais — snapshot posterior, 08:57 UTC

O CSV Zenodo guarda contagens inteiras como strings decimais (`7232900.0`).
A conversão direta para Int64 produzia nulos: na amostra KR/RU de 2021,
10.400 de 10.400 linhas eram rejeitadas, apesar de todas serem inteiras.
`integer_metric` agora remove exclusivamente a parte decimal composta de zeros
antes da conversão, sem float ou arredondamento. Valores fracionários,
não numéricos e fora de Int64 continuam inválidos. O teste inclui inteiro
acima de 2^53 para demonstrar ausência de perda de precisão.

O novo snapshot, sem sobrescrever o anterior, está em
`data/derived/annual_revision/integer-metrics-2018-2026-20261031`.
Run PostgreSQL imutável:
`b55a72074285c68c1be31b7dad79759f23a6f08a291a6be692b34e0e5dbb9474`.
Tem 83.500 vínculos principais, 2.590 provisórios, 86.090 no total e
28.373 candidatas únicas. A célula RU2020 passou a ter calendário completo
YouTube e 200 posições anuais; a seleção Spotify incompleta anterior permanece
nos snapshots históricos. Uma recomputação independente com csv/Decimal/dict
conferiu as 53 semanas, 5.300 itens-período e todas as posições/métricas do
Top200. Evidência: `russia-2020-independent-verification.json`.

Os demais conflitos Zenodo não desapareceram com a conversão. A página oficial
KR de 21/03/2019 foi conferida: o mesmo título, artista e vídeo aparece nas
posições 1 e 7, com métricas diferentes, como no arquivo. A captura está em
`data/raw/historical_backfill/20261030/official-conflict-review/KR-2019-03-21.json`.
Não foi escolhido um valor nem somadas essas linhas para fabricar uma seleção.

O proprietário PID9076 continua com o snapshot anterior e não foi interrompido.
O wrapper v5, ainda em espera e sem trabalhador iniciado, foi substituído pelo
v6, que aguarda o handle real desse proprietário e usará o novo snapshot.
Estado: `data/runtime/identity-repair-v6-20261031/status.json`.
A evidência da substituição está em
`data/runtime/identity-repair-v5-20261031/superseded.json`.
O inventário já foi reexportado para a nova seleção; 200 candidatas novas
ainda não estavam enfileiradas no proprietário antigo, como esperado.

55 testes relevantes passaram. A correção não valida identidades de gravação
ou letras e não aciona classificação paga.

## Arquivo original Kaggle e Israel 2021 — 09:07 UTC

As lacunas diárias MGD foram localizadas: RU2021 tem ausência de 31/08;
IL2021 tem ausências de 08/05, 07/06 e 31/08. As rotas públicas antigas do
Spotify redirecionaram para o overview atual, e os índices consultados do
Internet Archive não forneceram os CSV dessas datas. As respostas de prova
estão em `data/raw/historical_backfill/20261030/missing-day-probes`.

O arquivo normalizado Kaggle local tinha apenas posições até 100. A versão
original 85 de dhruvildave/spotify-charts foi recuperada da fonte pública,
com metadata e lista de arquivos preservadas. ZIP: 991.225.045 bytes;
CSV: 3.483.476.388 bytes, extração com verificação CRC e tamanho esperado.
SHA256 do CSV:
`8238a106f723af9b1d3b857b78ec43f7147d82472b491c63853bcbcc3c23cb1b`.
`scripts/recover_original_kaggle_charts.py` normalizou os dados sem corte
Top100 em `kaggle-dhruvildave-v85/full-top200.parquet`, com 69 códigos de
mercado (incluindo global). Estado terminal:
`data/runtime/kaggle-original-recovery-20261031/status.json`.

`scripts/audit_missing_spotify_days.py` comparou conjuntos diários completos
de IDs e reproduções. Em IL2021, todas as 331 datas comuns coincidiram, com
profundidade 200; os três dias ausentes foram acrescentados sem substituir
observações MGD. O calendário resultante tem 365 dias, zero conflitos e
profundidade mínima 200. A soma independente em dicionários conferiu todas
as 120 posições e métricas selecionadas.

RU2021 não foi reconciliado: 19 dias têm conjuntos diferentes. Uma análise
adicional mostrou que a fonte auxiliar é subconjunto da principal nessas
datas, sem reproduções divergentes nos itens comuns; a diferença está em
1–3 IDs ausentes por dia. Essa evidência ainda não foi usada para promover
o calendário, que permanece provisório sob a regra atual de igualdade total.

Snapshot novo preservado em
`data/derived/annual_revision/reconciled-daily-2018-2026-20261031`;
run PostgreSQL `85ec182ee589e9a6000343edfcc223b94592a02f8e05894efc0b14937a4c458c`.
Seleção: 83.620 vínculos principais, 2.470 provisórios, 28.373 candidatas
únicas. O inventário foi atualizado para esse snapshot.
O wrapper v6 que só aguardava foi substituído pelo v7, mantendo o proprietário
9076 em execução. Próximo estado:
`data/runtime/identity-repair-v7-20261031/status.json`.
Não houve novas chamadas pagas ou aprovação automática de letras.

## Participações não solicitadas — 09:10 UTC

A correspondência Genius por artista principal admitia participações adicionais
quando o título permanecia igual. Agora a lista completa de intérpretes deve
corresponder aos créditos solicitados ou às participações explicitadas no
título. A extração JSON-LD também deixou de aceitar qualquer integrante isolado
de `byArtist`: sem prova externa de créditos, exige a identidade completa;
com prova Genius previamente conferida, permite apenas os artistas nela listados.

A auditoria reavalia os créditos estruturados salvos. Um indicador booleano
antigo sem a lista observada recebe `full_provider_performer_evidence_missing`.
Os textos ficam preservados como candidatos; a próxima rodada os revisita.
O inventário reexportado às 09:10:28 registra 13.413 referências Genius com
essa evidência ainda ausente, sem afirmar que todas estejam incorretas.
As 17 recuperações offline foram reavaliadas pelas novas regras, sem flags
adicionais. A importação serial também aplicará a auditoria vigente antes
de gravar os candidatos no banco principal.

56 testes relevantes passaram, incluindo rejeição de participação extra,
preservação de participações solicitadas e extração integral. Ruff passou.
Essas alterações serão carregadas pelo v7 após o proprietário atual terminar;
o v4 vivo ainda executa sua versão previamente carregada.

## Retomada após reinício do computador — 31/10, 09:39 BRT

Na retomada da conversa, os processos 9076 e 9752 já não existiam. O Windows
registrou boot às 09:36:13 BRT. O wrapper v7 não havia iniciado seu trabalhador:
zero tentativas `exact-discovery-v7` no SQLite. Essa constatação veio da lista
real de processos e do banco, não de inferência por idade do status.

O PostgreSQL foi reiniciado com `scripts/research_environment.ps1` e concluiu
a recuperação WAL. O v7 foi lançado com a seleção reconciliada: PID real 4012,
início 09:38:48 BRT, estado `recovering`. Carregou as correções de cache,
créditos completos, participações e letras sincronizadas, que a execução
anterior ainda não tinha carregado. O corte continua 15/10/2026.

`PRAGMA quick_check` retornou `ok`. Foram importados 13 resultados offline
que ainda estavam sem texto, com histórico de tentativa preservado; os outros
resultados já tinham texto no principal e não foram substituídos.
Evidência de retomada: `data/runtime/identity-repair-v7-20261031/reboot-recovery.json`.
Logs novos: `resume.log` e `resume-errors.log` no mesmo diretório, preservando
os logs anteriores. A auditoria de blobs/inventário foi solicitada novamente.
Não houve liberação de classificação paga nem certificação de todas as letras.

## Escopo dos metadados da página — 09:44 BRT

A auditoria de blobs após o boot terminou às 09:41:28 BRT: 16.418 candidatas
com blob íntegro no snapshot de leitura, sem erros de hash reportados.
O processo de aquisição continuou avançando após esse snapshot.

Foi corrigida uma falha potencial no identificador JSON-LD: a travessia anterior
aceitava MusicRecording dentro de recomendações ou menções, podendo associar
metadados da música solicitada ao corpo principal de outra página. A travessia
agora segue somente raízes, `@graph`, `mainEntity` e `mainEntityOfPage`, sem
percorrer recomendações ou listas de faixas relacionadas. O teste de regressão
contém uma música principal diferente e a música solicitada nas recomendações;
o corpo errado é rejeitado.

Novas extrações registram `page_identity_scope`. Candidatos Genius anteriores
sem esse escopo recebem `page_identity_scope_unverified`, continuam preservados
e entram na recuperação seguinte. Isso não declara que todos estejam errados.
O v8 foi encadeado ao handle real do v7 PID4012 para carregar a correção sem
interromper requisições em andamento. Estado:
`data/runtime/identity-repair-v8-20261031/status.json`.
57 testes relevantes passaram na correção de travessia; os 17 de aquisição e
descoberta passaram novamente após acrescentar a evidência de escopo. Ruff passou.

## Rússia 2021 reconciliada — 09:46 BRT

A regra de conciliação passou a distinguir contradição de omissão na fonte
auxiliar. A principal nunca é truncada ou substituída por um subconjunto:
somente dias inteiros ausentes são acrescentados. Há exigência de pelo menos
uma data com conjuntos integralmente idênticos; toda observação auxiliar em
datas comuns deve existir na principal com a mesma reprodução, e qualquer
ID extra ou reprodução diferente impede a conciliação. Cada dia acrescentado
deve conter 200 IDs e posições exatamente 1–200.

RU2021 cumpriu as condições: 314 dias idênticos, 19 subconjuntos sem contagens
divergentes, nenhum ID auxiliar inesperado. O dia 31/08 tem as 200 posições.
Os 364 dias MGD foram preservados, incluindo as faixas ausentes no auxiliar.
Resultado: 365 dias e 73.000 itens-período, sem conflitos ou contagens inválidas.
A recomputação independente por dicionários conferiu as 200 posições e métricas.
Prova: `russia-2021-independent-verification.json` no snapshot novo.

Auditoria anterior preservada; nova análise em
`data/derived/annual_revision/missing-day-reconciliation-v2-20261031`.
Snapshot atual preparado:
`data/derived/annual_revision/reconciled-russia-2018-2026-20261031`.
Run PostgreSQL `391e785bae075dc1c9c203d5df26b68571e4e47d5a8bbbe757fddcb5274d43fe`.
Seleção: 83.820 vínculos principais, 2.270 provisórios, 28.373 candidatas únicas.
O inventário foi reexportado para esse snapshot às 09:46:05 BRT.

O v7 PID4012 continua ativo. O wrapper v8 ainda sem trabalhador foi substituído
pelo v9, que usará a seleção nova após o encerramento real do v7. Estado:
`data/runtime/identity-repair-v9-20261031/status.json`.
58 testes relevantes passaram, incluindo rejeição de métricas contraditórias,
IDs inesperados e conciliação sem nenhuma data integralmente idêntica.

A visão nova também expôs diferenças de nomes em registros MGD: dois resultados
com créditos Genius de Big Baby Tape/kizaru agora são comparados à grafia
`Big BaTape, kizaru` do histórico. Isso não prova letra errada; exige resolver
o nome pelo mesmo ID nativo, mantendo a evidência anterior. Não foi usada
aproximação textual para aceitar a diferença. A fila conserva os textos e
marca as diferenças de metadados para revisão.

## Nomes conferidos pelo URI nativo Spotify

`scripts/resolve_changed_rank_metadata.py` examinou as 28 candidatas com
diferenças de exibição relevantes. O Spotify público respondeu com o URI
exatamente correspondente em todos os 28 casos, incluindo Dirrt e Andrew Story:
o crédito é Big Baby Tape | kizaru, enquanto o histórico MGD trazia Big BaTape.
Não se aplicou equivalência aproximada. Apenas metadados filtrados, URL pública,
data e hashes foram preservados; sessões e tokens do embed não foram salvos.

As referências estão em `native-display-metadata.json` do snapshot
`reconciled-russia-2018-2026-20261031`; evidências filtradas em
`data/raw/metadata_resolution/20261031/rank-change-*.json`.
`apply_native_display_metadata` verifica o hash do arquivo, status HTTP,
URL oficial e URI nativo antes de corrigir nome/artista na visão de aquisição.
Os campos históricos ficam em `original_display_metadata`; fontes, posições,
contagens e identidades dos rankings imutáveis permanecem preservados.

As correções mudaram 28 candidatas em 66 vínculos. Uma assinatura dos campos
país/ano/plataforma/posição/ID/métrica foi calculada antes e depois, nos 86.090
vínculos, e permaneceu idêntica. Prova: `native-display-verification.json`.
A contagem de alterações foi feita por vínculo contra seus campos originais,
sem confundir diferenças de grafia preexistentes entre países/anos com novas
correções. A reexportação do inventário foi iniciada; o v9 carregará a visão conferida.

59 testes relevantes passaram, incluindo preservação do ranking, rejeição de
prova de outro ID e rejeição de evidência adulterada. Ruff passou.
URI e nome conferidos não certificam a transcrição integral da letra.

## Conferência nativa ampliada e pausa do provedor — 09:59 BRT

`scripts/collect_native_spotify_metadata.py` foi implementado para as 27.156
candidatas Spotify da seleção, independentemente da disponibilidade de letra.
Reaproveitou as 28 provas existentes e recuperou mais 12, totalizando 40.
Após uma resposta de interrupção, parou as consultas. A primeira execução
não reteve o status dessa resposta no checkpoint; não se inferiu se era
limite de acesso ou falha transitória. A versão seguinte registra todas
as tentativas e o status responsável pela pausa em SQLite.

As respostas filtradas ficam em `data/raw/metadata_resolution/20261031/native-metadata.sqlite`.
As evidências positivas são publicadas em lotes imutáveis de até 100 registros,
nomeados pelo SHA256, em `native-proof-batches`. As referências são atualizadas
atomicamente em `native-display-metadata.json`. A leitura da aquisição verifica
o hash do lote e o URI de cada registro, reutilizando o lote em memória.
Isso evita abrir um arquivo por faixa para todos os metadados.

O processo de retomada real PID20764 está vivo e aguarda até 10:11 BRT antes
de consultar novamente. Haverá no máximo três rodadas; 429 exige ao menos
15 minutos de espera, 5xx ao menos um minuto, respeitando Retry-After inteiro
maior. 401/403 encerra as rodadas. Limite atual: dois acessos concorrentes,
inícios espaçados de um segundo. Nenhum token, sessão ou HTML do embed é salvo.
Estado: `data/runtime/native-spotify-metadata-20261031/status.json`.

O coletor de letras PID4012 e seu sucessor serial PID6152 continuam vivos.
O inventário anterior terminou às 09:54:33 BRT com 16.545 blobs íntegros.
60 testes relevantes passaram após acrescentar a leitura de provas em lote,
incluindo rejeição de um registro de outro URI dentro do mesmo lote. Ruff passou.
As 40 provas são conferências de metadados nativos, não aprovações de letras.

## Elegibilidade por cotas, sem reposição abaixo do ranking

Foi acrescentado `lyrics/quota_eligibility.py` para preparar a revisão da
seleção variável. O fluxo histórico Top80 continua separado; sua reposição
por reservas não define a amostra nova. O preparador novo conserva as posições
originais, verifica a cota única por célula e rejeita posições inválidas ou
candidatas nativas duplicadas na mesma célula.

Usa o contrato de adjudicação já existente: identidade e integridade explicitamente
verificadas, documento atual vinculado à gravação e hash, evidência oficial ou
conferência humana por áudio. Se o documento mudar de hash, o vínculo é recusado.
Uma gravação com dois textos diferentes supostamente validados fica em conflito,
sem escolher automaticamente um dos textos. Vínculos do mesmo recording/hash
em países/anos diferentes são preparados uma vez, preservando as associações.

O exportador integra essa conferência como relatório, sem inferir adjudicações
dos resultados do scraping. Não foram fornecidos registros de validação ou
bindings de documentos adjudicados para este inventário; o relatório declara
`validation_records_loaded=0`, zero candidatos preparados e classificação não
liberada. Mesmo entradas demonstrativamente validadas no preparador permanecem
`not_for_paid_submission`, com protocolo, orçamento e piloto pendentes.

Artefato: `data/derived/lyrics/quota-20261030/review-inventory/review-gate-summary.json`.
Executado nos 86.090 vínculos e nas 612 combinações esperadas; 25 células sem
ranking selecionado aparecem com déficit integral, em vez de desaparecer.
Exemplos: BR230 e IN440 conservam todas as suas posições, sem corte Top80.

A execução real detectou e corrigiu uma colisão de chave do marcador de bloqueio
em linhas provisórias; o caso foi incorporado ao teste. 64 testes relevantes
passaram após a correção e a inclusão das células ausentes. Ruff passou.
O inventário de textos terminou às 10:04:17 BRT com 16.754 candidatas com blob
íntegro no snapshot. Isso inclui textos em quarentena ou revisão, não valida
automaticamente suas atribuições e não libera chamadas pagas.

## Censura dos charts e base do ranking anual — 10:14 BRT

Foi acrescentado `ingestion/rank_uncertainty.py`. Um calendário completo de
Top200 diários não observa as reproduções dos dias em que uma faixa ficou
fora do chart. O módulo calcula limites condicionais: o limite inferior é
a soma observada; o superior acrescenta, em cada dia ausente, a menor contagem
publicada. A hipótese explícita é que uma faixa elegível não listada não supera
o último lugar publicado; faixas excluídas por regras do provedor não são
certificadas por essa hipótese.

Antes de calcular, verifica calendário exato, posições diárias contíguas,
IDs únicos, inteiros não negativos e ordem de reproduções. Não produz limites
para calendários ou charts incompletos. Considera ainda músicas que nunca
apareceram no chart; não as trata como reprodução zero.

Execução RU2021: 365 charts com 200 posições. A soma observada e a ordem
coincidem integralmente com a seleção preparada. O limite anual para faixa
nunca observada é 4.849.708. Sob a hipótese, 65 das selecionadas têm presença
no Top200 garantida; nenhuma posição exata pôde ser certificada pelos limites.
Isso é ausência de certificação, não demonstração de ordenação incorreta.
Artefato: `russia-2021-rank-uncertainty.json` no snapshot reconciliado.

As candidatas permanecem na coleta. Os vínculos passam a carregar a métrica,
unidade e `ranking_metric_basis=sum_observed_chart_metrics`. O inventário
declara `full_annual_stream_order_certified=false`; as etapas pendentes incluem
a revisão da base anual/censura, além de identidade, letra e orçamento.
Não foi extrapolada a auditoria RU2021 para os demais países/anos.

66 testes relevantes passaram. A coleta nativa retomou após um erro HTTP504
e chegou a 153 metadados verificados no checkpoint das 10:14 BRT. A retomada
respeitou a pausa e preservou a evidência da falha. Os processos de coleta de
letras e metadados permanecem ativos; não houve chamadas pagas.

## Atualização de nomes entre rodadas — 10:25 BRT

A continuação serial agora verifica a assinatura de `native-display-metadata.json`
no início de cada rodada, depois de drenar os pedidos anteriores. Quando há
novas provas, confere hashes/URIs e atualiza somente os metadados das tarefas
da seleção atual, sob o mesmo lock de escritor. Posições, textos e tentativas
anteriores são preservados. Mudanças de nome recebem histórico e exigem nova
correspondência, mesmo quando a busca anterior terminou sem erro transitório.

Uma correspondência nova pode remover apenas a pendência de nome, após gravar
o resultado textual e conferir sua evidência vigente. Isso não remove pendências
de gravação/completude nem autoriza classificação. Falhas de recuperação mantêm
o texto anterior; a pendência de nome fica ativa. A auditoria LRCLIB agora também
recusa explicitamente título/artista antigos, inclusive em faixas sem participação.
O caminho inicial de busca passa a consultar a auditoria completa antes de
dispensar a descoberta de créditos do provedor.

O teste integrado em SQLite separado conferiu mudança de nome, preservação do
texto/status/vínculos e idempotência de uma segunda atualização. Outros testes
conferem rejeição de prova para outra candidata e impedem que resolver um nome
aprove automaticamente identidade ou letra. 69 testes relevantes passaram;
Ruff passou. As alterações entram no v9; o v7 ativo conserva seu código carregado.

Checkpoint de metadados às 10:24 BRT: 751 URIs resolvidos e dois sem metadados
utilizáveis nessa rodada. O v7 tinha 17.128 candidatas com texto em seus contadores
às 10:25:31 BRT, ainda pendentes de revisão. Os três processos reais de aquisição,
coleta nativa e espera serial foram novamente confirmados vivos.

## Persistência PostgreSQL dos candidatos e textos

Foi implementada a área pendente descrita em
`docs/operations/postgres-lyric-staging-20261031.md`. O primeiro snapshot real
tem 28.373 candidatas, 17.273 referências a texto e 15.461 blobs distintos,
com hashes conferidos e zero registros liberados para classificação. Contagens
e constraints foram consultadas após o commit. Os documentos e classificações
históricos permaneceram com 159.111 e 167.952 registros.

O v7 continuou ativo. Uma atualização está encadeada ao seu handle, e o v9
carregará a chamada automática de staging ao encerrar a aquisição. Direitos,
identidade e completude continuam pendentes na área de importação; nenhum
documento histórico foi sobrescrito ou promovido por equivalência de nome.
72 testes relevantes passaram.

## Segunda recuperação local e continuidade nativa — 11:13 BRT

O replay foi atualizado para usar o snapshot reconciliado, provas nativas
atuais e o parser de entidade principal. A assinatura dos artefatos inclui
candidata/título/artista/regras, preservando os resultados anteriores quando
os nomes mudam. Examinou 10.896 candidatas e recuperou 20 textos (16 Genius,
quatro LRCLIB), sem requisições de rede, erros ou flags automáticas novas.
O PostgreSQL incorporou 17 deles que ainda preenchiam lacunas no momento da
leitura; as outras candidatas já tinham sido atendidas pelo coletor principal.
Detalhes no documento de staging e no novo manifesto PostgreSQL.

O coletor nativo anterior encerrou após três pausas, embora houvesse milhares
de respostas úteis entre erros HTTP504 isolados. O processo foi confirmado
terminal antes da retomada. A política agora limita a janela a oito horas,
conta falhas consecutivas sem progresso separadamente e continua após 5xx
isolados com pelo menos um minuto de pausa. Três pausas 429 encerram as
tentativas, com espera mínima de 15 minutos; 401/403 encerra imediatamente.
Uma resposta de negação não pode ser substituída por um 5xx concorrente na
decisão de retomada. Um ID com três 5xx é mantido como indisponível para revisão,
sem inventar metadados ou impedir a tentativa dos demais IDs.

O novo PID6460 foi observado vivo em coleta/espera conforme o checkpoint;
os PIDs4012, 6152 e 21048 continuaram vivos. 77 testes relevantes passaram,
incluindo continuidade após falhas isoladas com progresso, parada por falhas
consecutivas, recusa de acesso e espera por limite de requisições. Ruff passou.

## Investigação de lacunas históricas e passagem para v10 — 11:58 BRT

A versão v9 encerrou às 11:54:16 BRT pela mesma falha de compartilhamento de
`status.json` que já tinha sido corrigida no código em disco. O wrapper real
assumiu automaticamente: v10 PID4240, iniciado às 11:54:17 BRT e observado vivo.
Essa versão carregou a publicação de status com retentativas, a nova identidade
Genius e a prioridade por posição. O checkpoint confirmou pausas das fontes
sem consumir milhares de reservas durante o bloqueio. Os resultados já salvos
foram preservados e os replays offline incorporados na inicialização.

Na investigação de Índia/2018, o arquivo YouTube 2018 do Zenodo não contém
o país. A navegação pública da semana 2018-12-27 retornou HTTP200, mas nenhum
ranking. Um controle no mesmo navegador para Índia/2026-10-15 mostrou país,
período e 100 linhas corretos; a repetição de 2018 continuou vazia. Evidências
em `data/runtime/historical-india-probe-20261031/{probe,control-probe}.json`.
Isso comprova o comportamento dessas consultas, sem provar inexistência de
todas as semanas de 2018 em outras fontes. Não houve substituição por ranking
global ou recente.

Também foram inspecionadas lacunas coreanas e russas. O arquivo de 2018 tem
35 semanas por país, com conflitos de chave/semana: para KR, por exemplo,
2018-07-26 apresenta o vídeo representativo `Fm5iP0S1z9w` nas posições 3 e 4,
com 2.887.274 e 2.680.195 views. Esses registros não podem ser somados ou
deduplicados arbitrariamente. Os conflitos permanecem excluídos da seleção;
os pacotes brutos originais continuam preservados para reconciliação.


### Evidência primária de disponibilidade das fontes na Índia

Os anúncios oficiais registram lançamento local do Spotify em 26/02/2019 (https://newsroom.spotify.com/2019-02-26/spotify-launches-in-india/) e do YouTube Charts em 16/09/2019 (https://blog.google/intl/en-in/products/platforms/youtube-charts-launch-in-india/). Os dois documentos foram arquivados com SHA-256 em data/raw/ranking-source-availability/20261031/manifest.json. Isso orienta a busca de IN/2018 para fontes históricas alternativas, sem provar inexistência de todo conjunto retrospectivo. A cota 440 permanece pendente e não foi alterada. Listas atuais de visualizações globais acumuladas para músicas lançadas em 2018 não medem consumo dentro da Índia durante o ano e não são substitutas válidas. Nenhum ranking novo recuperado nesta investigação.


### Auditoria semanal completa de KR/RU em 2018

CSV YouTube 2018 conferido contra sidecar SHA-256. Inventário por semana em data/runtime/historical-2018-weekly-identity-audit-20261031.json, com quantidade de linhas, posições contíguas, chaves repetidas e valores/nomes dos registros envolvidos. KR tem 35 semanas, 25 sem chaves repetidas e 10 com repetições; RU tem 35, 20 sem repetições e 15 com repetições. Ausência de chave repetida não certifica correção/completude do chart. No pacote bruto KR, o vídeo Fm5iP0S1z9w corresponde ao índice 271, Dance The Night Away/TWICE; portanto o caso duplicado não foi criado apenas pela normalização CSV. Nenhuma mudança de ranking realizada: não houve soma arbitrária, deduplicação de métricas nem descarte silencioso de semanas para alegar ranking anual. A investigação agora pode concentrar verificação independente nas semanas explicitamente identificadas.


### Conferência oficial KR/2018-07-26

A navegação Chromium pública para https://charts.youtube.com/charts/TopSongs/kr/weekly/20180726 retornou HTTP200, país South Korea e período Jul 20–26, 2018, com 100 posições. Captura em data/runtime/historical-korea-probe-20261031/probe.json, SHA-256 5458a34df671ed84b2b2f5b27540013465fee1ced5e33721531ee1b269df01da. As posições 3 e 4 publicadas são ambas Dance The Night Away/TWICE, com 2.887.274 e 2.680.195 views. A comparação integral com o CSV confirmou 100/100 métricas e 100/100 títulos, 91/100 créditos de artista normalizados. Portanto o caso de repetição existe na apresentação oficial, não apenas no pacote/normalizador. Inspeção limitada aos metadados públicos das entradas mostrou o mesmo ID de artista /g/11btzyw8k4 e não resolveu uma identidade independente da gravação. Não usar o ID do artista como ID da música nem somar as duas entradas. Metadados públicos capturados em entry-identifiers.json e public-song-entity-identifiers.json; comparação em official-comparison.json. Nenhuma alteração na seleção anual ou nas cotas. A consulta Kworb atual (https://kworb.net/youtube/insights/kr.html) mostrava semana de 2026 e não foi aceita como evidência de 2018.


### Candidato sem nome SPOTIFY:2me5SocGcxPzFwPe03my19

VN/2018, posição provisória 133/cota180, permanece sem título/artista. A consulta à base diária Kaggle normalizada encontrou 35 ocorrências do ID, todas com nomes vazios. Busca web pelo ID exato não retornou resultados. Uma única consulta MusicBrainz ws/2/url por resource exato open.spotify.com/track/2me5SocGcxPzFwPe03my19, incluindo recording-rels, retornou HTTP404; evidência em data/runtime/missing-native-identity-20261031/musicbrainz-probe.json e resolution-audit.json. Isso descreve as consultas realizadas, sem provar ausência em toda fonte possível. As tentativas oficiais Spotify anteriores também não trouxeram nomes; não foram repetidas. Nenhum nome foi inferido de posição, artista popular ou semelhança. Nenhuma letra/posição foi alterada.

### Descoberta histórica dirigida e recuperação após reinício — 01/11/2026

O Windows reiniciou às 09:21 BRT. A verificação das 09:23 encontrou o supervisor,
coletores e PostgreSQL ausentes; o atalho Startup havia registrado falha 103
do launcher da `.venv`. A retomada anterior, portanto, não funcionou nesse
reinício. `start_quota_supervisor.ps1` agora prepara o ambiente com
`research_environment.ps1`, inicia somente o cluster PostgreSQL 16 de destino
existente (55433, sem criar banco) e invoca o Python da `.venv` diretamente,
sem a composição intermediária cmd/Start-Process. O atalho real foi executado
com sucesso nesta sessão: supervisor 21176 e coletor real 19196, janela
supervised-lyrics-20261031/cycle-0001. Isso verifica o atalho, não um segundo
reinício físico. O supervisor foi depois recarregado para adotar a coleta de
rankings; nenhum coletor de letras ou rankings foi interrompido na recarga.

Novo `discover_quota_chart_gaps.py`: lê somente as 25 células com lacunas,
consulta os charts semanais oficiais YouTube de 2018–2026, até 15/10/2026,
confere país/período renderizados, posição publicada e visualizações exatas.
Uma sessão Chromium, cache/checkpoint por semana, intervalo de três segundos,
janela de oito horas, lock e interrupção por 401/403/429. Duas consultas
consecutivas sem evidência suficiente suspendem aquela célula; não provam
inexistência do ranking. O supervisor retoma execuções interrompidas, mas
mantém erros explícitos para atenção, sem loop de acesso ao provedor.

Importação aditiva na tabela `quota_chart_discovery_snapshots`, separada dos
rankings definitivos e da seleção congelada. Capturas imutáveis por SHA-256
em `data/runtime/chart-gap-discovery-20261101/captures`; checkpoints e logs no
mesmo diretório. Conferência SQL inicial: IL/2024, 24 semanas e 2.400
observações importadas. São posições semanais, não 2.400 músicas únicas nem
novas posições anuais validadas. A coleta permanece em execução.

Relatórios `annual-discovery-PAIS-ANO.json` exigem todas as semanas para emitir
candidatos provisórios até a cota existente. Repetição de título/artista na
mesma semana bloqueia a agregação, sem somar linhas conflitantes. Totais por
strings exatas permanecem em DISCOVERY_QUARANTINE, com bloqueio por identidade
nativa e revisão do protocolo anual. Nenhuma promoção automática ao ranking,
nenhuma alteração das cotas e nenhuma classificação paga.

Doze testes focados passaram e Ruff passou: janela aprovada, país/período,
corte de outubro, preservação de duplicatas, bloqueio de história incompleta,
limite da cota e rejeição de evidência alterada, além dos testes do supervisor.
Último inventário pré-reinício: 19.144 candidatos com texto, 9.229 sem texto,
3.730 lacunas anuais em 25 células; texto não certifica atribuição/completude.

### Correção do limite de análise e da comunicação das contagens — 01/11/2026

A cota de Israel continua sendo **120 músicas por ano**. As 3.700 informadas
anteriormente eram ocorrências semanais coletadas como referência, com repetição
da mesma música ao longo das semanas. Não eram 3.700 músicas selecionadas para
análise. A comunicação dessa distinção foi insuficiente; não houve ampliação
da cota nem inclusão da tabela semanal na análise.

`audit_quota_analysis_scope.py` conferiu tanto `combined.jsonl` como os vínculos
do snapshot PostgreSQL mais recente: 86.090 vínculos em cada lado, zero posições
excedentes, zero ocorrências semanais usadas para análise e zero candidatos
liberados para classificação. Israel tem 120 posições em cada ano selecionado;
2023 e 2024 permanecem vazios enquanto o ranking anual não for reconciliado.
Evidência: `data/runtime/quota-analysis-boundary-20261101.json`, com hashes da
seleção e da tabela de cotas. Não foram apagadas evidências históricas.

Nova trava `ingestion/quota_boundary.py` aplicada antes da criação da fila e do
staging, e na preparação/importação de novos snapshots: rejeita posição acima
de N, duplicação, cota diferente da tabela, ano fora de 2018–2026 e entrada de
DISCOVERY_QUARANTINE como vínculo anual. Corrigidos também os padrões antigos
2017 nos pontos de preparação/seleção para 2018; os dados históricos permanecem
preservados. Relatórios de descoberta agora explicitam limite anual, zero
vínculos adicionados e ocorrências semanais de referência. A tabela de cotas
mantém SHA256 fcf64432b5cce91a666424cac2a54766d6645b81a4f9f859f17b6b085dc50f5a.

28 testes focados passaram; Ruff passou. O coletor real de letras PID19196 e
o coletor real de referências de charts PID9736 continuaram ativos, sem
interrupção ou duplicação. As travas novas serão carregadas nas próximas
execuções; o staging carregará o código atualizado quando for chamado.

A investigação adicional de IL/2024-12-19 encontrou o mesmo vídeo representativo
bWz97rgzxLE nas posições publicadas 13 e 51, com os mesmos créditos e título.
Prova pública do componente renderizado em
`chart-gap-discovery-20261101/identity-probe-IL-20241219.json`. Isso impede tratar
a repetição como duas gravações distintas ou somá-la arbitrariamente. Nenhuma
posição foi escolhida/excluída para fabricar o ranking anual. Seguem pendentes
3.730 posições de ranking e a validação de identidade/completude das letras.
