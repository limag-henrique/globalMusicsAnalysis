# Auditoria de identidade das letras — atualização 2026-09-27

## Escopo e integridade

Auditoria local do banco em transações PostgreSQL explicitamente somente leitura. Nenhum registro, snapshot, job ou arquivo do corpus foi alterado; não houve chamada paga ao Gemini. Foi criado/atualizado apenas o manifesto local de quarentena e o código do importador para contenção futura. Letras e respostas brutas não foram impressas nem copiadas para este relatório. O relatório registra agregados, metadados de faixa, hashes e IDs.

O corpus contém 159.111 documentos: GENIUS 124.591; LETRAS 26.540; LRCLIB 7.039; LYRICS_OVH 937; GOOGLE_MANUAL 4. Todos os 159.111 têm `language_code` nulo.

Em 27 de setembro de 2026 foi aplicada uma suspensão de fonte: os 26.540 documentos `LETRAS` permanecem preservados, mas são inelegíveis para novas importações, novas filas online/batch, retries e métricas científicas até validação independente. A suspensão é prospectiva e científica; não cancela nem modifica os batches Vertex já submetidos. Na aplicação da política, 26.536 documentos `LETRAS` já estavam reservados nos dois batches principais e continuam importáveis/reconciliáveis como evidência provisória imutável.

Na varredura local do JSONL de entrada, 1 registro não pôde ser interpretado como JSON; foi contado como malformado e não entrou na análise do grupo de hash. Seu conteúdo não foi reproduzido.

## Método da amostra

A amostra-base atual contém 179 documentos selecionados por ordenação pseudoaleatória reproduzível (`md5(UUID || seed)`), estratificada em 25 GENIUS, 100 LETRAS, 25 LRCLIB, 25 LYRICS_OVH e os 4 GOOGLE_MANUAL. O seed foi `identity-audit-20260927`; após o achado confirmado em LETRAS, a amostra desse estrato foi ampliada para 100 itens pela mesma ordenação. Como os estratos foram equalizados e o seed é determinístico, não se deve extrapolar as proporções observadas para o corpus.

Foram adicionados 30 documentos por seleção intencional, totalizando 209, para garantir casos <100 e 100–199 caracteres, resíduos sinalizados, títulos duplicados, hashes compartilhados entre faixas, identidades/títulos genéricos, marcadores de versão/remix/feat/tradução e o caso “Los sabanales”. Essa parte enriquecida é deliberadamente enviesada e não entra nas taxas da amostra-base.

Na amostra-base, heurísticas de script Unicode e listas pequenas de palavras sugeriram inglês, espanhol, português, francês, italiano, alemão, neerlandês, finlandês e casos de script misto. São rótulos exploratórios, não detecção validada de idioma. A amostra cobriu letras multilíngues; a fonte não fornece idioma registrado.

## Sinais locais observados

| Fonte | N base | <100 | <200 | Resíduo estrito | Título duplicado | Hash em outra faixa | Título/identidade genérica | Marcador de versão |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GENIUS | 25 | 1 | 1 | 0 | 5 | 1 | 0 | 1 |
| GOOGLE_MANUAL | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| LETRAS | 100 | 0 | 2 | 1 | 18 | 30 | 1 | 17 |
| LRCLIB | 25 | 0 | 1 | 0 | 5 | 0 | 0 | 2 |
| LYRICS_OVH | 25 | 1 | 1 | 0 | 5 | 0 | 0 | 2 |

“Título duplicado” significa título normalizado ligado a mais de uma faixa; é um aviso de desambiguação, não um erro por si só. “Hash em outra faixa” significa igualdade SHA-256 exata do texto entre identidades canônicas distintas; é um sinal forte para revisão, mas também pode refletir versão, tradução, cover ou metadado divergente.

### Taxas observadas por fonte

Não há taxa válida de correspondência letra–faixa calculável nesta etapa: no banco, 0/179 itens da amostra-base tinham uma segunda fonte para a mesma identidade canônica. A busca externa aberta tentada para os 79 itens não-LRCLIB não retornou respostas utilizáveis (79/79 indisponíveis); LRCLIB não foi usado para validar itens que já vieram de LRCLIB. Portanto, o denominador de comparações independentes concluídas é zero por fonte e a taxa de correspondência é **não estimável**, não 0%.

Como indicador de risco distinto — não como taxa de erro ou de correspondência — a amostra-base apresentou colisão de hash entre identidades em: GENIUS 1/25 (4,0%); GOOGLE_MANUAL 0/4 (0%); LETRAS 30/100 (30,0%); LRCLIB 0/25 (0%); LYRICS_OVH 0/25 (0%).

