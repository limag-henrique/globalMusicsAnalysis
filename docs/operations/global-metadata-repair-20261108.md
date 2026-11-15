# Correção dos metadados importados — 08/11/2026

Foram corrigidos os **30 vínculos adicionais sem título/artista**, referentes a
**19 IDs Spotify** do Paquistão. Os **5.910 vínculos adicionais agora têm ambos
os campos preenchidos**, nos arquivos e na nova versão do PostgreSQL.

O Spotify público respondia HTTP 200, mas entregava nomes vazios e a indicação
`COUNTRY_RESTRICTED`. A coleta anterior tratava corretamente essa resposta como
indisponível, porém o processamento não procurava uma evidência histórica
alternativa. Não houve tentativa de contornar a restrição territorial.

Os nomes foram recuperados das páginas históricas do Kworb cujo caminho contém
o ID exato da faixa. Não houve busca por similaridade, troca de ID ou seleção de
outra música. Cada correção registra URL solicitada, URL final, status HTTP,
data, arquivo de evidência, hash SHA-256 e os nomes originais ausentes. O HTML
é reprocessado na aplicação da correção; nomes fornecidos em um mapa sem prova
não são aceitos. A origem permanece identificada como arquivo histórico, sem
atribuir a resposta ao Spotify atual.

Também foi corrigido um defeito no parser que podia incluir um link de artista
de uma seção posterior ao cabeçalho. Um teste com recomendações fora do
cabeçalho reproduziu a falha antes da correção. O parser agora encerra a coleta
de título e artistas na primeira seção de conteúdo posterior ao cabeçalho e
confere a concordância com o título da página.

As correções são atômicas na validação dos metadados: URL de outro ID, hash
alterado, redirecionamento inesperado, nomes conflitantes ou página sem título
impedem a aplicação. Nomes já completos não são sobrescritos. O diagnóstico
`metadata_missing` dos 30 vínculos foi substituído por
`native_id_pending_recording_review`, mantendo o diagnóstico original na prova.
Isso resolve a ausência nominal; não certifica a gravação, a letra ou a
elegibilidade para classificação.

## Verificação do resultado efetivo

- 92.000 vínculos mantidos, com os mesmos países, anos, posições, cotas, IDs e
  métricas da versão anterior.
- 30 vínculos alterados exclusivamente para corrigir os metadados e registrar a
  transição do diagnóstico de ausência para revisão de identidade pendente.
- Todos os outros vínculos e os 86.090 registros da base anterior preservados.
- 5.910 vínculos adicionais com título e artista completos; nenhum adicional
  permanece com esses campos ausentes.
- Comparação entre a versão PostgreSQL anterior e a corrigida, verificação dos
  arquivos exportados, provas históricas e idempotência da importação.
- 148 testes de ingestão/fontes aprovados; Ruff e Mypy no módulo novo.
- Nenhuma chamada paga, aquisição de letras ou classificação iniciada.

Código: `src/chart_observatory/ingestion/archive_metadata.py`,
`scripts/repair_global_annual_metadata.py` e
`scripts/verify_global_metadata_repair.py`. O construtor
`scripts/incorporate_global_annual.py` reaplica as provas ao reconstruir o
conjunto, sem perder a correção.

Evidências e auditoria estão em:

- `data/raw/metadata_resolution/global-20261108/kworb/`;
- `data/derived/annual_revision/global-2018-2026-20261108/archive-display-metadata.json`;
- `data/derived/annual_revision/global-2018-2026-20261108/metadata-repair-20261108/verification.json`.

## Pendência antiga identificada separadamente

Há **um vínculo anterior do Vietnã**, de 2018, posição 133, ID Spotify
`2me5SocGcxPzFwPe03my19`, que continua sem título e artista completos. Ele não
faz parte dos 5.910 adicionais. A fonte atual tem o título vazio; os arquivos
locais consultados não recuperaram seu nome. A página histórica do Kworb e
cópias arquivadas do Spotify consultadas também têm o título vazio. A busca
MusicBrainz pelo URL exato não retornou uma associação.

Não se inferiu um título a partir do artista ou da data de lançamento. A linha
original foi preservada e a pendência consta da auditoria, com
`overall_metadata_complete=false`. Assim, **os erros de ausência nominal dos
adicionais foram corrigidos; a completude nominal de todo o acervo ainda não
pode ser declarada**. As 185.650 posições históricas ainda sem fonte suficiente
e os 224 conflitos de métricas continuam sendo pendências distintas desta
correção de nomes.
