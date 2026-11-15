# Correção e verificação da aquisição — 7 de novembro de 2026

## Alterações

- O fallback mantém os erros e a evidência HTTP de cada etapa, sem duplicar os erros anteriores nem perder a origem da recuperação. Uma alternativa com conflito de identidade não é promovida a texto principal.
- Respostas do LRCLIB são comparadas pela normalização versionada já existente: Unicode, espaços e quebras de linha. Ordem, pontuação, seções e repetições permanecem significativas. O texto original escolhido é preservado.
- A recuperação offline e as próximas coletas também consultam os caches das campanhas recentes. As pausas compartilhadas por provedor permanecem vigentes.
- `verify_lyric_source_chains.py` verifica hashes do texto e da resposta web preservada, reextrai o texto do registro/contêiner correspondente e compara os resultados. Não faz requisições nem modifica o banco de produção. Checkpoints permitem retomada.

Correspondência com a resposta de uma fonte não comprova transcrição integral da gravação. Identidade, completude e autorização para classificação continuam falsas, inclusive quando a cadeia de origem corresponde.

## Execução e limites

A coleta existente em `data/runtime/import-all-lyrics-20261107` foi preservada. Seu processo já carregou a versão anterior do código; as correções novas não são retroativas à memória desse processo.

Uma continuação com o código corrigido está em `data/runtime/import-all-lyrics-repair-20261107/acquisition/status.json`. Ela aguarda o processo supervisor 3632 terminar, depois adquire o mesmo lock exclusivo da aquisição. Recupera ausências e casos sinalizados em toda a seleção congelada, preserva o histórico e faz staging ao terminar. Tem limite de seis horas após a espera, limitado também pelo manifesto local. O limite absoluto é 8 de novembro às 04:52 BRT. Não usa inferência paga.

A auditoria integral de origem está em `data/runtime/web-integrity-20261107/full/status.json` e seu inventário individual privado em `checkpoint.sqlite`. Usa uma fotografia imutável de staging, identificada pelo `run_id`; não deve ser confundida com o progresso ao vivo da coleta.

A recuperação offline examinou 2.983 alvos, sem erros e sem novas propostas aceitáveis. Seus resultados estão em `data/runtime/web-integrity-20261107/replay/status.json`. Não houve substituição de textos por essa recuperação.

Às 11:30 BRT, o importador de progresso observava 28.373 candidatos: 25.498 com texto e 2.875 sem texto. Esses números não significam letras aprovadas. O processo de importação incremental permanece ativo.

## Validação

`python -m pytest tests/unit/lyrics -q --basetemp=data/runtime/test-web-integrity-20261107`: **518 passed**.

Ruff passou nos arquivos alterados. O diretório temporário dos testes deve permanecer no volume D:, conforme a restrição existente do serviço batch. Uma execução com o temporário padrão em C: falhou nessa restrição; a execução em D: passou integralmente.

Os novos testes cobrem preservação da proveniência do fallback, divergência real versus formatação, repetições, caches recentes, corrupção da evidência, versão Live incorreta e truncamento no início, meio e fim. Todos usam respostas simuladas e não iniciam chamadas pagas.

## Acompanhamento

Consultar os arquivos de status antes de informar conclusão. Fonte indisponível, evidência ausente, metadados conflitantes e diferença de texto são estados distintos. Nenhum deles autoriza inventar letras, escolher arbitrariamente uma edição ou ultrapassar bloqueios das fontes.

## Pedido de aprovação após validação

A auditoria da fotografia `464d1a5d12dee68d507c5a7bacebb4b4137c5f754ff90f25d241574125094f78` terminou às 12:01 BRT. Os 28.373 candidatos foram examinados: 24.505 correspondências com a fonte, 113 correspondências com metadados pendentes, 877 evidências de origem não resolvidas e 2.878 ausências de letra. Não houve diferença textual ou corrupção de hash detectada entre as respostas efetivamente reextraídas e os textos comparados. Isso não resolve as evidências ausentes nem comprova gravação e completude.

Após o pedido de aprovação, iniciou-se uma nova verificação na fotografia mais recente, `3fed7df90204ee85887bfb1df5434262ade3a04c0331af35307e8dcf0fdb7e1a`, em `data/runtime/lyric-adjudication-20261107`. Ao concluir, gera `adjudication-queue.jsonl`, com ID, título, artista, hash, origem, resultado e pendência por candidato, sem copiar letras nem aprovar automaticamente. A fila só recebe o nome final após toda a execução; durante a geração existe um arquivo `.part`.