No corpus completo, 9.493 documentos estão em grupos de hash compartilhado por faixas diferentes: GENIUS 1.365/124.591 (1,10%; 672 grupos); LETRAS 8.106/26.540 (30,55%; 2.684 grupos); LRCLIB 11/7.039 (0,16%; 6 grupos); LYRICS_OVH 11/937 (1,17%; 6 grupos); GOOGLE_MANUAL 0/4. No total, 4.440 documentos LETRAS pertencem a grupos com três ou mais identidades canônicas. Isso não prova erro em cada registro, mas impede tratar esses casos como correspondência confirmada sem revisão.

### Comprimento e resíduos

Nos documentos do corpus, 2.122 têm menos de 100 caracteres e 8.187 menos de 200. Entre os itens efetivamente submetidos nos dois lotes principais, os totais são 2.118 e 8.182, respectivamente — consistente com a diferença entre corpus e itens submetidos.

Um detector textual estrito de marcadores explícitos de interface encontrou 95 documentos LETRAS; um conjunto mais amplo encontrou 521. O valor anteriormente informado de 26.535 resíduos LETRAS não foi reproduzido por essas regras; como a definição anterior não está disponível, esse número permanece não reconciliado e não é apresentado como contagem auditada.

Há 11.896 grupos de títulos normalizados duplicados no corpus. Os padrões de versão presentes no título são somente triagem lexical, não verificação da gravação específica.

## Casos examinados

### Incorreto confirmado

