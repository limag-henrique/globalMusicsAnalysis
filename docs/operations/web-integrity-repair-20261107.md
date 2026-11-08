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