Uma retomada agora relê e verifica a impressão digital dos arquivos de resposta, além do texto e dos metadados, antes de reutilizar resultados. Resultado inalterado pode ser reutilizado entre fotografias somente com a mesma assinatura completa. Um piloto real de três registros verificou a geração da fila e a retomada dos três resultados, sem escrita de produção.

O gate existente admite aprovação fundamentada em `official_transcription` ou `human_audio_verification`, vinculada ao documento, à gravação, à fonte e ao hash. A autorização do usuário para aprovar depois da validação não constitui evidência de que a validação aconteceu. Nenhuma aprovação foi fabricada a partir de concordância entre caches, título/artista ou HTTP 200. A coleta e a continuação corretiva permanecem ativas, sem inferência paga.

## Retomada efetiva às 16:15 BRT

A continuação anterior não executou a recuperação pretendida: seu manifesto continha `ends_at=2026-07-12T04:52:27-03:00`, anterior ao início em novembro. A conversão de datas usada na configuração foi incorreta. A afirmação anterior de que essa continuação recuperaria pendências não se confirmou. O manifesto e os logs foram preservados como evidência, sem reescrever o histórico.

`require_active_campaign` agora verifica o prazo, a ordem entre início e fim e os hashes dos insumos antes de alterar o armazenamento de aquisição. Testes reproduzem a data invertida e uma campanha vencida.

A nova campanha está em `data/runtime/import-all-lyrics-resume-20261107`, iniciada em `2026-11-07T19:15:29.391940Z`, com limite em `2026-11-08T07:15:29.391940Z` (04:15 BRT). Seu manifesto foi criado pelo supervisor Python, sem conversão de datas pelo PowerShell. Toda a seleção é elegível para reexaminar ausências e sinais de conflito; textos existentes e rankings são preservados.

Um teste público do embed Spotify passou a fornecer duração para um candidato anteriormente sem esse dado. O coletor nativo já existente foi iniciado com atualização das durações ausentes para 2.467 IDs Spotify pendentes ou sinalizados. Preserva as provas antigas e não persiste sessões ou tokens. Pausa nas respostas de bloqueio ou limitação. A descoberta de duração não aprova identidade ou completude.

`watch_native_lyric_replays.py` acompanha as novas provas e recupera candidatos usando somente os caches locais. O importador incremental agora observa propostas offline, além da fila de aquisição, para importá-las mesmo antes do encerramento do coletor. Apenas o importador ocioso foi reiniciado para carregar essa mudança; a coleta permaneceu ativa.

O staging também passou a distinguir checkpoints negativos `*.outcome.json` das propostas positivas. Tentativas sem letra não interrompem a importação; uma proposta positiva malformada continua causando erro explícito. Testes cobrem ambos os casos.

Às 16:24 BRT, oito propostas novas haviam sido importadas no snapshot `3f5385396c0bf88497d30fde7239b7657110216ab1aecddf2e04d700d440e765`: 25.506 candidatos com texto, 2.867 sem texto. As oito foram reextraídas da evidência preservada e todas tiveram `source_chain_matched`, sem aprovação. A conferência individual está em `data/runtime/import-all-lyrics-resume-20261107/native-replays/source-chain-checks.jsonl`. A contagem da SQLite de aquisição pode ficar temporariamente abaixo do staging, que também incorpora as propostas offline verificadas.

Às 16:26 BRT, o snapshot seguinte `f1ac657f68f099c8799188456352a2dab7a6d42eb3e530ba335a47ae2d8bae76` confirmou 25.510 candidatos com texto e 2.863 ausências: mais 12 textos em relação ao início da retomada. Os estados de conflito passaram de 250 para 249; os de adjudicação pendente, de 693 para 692; suspeitas de parcialidade permaneceram em 47. Não são aprovações. A conferência independente das propostas novas examinou 17 arquivos e reproduziu todas as 17 letras a partir da evidência preservada.

A atualização nativa obteve 541 durações nessa fase, sofreu uma resposta 504 e retomou após a espera de 60 segundos prevista pelo coletor. A recuperação local e o staging continuam acompanhando suas publicações. A suíte completa de letras passou com **522 testes**, e Ruff passou nos arquivos alterados. Não houve chamadas pagas.