- `179e80ba-a52b-5775-9258-6425f8ecbb6d` — LETRAS, “Los sabanales”, Calixto Ochoa, 1.226 caracteres. O conteúdo local não contém os termos-âncora do trecho de referência consultado. O Ministério da Cultura da Colômbia credita “Los sabanales” a Calixto Ochoa e descreve a canção; a coleção Frontera da UCLA cataloga gravação de “Los Sabanales” e atribui Ochoa como compositor. A identidade de título/compositor é corroborada, mas o texto armazenado não corresponde à referência consultada; tratar como **letra incorreta**, em quarentena para correção. Referências: [Ministério da Cultura da Colômbia](https://mng.mincultura.gov.co/Sitios/patrimonio/bibliotecas-de-cocinas/tomos/tomo10.pdf), [UCLA Strachwitz Frontera Collection](https://frontera.library.ucla.edu/recordings/los-sabanales).

### Identidade ambígua — hashes idênticos em títulos distintos

Os seguintes grupos LETRAS foram selecionados aleatoriamente e têm texto idêntico associado a títulos diferentes. São suspeitos para revisão/quarentena, não erros confirmados individualmente:

- “Batman” / “Maux de tête”, Lefa: `0f5fb32c-b8ad-5b20-b9bc-bce1b9411e82`; `7254b04e-dc20-5905-9b92-75b2c5b697b4`.
- Happoradio, três títulos — inclui “Tehdään jotain kaunista - Akustinen versio”: `35c33257-4988-5cf4-ac4b-51d1c6ad1993`; `7287baf9-f0f6-57b2-9647-a539a2d1dedc`; `dfc705e2-9f76-5b0b-8136-f6e9524dd54b`. Catálogos oficiais confirmam que a versão acústica existe; isso não valida o texto compartilhado. Referências: [Happoradio](https://www.happoradio.net/majakka), [Biblioteca Nacional da Finlândia](https://kansalliskirjasto.finna.fi/Record/fikka.5427019).
- Anh Khang, três títulos — inclui “Ai Con Cho Ai (Acoustic Mix)”: `6809c2bd-5dd8-594a-9188-0de6b1327c66`; `495f3f48-f9cc-57be-8d42-b9bc5501227f`; `e1759482-05e8-5329-be53-906ac0a27d0b`.
- Maico, “Goodbye” / “Moment” / “Hey Hey”: `75bc182c-47a9-5cc2-8abd-775caa499270`; `43c1fcfa-0208-542a-b8bb-54176255a2bb`; `fc64457e-7c0b-5908-a49d-208fd02caef9`.
- Boris Brejcha, “Maximum Overdrive” / “Lost Memory”: `939b65be-fdc3-5e4e-9e71-366952271b08`; `6cac230c-4157-52a2-8d73-06bd781ea70e`.
- “Djúsinn” / “Încrederea”, Amma vs. AMNA e George Hora: `b2ba3365-51b0-5315-a349-5de6433a0330`; `5205e9a5-f739-57ae-8a75-a2365f0d6341`.
- Joshua Dietrich, oito títulos com o mesmo hash: `cf976865-7169-5f2d-8d4c-db95ffc0da40`; `1af364dc-e70a-5105-a79d-dc128701eaf1`; `42dddbb4-fc0d-52b8-bffa-17f4a5b5111c`; `6488e459-a314-57fc-ae9f-f2352bb6449b`; `6923edb2-8b47-5b81-97eb-85287599e47d`; `8082f7ca-49a0-5f71-b77c-7598893616d7`; `c2ff793c-d842-598b-ad8b-dc4a4a0b4193`; `d021b994-a0de-5c1f-a304-1f66f025f3d0`.

### Texto insuficiente e resíduos — exemplos para revisão

- Menos de 100 caracteres: GENIUS `185cd502-63e9-507d-a900-3314b75cd781`; GENIUS `9c706a75-6dd0-5c49-9cce-0ddfa7d78003`; LRCLIB `74d6d472-e3c4-5710-8143-9567de5d5782`; LYRICS_OVH `67721564-b517-59bd-9658-5e3b636db682`.
- Marcador estrito de resíduo na amostra: GENIUS `599fe476-0a53-5b73-859e-d4e43a21e7fc`; LETRAS `4245c2db-0b8d-5b46-afba-0df0cc685531`; LRCLIB `da98b7d0-b5e6-5b89-8186-5849967efe8a`; LYRICS_OVH `00221f0f-124c-50d4-9557-d49d26882977`.

## Fotografia inicial do progresso operacional (histórica; substituída abaixo)

- Run `9361b92b-64b6-4cb5-adb9-1a23dd78ec50`: 28.074/118.549 concluídas (23,68%), estado `running`, sem erro reportado pelo provedor.
- Run `41934591-0444-4fce-bfde-238497f31e3a`: 23.467/40.460 concluídas (58,00%), estado `running`, sem erro reportado pelo provedor.
- Nenhum dos dois runs ativos tem itens importados ou erros registrados ainda. O ledger histórico tem 2 erros de item `batch_invalid_provider_status` em um run encerrado; são anteriores e separados desta auditoria.
- RAM livre observada: aproximadamente 0,90 GB; nenhuma importação iniciada.

## Conclusão provisória da varredura inicial

Há um erro de letra conhecido confirmado e um agrupamento anormalmente alto de hashes LETRAS reutilizados entre identidades distintas. Naquela primeira passagem, a taxa de correspondência não era estimável porque ainda não havia comparações independentes concluídas. Essa conclusão foi supersedida pela validação externa item a item documentada abaixo; não reutilize as taxas de denominador zero como resultado final.

## Contenção reversível — atualização 2026-09-27

O manifesto versionado em `config/lyrics_identity_quarantine.json` registra 752 documentos sem texto bruto: 1 `confirmed_mismatch` (Los sabanales), 8 `suspected_mismatch` (grupo Joshua Dietrich com hash exato compartilhado entre oito identidades sem evidência de versão), 739 `insufficient_text` (4 textos curtos da seleção dirigida e o grupo LETRAS descrito abaixo) e 4 `contaminated_text` (marcador estrito de interface). As fontes são LETRAS 745, GENIUS 3, LRCLIB 2 e LYRICS_OVH 2. Cada registro preserva IDs do documento/faixa, título, artista, fonte, hash, motivo, método e evidências; referências a snapshots existentes são explícitas. Nenhuma colisão de hash isolada fora de grupo comprovadamente reutilizado foi automaticamente promovida a letra incorreta.

Na amostra pseudoaleatória LETRAS ampliada (n=100), 30 itens tinham hash exato compartilhado com outra identidade canônica; 17 títulos tinham marcador de versão; 18 tinham título normalizado duplicado; 1 tinha resíduo estrito; 2 tinham menos de 200 caracteres e nenhum menos de 100. Esses são sinais de risco, não proporções de erro. Intervalos de Wilson de 95% para sinais na amostra: hash compartilhado 30/100, 21,89–39,58%; marcador de versão 17/100, 10,89–25,55%; título duplicado 18/100, 11,70–26,67%; resíduo estrito 1/100, 0,18–5,45%; texto <200 2/100, 0,55–7,00%; texto <100 0/100, 0–3,70%. Para os demais estratos, a amostra-base permanece nos tamanhos descritos na tabela anterior. Nenhum desses intervalos mede correspondência letra–identidade.

Os 100 registros LETRAS compartilham o mesmo `source_version` (`legacy-api-import-v1`), timestamp de ingestão do artefato (2026-09-19 03:05:57.674939 UTC) e valor de metadados; portanto, o banco não permite estratificar esses registros por horário real da chamada à API ou versão individual da resposta. O timestamp observado é do arquivo importado, não prova o horário de aquisição.

O achado sistêmico contém 735 IDs LETRAS distintos, 735 combinações de artista/título e o mesmo hash de texto com 176 caracteres; os 735 estão marcados `FOUND` no próprio `data/derived/lyrics/gemini_annotations.jsonl`, antes da importação. Todos os títulos diferem do texto compartilhado; somente 1 nome de artista aparece. O texto contém um marcador relacionado a instrumental, mas não sustenta classificação específica por música. A classificação aplicada é `insufficient_text`, não `confirmed_mismatch`, pois não é evidência de qual seria a letra correta. Exemplos de metadados associados incluem “Iron Man 3” (Brian Tyler), “The Imitation Game” (Alexandre Desplat, London Symphony Orchestra) e “Neutron Dance - Edit” (Krystal Klear). O corpo da letra não é reproduzido.

A proveniência prova que a repetição já existia no JSONL e não foi criada por hash/canonicalização do banco nem pelo resolver; portanto, a causa está na aquisição upstream (resposta do endpoint LETRAS ou cache/coleta). Sem logs brutos por requisição, não é possível distinguir API versus cache/collector. O importador legado usa `original_lyrics` diretamente e a identidade canônica vem de artista+título. A contenção reproduzível agora filtra, para futuras importações, pares exatos `(fonte, SHA-256)` em estado de exclusão. Uma assinatura igual de outra fonte não é bloqueada. O importador antigo também descartava `song_id`/`source_metadata`; essa lacuna reduz auditabilidade, mas não explica a repetição já presente no arquivo.

O seletor comum de classificação online e batch exclui esses quatro estados de novas seleções. Também há função explícita de elegibilidade científica pelo manifesto. Não existe hoje exportação científica de letras/classificações no produto; as exportações existentes são de charts e permanecem inalteradas. Itens já reservados nos batches ativos não foram removidos nem cancelados: 749 IDs do manifesto permanecem `submitted` (381 no run 9361… e 368 no run 4193…). Seus resultados poderão ser importados para preservar a reconciliação, mas serão exploratórios, não evidência definitiva para esses IDs. Dois IDs do manifesto constam como itens/snapshots importados em runs encerrados; um ID Joshua não tem linha de documento nem item no ledger.

Consulta local somente leitura encontrou dois snapshots `classified` preexistentes associados ao manifesto — `171beb7a-ab2d-4fda-9ad9-b8cfaef824fa` e `622d1d50-cc7a-4b31-bf8a-706056ef3a47` — com custo estimado somado de US$ 0,004180875. Ambos seguem intactos. A consulta mais recente encontrou os outros 749 itens do manifesto ainda `submitted`, sem resultado importado.

## Custos e próximos passos direcionados

Os dois runs principais ainda não têm custo real conhecido (`known_cost_usd` nulo). O ledger contém 5 runs no total, 3 encerrados com custo conhecido acumulado de US$ 0,1972747500; os dois ativos têm custo esperado de US$ 291,4195091250 e reserva conservadora de US$ 571,0554746250. Somando custos conhecidos e reservas conservadoras ativas, o compromisso operacional observado é US$ 571,2527493750, deixando US$ 23,7472506250 abaixo do teto operacional de US$ 595. Isso não antecipa cobranças reais dos jobs ativos; o saldo deve ser recalculado quando os custos forem reconciliados. Nenhuma chamada, retry ou novo upload pago foi iniciado nesta auditoria.

Como proxy de planejamento, os atuais runs correspondem a cerca de US$ 0,001832 esperado e US$ 0,003591 conservador por item; não substitui estimativa por tokens da letra corrigida. Reclassificar apenas o único caso confirmado teria, por essa média, proxy de cerca de US$ 0,0018 esperado / US$ 0,0036 conservador. Os 8 suspeitos não devem ser reclassificados antes de resolver a identidade; os 4 textos contaminados só entram em reprocessamento se uma limpeza determinística alterar conteúdo relevante; os textos insuficientes exigem obter versão completa autorizada. Para 735 linhas do grupo sistêmico, obter primeiro conteúdo correto; se isso ocorrer, o proxy seria cerca de US$ 1,35 esperado / US$ 2,64 conservador para uma futura análise direcionada, sujeito a novo preflight. Não há gasto adicional nesta etapa. Uma repetição futura de todos os 752 itens teria proxy conservador de aproximadamente US$ 2,70; isso é custo potencial evitado, não crédito economizado. Os 749 já submetidos não são canceláveis nesta auditoria e permanecem dentro da reserva ativa já contabilizada.

O custo adicional gasto nesta contenção foi US$ 0. O teto bruto de planejamento que se evita ao não reenviar os 17 itens agora é aproximadamente US$ 0,061 conservador, usando apenas a média das reservas dos dois runs; é uma proxy, não economia faturada nem orçamento global disponível.

## Causa e limites atuais

O erro de “Los sabanales” está confirmado no nível do documento, mas a causa upstream específica (aquisição LETRAS, associação de metadados ou resolução canônica) permanece sem reprodução. Para Joshua Dietrich, a reutilização entre oito identidades permanece `suspected_mismatch`, sem prova da origem. Para o grupo de 735, a causa foi reduzida ao estágio anterior ao banco (API ou cache/collector); a distinção final depende de logs de requisição que não estão armazenados. O filtro fonte/hash e os testes de regressão corrigem a reentrada reproduzível no importador. Nenhuma letra armazenada foi sobrescrita nem excluída.

## Classificação final por evidência e limites de taxa

Entre os casos especificamente revisados e registrados no manifesto há 1 `confirmed_mismatch`, 8 `suspected_mismatch`, 739 `insufficient_text` e 4 `contaminated_text`. Os 30 sinais de hash da amostra LETRAS não foram todos chamados de erro: covers, traduções, versões acústicas, remixes e feats exigem identidade de gravação e conteúdo independentes. Exemplos continuam ambíguos, incluindo Lefa (“Batman”/“Maux de tête”), as faixas acústicas de Happoradio e Anh Khang, e os oito títulos de Joshua Dietrich. Nenhum desses é declarado incorreto apenas por hash compartilhado.

Resultado histórico da primeira passagem: comparação independente 0/179. Esse registro foi substituído pelos resultados item a item e intervalos apresentados na seção “Resultado da validação independente — relatório atual”.

## Acompanhamento complementar — 2026-09-27

### Reconciliação mutuamente exclusiva dos 752 IDs

As categorias do manifesto são mutuamente exclusivas e somam 752: 739 `insufficient_text` + 4 `contaminated_text` + 8 `suspected_mismatch` (Joshua Dietrich) + 1 `confirmed_mismatch` (“Los sabanales”). Assim, 739 + 4 + 8 + 1 = 752, sem sobreposição entre categorias.

Dentro dos 739 `insufficient_text`, 735 são o grupo LETRAS com texto genérico idêntico de 176 caracteres e quatro são exemplos distintos com menos de 100 caracteres (2 GENIUS, 1 LRCLIB, 1 LYRICS_OVH). Esses quatro curtos não são os quatro `contaminated_text`: estes são outra classe disjunta, um por fonte GENIUS/LETRAS/LRCLIB/LYRICS_OVH. O grupo Joshua Dietrich tem oito IDs LETRAS e o caso Los sabanales tem um ID LETRAS. A linha JSONL malformada é um registro de entrada que não se converteu em documento; está contada à parte e não pertence nem aos 752 IDs do manifesto nem aos 749 itens do ledger.

O ledger não é uma partição adicional desses 752, mas um estado operacional cruzado: 749 foram submetidos nos dois jobs em curso (381 no run `9361b92b-64b6-4cb5-adb9-1a23dd78ec50` e 368 no run `41934591-0444-4fce-bfde-238497f31e3a`); dois IDs do manifesto já tinham item/snapshot importados em runs anteriores; um dos oito Joshua Dietrich (`1af364dc-e70a-5105-a79d-dc128701eaf1`) não tem nem linha de `lyric_document` nem item no ledger. Os três que não estão submetidos nos jobs ativos são, portanto, exatamente dois preexistentes + um ausente. Dos dois preexistentes, um é “Los sabanales” e outro é o contaminado LYRICS_OVH. Isso não soma 752+2: os snapshots pertencem a dois dos mesmos IDs do manifesto. Snapshot preexistente não equivale a nova análise do batch atual.

Dos 749 submetidos, 739 são insuficientes, 3 contaminados e 7 Joshua Dietrich. Os restantes 2 IDs do manifesto já tinham snapshot, e o último Joshua não foi submetido. Preservar e reconciliar snapshots futuros não muda esses itens para evidência científica: o filtro exclui pelo ID do documento e os registra separadamente como exploratórios.

### Auditoria de proveniência LETRAS

A busca local foi somente leitura. O grupo de 735 textos LETRAS idênticos aparece no JSONL importado atual como `FOUND`, antes de chegar ao banco; não aparece nos três backups JSONL disponíveis de 11 de setembro. O JSONL atual contém uma linha malformada, contabilizada mas não reproduzida. `source_metadata` está vazio/não estruturado nessas linhas e não há cache persistente ou log de chamadas por item que permita confrontar request/response. Assim, está estabelecido que o texto repetido antecede a persistência do corpus, mas não é possível separar defeito da resposta LETRAS de defeito no coletor/cache. Nenhuma coleta externa adicional foi feita e nenhum conteúdo foi corrigido.

### Exclusão científica de resultados em quarentena

O gerador do relatório de qualidade agora carrega os IDs excluídos do manifesto, expõe somente `quarantined_items` como contagem exploratória agregada e remove esses itens antes de calcular distribuição de status, confiança, erro, intensidades, custos amostrais, concordância e lista cega. Os snapshots permanecem intactos. A mudança foi testada em SQLite descartável: o registro em quarentena não aparece nas métricas nem na lista cega, o registro elegível permanece, e ambos os estados originais do banco continuam iguais após a consulta. O teste também cobre assinatura estrita: apenas o par fonte/hash explicitamente listado é bloqueado; mesmo hash em outra fonte e nova letra de uma versão acústica na fonte original continuam elegíveis.

### Batches — estado mais recente, 2026-09-27 19:08 UTC

- Run `9361b92b-64b6-4cb5-adb9-1a23dd78ec50`: 29.995/118.549 (25,30%), `running`, sem erro do provedor.
- Run `41934591-0444-4fce-bfde-238497f31e3a`: 25.470/40.460 (62,95%), `running`, sem erro do provedor.
- Nenhum reenvio, retry, cancelamento, nova chamada paga, importação ou reconciliação foi iniciado. Resultados ainda não importados.
- Três runs históricos encerrados têm custo conhecido de US$ 0,1972747500; os dois ativos seguem sem custo real (`known_cost_usd` nulo), com expectativa somada de US$ 291,4195091250 e reserva conservadora somada de US$ 571,0554746250. Compromisso calculado para o teto operacional é conhecido + conservador ativo = US$ 571,2527493750; saldo até o limite operacional de US$ 595: US$ 23,7472506250. O teto geral continua US$ 600, com US$ 5 reservados para atividade histórica. Esses valores são reservas/previsões, não cobrança faturada.

### Incidente de credencial

Um erro de validação anterior expôs parcialmente o valor de conexão usado pelo processo local. O alvo de rotação é a senha embutida em `CHART_OBSERVATORY_DATABASE_URL`, para o role `chart_observatory` no PostgreSQL local `chart_observatory` em `127.0.0.1:5432`; nenhum segredo é reproduzido neste relatório. A configuração aponta para Docker Compose/PostgreSQL local, não para uma credencial de provedor cloud. A senha ainda não foi rotacionada: uma rotação agora exigiria atualizar sincronizadamente a senha do role e todas as cópias/configurações locais sem interromper leitores que ainda dependem da conexão. Nenhum comando foi usado para imprimir a URL.

Procedimento seguro para o operador: (1) usar um gerenciador de senhas para gerar uma senha forte e única; (2) no terminal local do projeto, abrir `docker compose exec -it postgres psql -U chart_observatory -d chart_observatory`, executar `\\password chart_observatory` e inserir a nova senha apenas nos prompts ocultos; (3) substituir a senha somente no editor de segredos local/`.env` e em qualquer secret store de execução, sem colá-la em terminal com eco, chat, ticket ou histórico de shell; (4) reiniciar apenas serviços locais que leem esse DSN, não os jobs Vertex já submetidos; (5) depois, validar conexão nova e rejeição da antiga sem imprimir nenhum DSN. A validação pós-rotação ainda está pendente da ação humana; a porta Docker 5432 está publicada em todas as interfaces e deve ser restringida a loopback em uma janela operacional separada, após conferir consumidores locais.

## Resultado da validação independente — relatório atual

Foram concluídas 179 comparações item a item, pela seleção pseudoaleatória estratificada já fixada: GENIUS 25, LETRAS 100, LRCLIB 25, LYRICS_OVH 25 e GOOGLE_MANUAL 4. Os 4 GOOGLE_MANUAL constituem estrato dirigido/manual e não amostra probabilística. Para cada registro, a revisão conferiu a linha local de título/artista, procurou fonte pública independente por identidade exata e tentou comparar 2–3 fragmentos breves. O anexo [`lyrics-identity-sample-evidence-2026-09-27.md`](lyrics-identity-sample-evidence-2026-09-27.md) guarda ID, título/artista local, decisão, número de fragmentos corroborados, URL(s), data e resumo do método/evidência por item. Nenhuma letra completa ou fragmento literal foi registrado.

Regra de classificação conservadora: um ou mais fragmentos distintivos corroborados com metadados consistentes podem sustentar `probable`; fragmentos múltiplos e gravação/credits compatíveis sustentam `confirmed`; discrepância positiva sustenta `incorrect`; uma gravação relacionada sem confirmar a versão exata fica `related_version`; conflito não resolvido fica `ambiguous`; se não há transcrição acessível para comparar conteúdo, fica `not_verifiable`, mesmo quando catálogo confirma título e artista. A falta de fonte não foi tratada como erro. O intervalo de Wilson de 95% foi calculado sobre os numeradores/denominadores explicitados abaixo. Para confirmação+provável, incorreta, ambígua e versão relacionada o denominador é o conjunto verificável (N menos `not_verifiable`); para não verificável o denominador é a amostra completa da fonte.

| Fonte | N total | Verificáveis | Confirmada + provável (Wilson 95%) | Incorreta (Wilson 95%) | Ambígua (Wilson 95%) | Versão relacionada (Wilson 95%) | Não verificável / N (Wilson 95%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| GENIUS | 25 | 21 | 21/21 = 100,0% (84,5–100,0) | 0/21 = 0,0% (0,0–15,5) | 0/21 = 0,0% (0,0–15,5) | 0/21 = 0,0% (0,0–15,5) | 4/25 = 16,0% (6,4–34,7) |
| LETRAS | 100 | 65 | 42/65 = 64,6% (52,5–75,1) | 16/65 = 24,6% (15,8–36,3) | 6/65 = 9,2% (4,3–18,7) | 1/65 = 1,5% (0,3–8,2) | 35/100 = 35,0% (26,4–44,7) |
| LRCLIB | 25 | 17 | 16/17 = 94,1% (73,0–99,0) | 0/17 = 0,0% (0,0–18,4) | 0/17 = 0,0% (0,0–18,4) | 1/17 = 5,9% (1,0–27,0) | 8/25 = 32,0% (17,2–51,6) |
| LYRICS_OVH | 25 | 24 | 22/24 = 91,7% (74,2–97,7) | 0/24 = 0,0% (0,0–13,8) | 0/24 = 0,0% (0,0–13,8) | 2/24 = 8,3% (2,3–25,8) | 1/25 = 4,0% (0,7–19,5) |
| GOOGLE_MANUAL | 4 | 4 | 4/4 = 100,0% (51,0–100,0) | 0/4 = 0,0% (0,0–49,0) | 0/4 = 0,0% (0,0–49,0) | 0/4 = 0,0% (0,0–49,0) | 0/4 = 0,0% (0,0–49,0) |
| **Total observado** | **179** | **131** | **105/131 = 80,2% (72,5–86,1)** | **16/131 = 12,2% (7,7–18,9)** | **6/131 = 4,6% (2,1–9,6)** | **4/131 = 3,1% (1,2–7,6)** | **48/179 = 26,8% (20,9–33,7)** |

As categorias são exaustivas e mutuamente exclusivas: 86 confirmadas, 19 prováveis, 16 incorretas, 6 ambíguas, 4 versões relacionadas e 48 não verificáveis (=179). Entre verificáveis: 105 confirmadas+prováveis, 16 incorretas, 6 ambíguas e 4 versões relacionadas (=131). Taxas descrevem somente cada amostra estratificada observada; devido à alocação desproporcional por fonte e ao pequeno estrato GOOGLE_MANUAL, não se extrapolam ao corpus de 159.111 documentos.

Ao padronizar a regra, cinco resultados LETRAS — “Garion”, “Boo'd Up (Remix)”, “Carabiner”, “Mosaico Bailador” e “Foreign Linen” — e cinco LRCLIB — “I Got You”, “Kırmızı Paltolu Kız”, “Sinuun minä jään”, “Real Love” e “Déjenme sufrir” — antes chamados `probable` foram reclassificados como `not_verifiable`, pois os sites/catálogos confirmavam metadados, mas não havia fragmento lírico independente coincidente. “The Parachute Ending” foi classificada como `related_version` porque a comparação textual disponível era da versão remixada Vitalic, não da gravação exata listada. Nenhum desses ajustes converteu ausência de fonte em erro.

### Identidades incorretas observadas na amostra aleatória

As 16 classificações `incorrect` da amostra vieram todas do estrato LETRAS; nenhuma foi contada por mera colisão de hash. IDs (separados por ponto e vírgula): `6809c2bd-5dd8-594a-9188-0de6b1327c66`; `436071c0-8a37-5482-9a9c-e94182d8f9c0`; `24671d90-415c-5d72-b3f2-5686bed3ba31`; `06145de9-9352-5611-aacc-0750583ac8a2`; `9470b0bf-1118-5b78-9888-2636d07772dd`; `e3ba9c66-a1ce-5581-9be7-9f561834b2dd`; `08ef78b1-94fb-5cb0-90df-2078e18cc387`; `bbf75c5b-85ae-591d-bd43-926c74363e6f`; `46100ca4-1b0b-5d16-970e-a4af7ea70982`; `b0c825d5-3584-5bbc-8517-1c083f61d309`; `8a5f8224-2b90-56f7-b2cd-b11727b567fe`; `78546ddf-60d7-5399-be89-b9bc5679a02c`; `f9d2fe2a-26ab-52db-8469-53b0ddaddede`; `189b7903-8f9d-5297-a093-5f1a3993d1fe`; `e4780c0b-d404-5261-b97e-e6a802f684ff`; `f73ee3a6-24a9-5124-85f4-4210aa7ec777`. “Los sabanales” é um caso dirigido adicional do manifesto, fora das 179 comparações aleatórias; não entra nesta taxa.

### Itens não verificáveis

Nenhum ID abaixo é declarado incorreto: faltou fonte externa acessível que confirmasse conteúdo. GENIUS (4): `931444a7-9eb6-50e0-84f9-608f2be7d410`; `ce0dbd3c-d34d-563e-be03-c2515df82763`; `595af992-4571-5d11-b9d7-9a9ee329d3aa`; `185cd502-63e9-507d-a900-3314b75cd781`.

LETRAS (35): `bf9f3103-1a51-5257-bae4-ae96c5dc6adb`; `4a3a9aa4-5f3a-5985-b3ec-f8eb9f1bf5f9`; `b2ba3365-51b0-5315-a349-5de6433a0330`; `4245c2db-0b8d-5b46-afba-0df0cc685531`; `ed1b255d-2700-50cc-a940-261e3bb003ff`; `35c33257-4988-5cf4-ac4b-51d1c6ad1993`; `ef55f02f-f43d-5b25-8abd-a309f64498bd`; `975b887b-bd35-5505-82e4-f79a4c340e4d`; `cf976865-7169-5f2d-8d4c-db95ffc0da40`; `75bc182c-47a9-5cc2-8abd-775caa499270`; `94ec527c-4c2c-55ab-ac64-24e8eacb7796`; `3eee2a69-07c6-575d-977d-ebf9e48602a2`; `e4f2248a-e422-561d-b8ce-0e4b2ccd08f1`; `7659258b-4c7e-53ea-a974-18fbde449b4e`; `939b65be-fdc3-5e4e-9e71-366952271b08`; `b33c3716-84b3-5a31-82f6-71c6b5121f4d`; `0f5fb32c-b8ad-5b20-b9bc-bce1b9411e82`; `734df6c1-0baa-5308-bfa9-1a688dbc43e7`; `f78c7604-001b-5f97-b21f-3cd7b050ee15`; `0fddcfbf-1684-546f-85c4-c4e789b5f582`; `7bb3ad18-6c98-5fd7-8fd7-dc89242dd8b5`; `326c244c-15f1-562b-8a2f-a258392f72a0`; `a6cbaf17-4ec0-5208-b4a4-2ec50379c53d`; `4bf704be-f45b-51b9-8f24-f5414269636c`; `9431814b-54f3-5618-8992-df7d1d866a0a`; `7a382d0a-4238-5bb5-86b8-322700f8aaa5`; `4a31fe99-aa60-596b-a962-646e6916ffd2`; `1d5ea2b6-30d8-57c7-a6a4-9e92692b9c1c`; `059a4985-de7e-551e-be9d-3656f6e929aa`; `c36d4db5-de7d-5324-b94d-41bd2b162c42`; `6cfb093d-4023-5b6d-98cb-7858d08a8889`; `34b2069f-ed29-5e55-8b40-441db8c0652c`; `7ae605b6-2f69-515d-ad40-689077f1c4b0`; `d30ad4b0-9311-5411-8aea-bba4812b144a`; `ad7423da-4d30-5290-8468-31b01e00b172`.

LRCLIB (8): `7ef2f025-cbad-5f32-b461-d821caef4c7e`; `a9c919a8-5595-5e01-8c47-7b4457f32694`; `8054f84a-bcb7-54cb-a7b0-459e0667420b`; `7fa9fc65-c817-505a-aaf9-d6d81ab03600`; `bdf5bdd6-2e7f-5c32-81a4-781a8ddfb7ee`; `792301c8-fcdc-567f-9fc9-332e5efdf652`; `b65a5e98-85aa-5371-aabe-e91e3747b4e4`; `b0b9e95d-36e1-595e-aca2-3cef0bbd6ff5`. LYRICS_OVH (1): `d883f21c-3628-54f9-bda6-cda03f6cb6ae`. GOOGLE_MANUAL: nenhum.

### Limite de inferência

Esta auditoria independente já não tem zero comparações, mas ainda é uma amostra pequena, com não verificabilidade relevante e resultados dependentes das fontes líricas públicas disponíveis. Ela responde à pergunta apenas para os registros amostrados e não valida automaticamente as outras 158.932 identidades do corpus. A próxima ampliação requer plano/amostra apropriados e não deve reutilizar chamadas pagas Gemini como verificador de identidade.
