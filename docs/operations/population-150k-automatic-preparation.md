# Seleção global de até 150 mil posições e preparação automática

Por instrução do usuário em 16/11/2026, o teto de 150.000 é compartilhado entre
todos os países, anos e plataformas. Não é um teto por país ou por ano.
Também foi autorizada explicitamente a preparação mediante aprovação automática
rigorosa, mantendo a aprovação científica separada.

## Alocação executada

A seleção ativa é
`data/derived/annual_revision/population-total-150k-2018-2026-20261116-v10-archives`.
Os dados e cotas anteriores permanecem preservados para comparação e recuperação.

- Janela: 2018–2026, nove anos. O corte parcial de 2026 permanece explícito.
- Orçamento de posições: exatamente 150.000, inclusive posições ainda sem fonte.
- 2018–2023: 16.667 posições em cada ano; 2024–2026: 16.666 em cada ano.
- Uma fonte primária por país/ano; plataformas e espelhos não multiplicam cotas.
- Mínimo de uma posição por país/ano com população disponível, máximo de 500.
- Países/territórios sem população harmonizada permanecem explícitos, sem valor
  populacional inventado. Sua eventual inclusão exige redistribuição dentro do teto.
- As mesmas gravações em diferentes países/anos são classificadas uma única vez.
  Portanto, o número de músicas distintas não pode ultrapassar as 150 mil posições.

O peso de esforço é:

`sqrt(população de referência) × (1 + 0,10 × relevância operacional + 0,10 × necessidade)`.

A raiz quadrada da população segue a abordagem demográfica já usada no projeto:
favorece países populosos sem eliminar a cobertura dos menores. Relevância é
operacionalizada pela quantidade de plataformas presentes na seleção histórica,
limitada a duas e normalizada para [0,1]; não mede valor cultural de um país.
Necessidade é a fração de posições ausentes na cota anterior do país/ano.
Esses ajustes são decisões de alocação, não estimativas de representatividade.

A população de referência é a série 2024 já preservada no projeto, com fontes
Banco Mundial, complementos ONU e exceções documentadas em
`research/global_inventory/expansion_20261108/population_evidence.json`.
Não se apresenta essa referência fixa como população observada em cada ano.
O arredondamento usa maiores restos, limites e desempate determinístico.

Resultados da alocação v10: 69.032 posições identificadas, 27.165 gravações
distintas conhecidas e 80.968 posições sem ranking disponível. A matriz cobre
250 países/territórios e nove anos; há registros em 77 países e 623 das 2.250
células país/ano. As extensões recuperaram 4.080 posições contíguas de arquivos
históricos, somente quando todos os IDs nativos e métricas do prefixo existente
coincidiram. A seleção mantém o corte anual registrado em 15/10/2026; os arquivos
adicionais estão identificados e hashados no manifesto. Isto não equivale a
reconstruir hoje todas as séries anuais. O arquivo de seleção não alega que
existam 150 mil letras ou posições de ranking disponíveis.

Arquivos `allocation.csv` e `allocation.jsonl`: cotas de cada país/ano, população,
fonte, ajustes e cota anterior. `combined.jsonl`: músicas conhecidas dentro das
novas posições. `country_years.jsonl`: denominadores e lacunas explícitos.
`manifest.json`: hashes e política. Nenhuma lacuna é preenchida por reservas de
posição inferior por falta de letra.

## Verificação e importação

`scripts/verify_prioritized_corpus.py` reavalia a coorte da seleção ativa, sem
amostragem, com snapshot dos metadados nativos e leitura das fontes preservadas. Verifica
hash do texto, reextração da fonte, créditos, qualificadores de edição, duração
quando disponível, indícios de trecho, contaminação, texto curto, início em seção
intermediária, refrão isolado e conflitos entre gravações/textos/IDs de provedores.
Falhas por registro são contabilizadas.

`scripts/import_prioritized_missing_lyrics.py` filtra as gravações sem texto pela
seleção ativa e pelos lotes imutáveis de staging. A ordem usa cota total do país decrescente, população
como desempate, posição crescente e ano crescente. Metadados nativos compatíveis
são aplicados antes da busca para ajudar a discriminar versões por duração.
Todas as posições de uma gravação são preservadas; uma aquisição serve a todos
os vínculos válidos. O worker não altera os processos ou saídas do AntiGravity.

## Preparação autorizada para Vertex

A política `automated-native-full-source-v1` exige aprovação de identidade,
completude e integridade da fonte, evidência nativa presente, texto com hash
verificado e ausência de alertas de qualidade, quarentena e conflitos no corpus.
Uma transcrição de áudio não é alegada como comprovada por esses testes.

A auditoria completa v10 com os lotes e a recuperação complementar identificou
20.632 músicas aptas à preparação técnica, com 56.481 vínculos país/ano. A preparação já foi materializada em
`data/runtime/automatic-vertex-population-150k-20261116-03-v10-acquisition-final`.
O pacote contém jobs privados por referência, contrato compartilhado, tabela de
posições prontas por país/ano e `vertex-requests.jsonl` com 20.632 requests
completos (852.960.847 bytes). O JSONL materializa letras nas requests; o arquivo
`jobs.private.jsonl` mantém referências sem copiar letras. Não houve upload nem
inferência do Vertex.

A preparação usa ledger cumulativo, deduplicado por gravação, limitado a 150 mil,
contando conservadoramente também reservas do preparo legado. Mudanças de texto
ou perfil não substituem silenciosamente jobs anteriores. Antes de cobrança,
a versão efetiva do modelo e o orçamento monetário ainda devem ser conferidos.
O modelo configurado não é apresentado como uma revisão remota já resolvida.

Esta política técnica não fabrica revisão humana, não modifica aprovações
históricas e não representa aprovação dos gates científicos G1–G5.

## Estado de execução em 16/11/2026

- A auditoria integral v10, após incorporar os lotes e o worker de recuperação,
  terminou com 27.165 músicas: 25.143 com texto, 2.022 sem texto, 20.632 aptas à
  preparação técnica e zero erros de validador. As 1.231 letras encontradas pelo
  worker foram reavaliadas; 150 músicas adicionais passaram todos os critérios
  automáticos para preparação. Aprovação científica continua separada. Foram
  sinalizados 197 possíveis inícios em seção intermediária, 86 letras dominadas
  por refrão repetido e 40 duplicações de metade; as categorias se sobrepõem e
  nenhuma dessas sinalizações passou a validação integral do provedor.
- O lote de recuperação terminou com 1.231 resultados de texto candidatos e
  2.022 músicas sem texto verificável. Os candidatos ainda não aprovados ficam
  fora da classificação Vertex.
- A atualização corrente de charts tentou 498 país/fonte (Spotify e YouTube,
  249 países/territórios): 89 completas, 33 parciais, 86 falhas de consulta e
  290 fontes indisponíveis. Os charts atuais datam de 14/11 (Spotify) e 12/11
  (YouTube). Essa atualização não reconstitui séries anuais históricas nem
  altera a seleção anual v10.
- O material de classificação ainda precisa da resolução explícita da revisão
  do modelo antes de qualquer despacho. Chamadas pagas, uploads e inferências:
  zero.