## Preparação local para Vertex em 8 de novembro

O snapshot final da rodada anterior, `e0660a54a9781fc3ee599d80252ab246d96869cbecb33ee9dfb5b5ccdd7cf44f`, contém 28.373 candidatos, dos quais 25.566 têm texto e 2.807 não têm. Não há adjudicações positivas registradas na tabela canônica de letras. Os estados de triagem são 24.580 adquiridos sem comprovação integral, 691 pendências de adjudicação, 248 conflitos de identidade e 47 suspeitas de parcialidade. Esses estados não são taxas confirmadas de erro.

`scripts/prepare_vertex_readiness.py` produz um dossiê local imutável, sem clientes de upload/inferência. A última execução está em `data/runtime/vertex-preparation-20261108/dossier-0004`:

- `protocol.json`, `prompt-template.txt`, `response-schema.json` e `generation-config.json`: conteúdo efetivo do contrato e hashes da implementação; congelamento de conteúdo não equivale a aceitação científica;
- `prices.json`: valores batch globais do modelo configurado, conferidos em fonte oficial em 8 de novembro e válidos até 31 de dezembro de 2026; modelo, região, modalidade, ambos os preços e validade temporal são verificados contra as configurações efetivas;
- `pending-candidates.jsonl`: todas as pendências por ID, título, artista, hash e auditoria, sem texto integral ou aprovação fabricada;
- `local-budget-reconciliation.sqlite` e `budget.json`: cópia reconciliada do ledger local, sem modificar o ledger de produção; não atesta fatura externa. Não há compromissos conhecidos para a revisão. O teto de planejamento é o menor dos limites documentados, US$150; gasto autorizado continua em zero;
- `readiness.json` e `manifest.json`: bloqueios explícitos, contagens, impressão digital dos artefatos e hash do produtor. Não foi gerado arquivo de requisições para músicas sem aprovação.

Fonte de preços: https://cloud.google.com/model-garden/pricing . Documentação do modelo e suporte batch: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash . A conferência não habilita faturamento, não atualiza permissões e não autoriza envio.

O piloto está planejado como um canário e 99 itens subsequentes. Sua execução e aceitação empírica não podem ser declaradas concluídas sem executar a inferência; permanecem bloqueadas pela instrução explícita de não iniciar chamadas pagas. Também permanecem pendentes evidência oficial/escuta integral, vinculação canônica aprovada, condições de uso das letras, aceitação científica do protocolo, reconciliação de faturamento externo e preflight de permissões cloud. Nenhuma dessas verificações foi simulada como se fosse evidência real.

Uma nova campanha de recuperação começou às 09:02 BRT em `data/runtime/import-all-lyrics-20261108`, direcionada a 4.033 candidatos ausentes ou sinalizados, preservando os demais. Limite da rodada: 15:02 BRT; pausas das fontes continuam compartilhadas. O importador de progresso está ativo. A verificação completa da origem do snapshot anterior foi iniciada separadamente em `data/runtime/vertex-preparation-20261108/source-audit`; conferir seu status antes de afirmar conclusão.

Validação da preparação: **532 testes unitários de letras passaram**, incluindo expiração de preços, incompatibilidade de modelo/região/modalidade, alterações em cada preço, adulteração de rankings e referências fora do projeto. Ruff passou. A geração real do dossiê foi executada com transação PostgreSQL somente de leitura e sem upload ou inferência.

Durante essa rodada, o importador incremental recusou inicialmente o hash de `combined.jsonl`: o coletor havia regravado os metadados nativos no mesmo arquivo. A comparação independente com as fontes congeladas comprovou que todos os vínculos, posições, cotas e métricas permaneceram iguais. O importador agora permite essa atualização somente após conferir os hashes das fontes e reconstruir a seleção completa; alterações de música, país, ano, posição, cota, métrica, status de seleção, remoções ou duplicações continuam sendo rejeitadas. O coletor foi corrigido para preservar os bytes de snapshots já existentes, usando os metadados atualizados apenas na fila de aquisição. O importador foi reiniciado após a correção e voltou a gerar staging.

O finalizador `scripts/finalize_vertex_dossier.py` está ativo e aguarda o término da coleta e da auditoria em andamento. Depois verifica a fotografia final e gera `data/runtime/vertex-preparation-20261108/final-dossier`, sem upload, reserva paga ou inferência. Seu status fica em `data/runtime/vertex-preparation-20261108/finalization/status.json`. Concluir a geração do dossiê com bloqueios documentados não equivale a aprovar letras ou aceitar o piloto.

Após a correção da seleção, **560 testes de letras e ingestão passaram**, e Ruff passou nos arquivos envolvidos. A conferência real do manifesto do dossiê verificou nove artefatos sem divergências; o hash do produtor também corresponde ao script atual. O staging incremental voltou a concluir com código zero. A auditoria subsequente permanece em execução e não deve ser confundida com uma revisão humana concluída.

## Continuação da recuperação às 09:31 BRT

A campanha de 8 de novembro e o auditor já estavam ativos; nenhum coletor concorrente foi iniciado. O Genius permanecia com pausa compartilhada por limitação de acesso.

Foi corrigida uma lacuna: a duração nativa, já aplicada na busca inicial do LRCLIB, não chegava à descoberta por busca livre nem à reconciliação de créditos por papéis. Agora esses caminhos recebem o mesmo filtro de incompatibilidade de duração. Sem duração, versões divergentes continuam bloqueadas; versões com a mesma duração e textos diferentes também não são escolhidas arbitrariamente. O filtro não certifica a transcrição da gravação.

A reexecução offline em `data/runtime/duration-replay-20261108` examinou 3.788 alvos recuperáveis dentro do filtro de 4.033 candidatos ausentes/sinalizados. Encontrou 12 propostas, sem erros e sem rede: cinco ausências e sete reparos de resultados sinalizados. As 12 foram reextraídas das respostas preservadas, tiveram hashes e metadados conferidos e passaram novamente pelos validadores de substituição vinculada ao hash anterior. Os resultados individuais estão em `publication-checks.jsonl`. Somente depois dessa conferência as propostas foram publicadas em `offline-replay`, sem escrever na SQLite de aquisição enquanto o coletor está ativo.

O staging confirmou a importação no snapshot `9498eb2b3e718432b8b46aa94295842794483c486636798fd58009d3fe9cbd0e`: **25.571 candidatos com texto e 2.802 sem texto**. Os textos anteriores continuam preservados e nenhuma aprovação definitiva foi registrada. A auditoria de qualidade desse novo snapshot permanece separada da comprovação oficial/escuta integral.

Também foi corrigida a criação do diretório de saída do replay quando seus diretórios pais ainda não existem. Os testes de descoberta cobrem duração ausente, incompatível, compatível e reconciliação por papéis, mantendo falsas as validações de identidade/completude e a autorização de classificação. A suíte ampliada passou com **564 testes de letras e ingestão**, e Ruff passou.

A auditoria desse snapshot terminou às 09:39 BRT: 24.592 adquiridos sem comprovação integral, 690 pendências de adjudicação, 241 conflitos de identidade, 48 suspeitas de parcialidade e 2.802 ausências. A redução de 248 para 241 conflitos é um resultado de triagem, não sete aprovações. O acréscimo de uma suspeita de parcialidade refere-se a `SPOTIFY:3xJK8ywApYVEYIDhymYMC6`: o hash do texto permaneceu igual, a divergência de duração deixou de existir e o sinal anterior `short_text` continuou presente. O candidato permanece retido para comprovação.

`scripts/publish_source_checked_replays.py` agora executa a conferência de reprodução da fonte e a vinculação ao resultado atual antes de publicar propostas para staging. Uma segunda execução sobre as 12 propostas confirmou idempotência: 12 já publicadas, nenhuma duplicação, nenhuma aprovação e nenhuma escrita na SQLite de aquisição. Testes também bloqueiam resposta bruta corrompida e substituição indevida de texto existente; checkpoints negativos são ignorados.

O finalizador foi atualizado e reiniciado enquanto ainda aguardava, sem interromper coleta ou auditoria. Após a coleta atual, ele executará mais uma recuperação estritamente offline com o código corrigido, publicará apenas propostas cuja origem foi reproduzida e cuja vinculação continua válida, fará staging e auditoria de qualidade, verificará a origem da fotografia final e reconstruirá o dossiê. A rodada offline posterior usa as respostas novas que o coletor obtiver; não abre outra coleta web e não inicia inferência.

Validação final desta continuação: **567 testes de letras e ingestão passaram** e Ruff passou. Coleta, auditoria de origem e finalizador continuavam ativos às 09:44 BRT, com zero chamadas pagas e zero aprovações definitivas.

## Comparação com respostas web atuais — 8 de novembro

O pedido seguinte distinguiu a comparação com a web atual da reprodução de respostas antigas. `scripts/compare_all_lyrics_web.py` e `lyrics/web_comparison.py` implementam essa etapa separadamente, sem confundi-la com adjudicação.

O piloto real de cinco candidatos terminou em `data/runtime/web-comparison-pilot-20261108`: três conjuntos de edições ambíguas, uma diferença textual e uma concordância com o mesmo provedor. Não houve aprovação. O comparador preserva repetições, exige título/versão e créditos compatíveis, aplica duração quando comprovada e não escolhe arbitrariamente uma edição maior. Uma concordância entre provedores pode refletir cópia entre sites; não comprova, por si, transcrição integral da gravação.

A tentativa inicial da fila integral preservou 16 resultados em `data/runtime/import-all-lyrics-web-comparison-20261108`, mas recebeu limitação de acesso do LRCLIB. O processo foi encerrado enquanto aguardava a pausa, sem descartar resultados ou respostas. Seu status foi marcado como pausado para serialização, com cópia do status anterior.

A fila integral serializada está em `data/runtime/import-all-lyrics-web-comparison-final-20261108/status.json`. Ela aguarda a coleta atual terminar para não disputar o limite público de requisições. Depois captura a fotografia mais recente **da seleção correta**, verifica seu conjunto de candidatos e compara todos os 28.373 IDs, priorizando ausências e sinais de erro. O período de até 24 horas conta a partir do início efetivo da comparação. Não há garantia de conclusão nesse prazo caso as fontes continuem bloqueadas.

O comparador consulta o LRCLIB atual: busca por metadados quando a aquisição veio de outro provedor e consulta pelo ID quando a origem já era LRCLIB. Portanto os resultados distinguem concordância no mesmo provedor, concordância entre provedores, divergência, edições ambíguas e indisponibilidade. Ele não empresta respostas de campanhas antigas, registra cada resposta bem-sucedida com hash e respeita `Retry-After` e as pausas compartilhadas. A documentação de limites foi consultada em https://lrclib.net/docs.md; a aplicação se identifica sem registrar credenciais ou tentar contornar restrições.

Os insumos são copiados para uma SQLite privada com snapshot PostgreSQL somente de leitura; não se mantém uma transação PostgreSQL aberta durante a comparação longa. O processamento usa uma fila indexada e retomável, com apenas um candidato em memória. Somente propostas sem sinais impeditivos e para ausências/reparos sinalizados seguem para o publicador, que novamente reproduz a fonte e verifica o hash anterior. Publicações aceitas fazem staging; nenhuma comparação marca identidade, completude ou classificação como aprovadas.

O finalizador agora aguarda também essa comparação integral antes da última recuperação offline, auditoria e reconstrução do dossiê. Erros explícitos passam a ser gravados em seu status. As execuções foram mantidas sem inferência Vertex, upload ou chamadas pagas.

Validação: **575 testes de letras e ingestão passaram**, com casos de concordância sem aprovação, refrão ausente, versão Live diferente, artista incorreto, duração incompatível, duas edições igualmente compatíveis e corrupção do texto armazenado. Ruff passou. O piloto real confirmou requisições web atuais e persistência dos resultados. Às 10:19 BRT, o retrato importado continuava em 25.571 textos, 2.802 ausências, 241 conflitos e 48 suspeitas de parcialidade; a comparação integral serializada ainda estava aguardando a coleta.

## Importação das músicas dos novos mercados

Após o pedido explícito para importar as músicas incorporadas na expansão mundial, o fluxo passou a aceitar o protocolo `worldwide-annual-quotas-v1`. A verificação real de `verify_global_annual_import.py` passou: 92.000 vínculos observados e preservação dos 86.090 vínculos anteriores. A expansão acrescentou 5.910 vínculos em BY, HK, KZ, NG, PK, RS, UG, VE e ZW, incluindo 2.554 identidades candidatas que não existiam na seleção anterior. Vínculos novos de um ID já existente reutilizam a letra desse mesmo ID, sem nova aquisição ou duplicação da música.

`lyrics/global_import.py` valida os hashes dos artefatos, cotas, posições e preservação dos objetos anteriores, prepara o delta de novos IDs e produz staging global imutável. O armazenamento `data/derived/lyrics/global-20261108` contém apenas a aquisição desse delta; o restante é herdado do snapshot de letras anterior. Os textos são conferidos por SHA-256, preservando inclusive quebras CRLF. IDs YouTube opacos não são transformados em IDs de vídeo nem considerados gravações canônicas confirmadas.

`scripts/import_new_global_lyrics.py` iniciou a campanha em `data/runtime/global-lyrics-20261108`. Reaproveitou quatro resultados pelo ID nativo exato. A recuperação offline examinou 2.554 alvos, encontrou 122 propostas e terminou sem erros ou rede. O primeiro staging global confirmou 30.927 candidatos e 25.696 textos disponíveis. Em seguida, a mesma recuperação online anterior, com store explícito, iniciou somente os 2.554 IDs novos, compartilhando as pausas dos provedores. São até 12 horas nesta rodada, com zero chamadas pagas autorizadas.

A união de candidatos ultrapassa o limite histórico de 30 mil. O pedido autoriza a importação pública do delta; não modifica os limites de classificação, o orçamento ou a autorização de inferência. Os snapshots permanecem com identidade/completude não aprovadas, direitos não verificados e classificação bloqueada. Rankings provisórios e 2026 parcial conservam seus estados; lacunas de países/anos não recebem músicas inventadas.

O importador incremental foi ampliado para unir a aquisição antiga e a nova por ID, preferindo o resultado do delta quando o ID coincide. Publicações, auditoria, comparação web e geração de dossiê receberam parâmetros explícitos de seleção/store. O staging global herda os textos anteriores, inclui o delta e mantém todos os vínculos novos de músicas já conhecidas. A navegação PostgreSQL dos candidatos foi testada nos nove mercados adicionais e retornou registros em todos eles.

O snapshot `733d59fa8681982a839c9cf295a037a72d9cb3a7df485f63e0335e30144ebd79` confirmou **992 dos 2.554 novos candidatos com texto**, restando 1.562 novos sem texto. No conjunto global: **26.563 com texto e 4.364 sem texto**. Esses números se referem a esse snapshot; a coleta e as importações incrementais continuam. O dossiê global correspondente está em `data/runtime/vertex-global-preparation-20261108/dossier-intake-0001` e permanece bloqueado para submissão.

Para não duplicar a pressão sobre as fontes, a comparação web anterior foi pausada com **18.732 resultados preservados**, sem interromper o coletor do delta. A continuação global aguarda em `data/runtime/import-all-lyrics-web-comparison-global-20261108`, agora abrangendo os 30.927 candidatos. Respostas da mesma comparação com até 24 horas no início da continuação podem ser reutilizadas somente após conferir domínio, URL, nome/hash do arquivo e bytes da resposta; datas originais são preservadas e a comparação é refeita contra o texto/metadata atuais. Respostas antigas ou corrompidas não são reutilizadas. Não se reaproveita uma aprovação nem se muda a data de uma consulta anterior.

O finalizador anterior foi marcado como substituído pelo fluxo global. A auditoria de origem, a comparação e o dossiê final globais estão encadeados em `data/runtime/vertex-global-preparation-20261108`, usando a seleção e o armazenamento corretos. Nenhum desses passos faz upload ou inferência Vertex.

Validação: **583 testes de letras e ingestão passaram**, incluindo preservação das posições antigas, rejeição de artefatos adulterados, reutilização idempotente por ID, preservação de bytes, staging global sem aprovação e rejeição de respostas expiradas/corrompidas. Ruff passou. A verificação anual real, o staging PostgreSQL, a consulta dos nove mercados, o piloto da auditoria e a geração do dossiê global foram executados.

A fotografia global posterior `ab3d9d0ca27e226f7787bda510c454cdbde6ed3d9ddb69cfe223b3f3ed9a32ef` confirmou **1.394 novos candidatos com texto e 1.160 novos ainda sem texto**. No conjunto: 26.965 textos e 3.962 ausências entre 30.927 candidatos. A coleta continuava na primeira rodada, e os logs da aquisição, do importador incremental, da comparação agendada e do finalizador não apresentavam erro de execução. Disponibilidade do texto continua separada da aprovação de identidade/completude.
