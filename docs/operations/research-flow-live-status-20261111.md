# Estado verificável do fluxo — 11/11/2026

Este retrato acompanha o protocolo em
[`research-flow-20261110.md`](research-flow-20261110.md) e a avaliação de fontes
em [`research-source-availability-20261111.md`](research-source-availability-20261111.md).
As métricas observadas, a integridade técnica e a aprovação científica são
relatadas separadamente.

## Estado dos portões

| Etapa | Estado auditado | Evidência atual |
|---|---|---|
| G1 — rankings | **Reprovado, 0% aprovado** | 90.600/277.650 posições observadas na seleção v4 (32,63% bruto); nenhuma aprovação científica |
| G2 — letras | Pendente, 0 aprovadas | PostgreSQL tem texto para 27.607/30.927 candidatos (89,27%); identidade, completude e direitos não aprovados |
| G3 — preparação | Pendente | 0 itens elegíveis; escores e presença ficam nulos |
| G4 — homologação | Pendente | Sem split humano validado, alpha/kappa/macro-F1 ou referência independente |
| G5 — resultado | Pendente | Nenhum resultado científico importado |

Não se calcula média entre disponibilidade, implementação e portões. O
percentual de disponibilidade de G1 tampouco passa o gate: faltam 131.520
posições observadas para chegar a 80% bruto na v4, além da adjudicação científica
das posições existentes. A aprovação exige 80% global **e em cada país/ano**;
72 células não têm cota definida e seguem no denominador como aplicabilidade
pendente.

## Rankings

Seleção auditada: `data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002/`.

| Medida | Resultado |
|---|---:|
| Posições previstas | 277.650 |
| Participações observadas | 90.600 (32,63%) |
| Definitivas / provisórias | 73.580 / 16.460 |
| Células com ao menos um item | 615 / 2.250 |
| Células com pelo menos 80% da cota conhecida observada | 615 / 2.178 (28,24%) |
| Células com calendário completo após validação de profundidade | 425 / 2.250 (18,89%) |
| Participações provisórias / completas | 16.460 / 74.140 |
| Conflitos / pares empatados pendentes / itens sem metadados | 2.261 / 6 / 195 |
| Aprovadas cientificamente em G1 | 0 / 277.650 |

Cada período precisa atingir a profundidade Top-K declarada: 100 faixas únicas
para YouTube e 200 para Spotify; duplicatas não satisfazem profundidade. A
reconciliação semântica das células validou 2.250 linhas da v3 e 2.250 da v4,
sem falhas. O relatório antigo de 126 divergências era um falso positivo: as
posições provisórias são subconjunto das posições selecionadas, não um conjunto
adicional. O suplemento v4 adiciona 560 participações marginais verificadas
(Israel 2019/2020/2021 e Rússia 2021), sem colisões com a seleção anterior.
Esses registros elevam a cobertura bruta de 90.040 para 90.600; não comprovam
representatividade nem aprovação da fonte para toda a pesquisa. O manifesto
documenta os conflitos de fonte, limites de licença/proveniência, calendário e
metadados ausentes. Uma verificação final encontrou que o relatório
`source_coverage.json` da v4-final-0001 continha 48 nomes de campos como strings,
devido a uma concatenação incorreta, e omitia as duas linhas de cobertura de
2021. Essa versão foi preservada como histórico e substituída pela
v4-final-0002; a correção adicionou validação de schema e regenerou o artefato.
O snapshot corrigido tem 997 linhas objeto, sem strings ou campos obrigatórios
ausentes. Comparação hash a hash confirma que só `source_coverage.json` mudou;
as 90.600 participações, os rankings e as células país/ano são idênticos.

A auditoria congelada atual está em
[`audit-v4-final-0003`](../../data/runtime/research-flow-20261111/audit-v4-final-0003/)
e o progresso em
[`progress-v4-final-0003`](../../data/runtime/research-flow-20261111/progress-v4-final-0003/).
`research verify` confirmou a integridade; `research require --gate G1` retorna
código 1 porque o portão continua reprovado. A seleção v4 não foi aplicada ao
PostgreSQL nem alterou seleções legadas.

## Letras e coletores

O banco configurado permanece disponível em `127.0.0.1:55433`, PostgreSQL
16.15, base `chart_observatory_recovery_20261007`. A leitura `READ ONLY` de
17:49 UTC vinculou a seleção original ao run atual
`2b7301232af15ac3ac5acf64c1226d78e9b1f5feb41875e16f95c501d28c3a77`:
30.927 candidatos, 27.607 com texto, 3.320 sem texto e zero prontos para
classificação. Não houve escrita de produção. A auditoria original reexecutada
com o validador de schema atual está em
[`audit-original-v5-final-0001`](../../data/runtime/research-flow-20261111/audit-original-v5-final-0001/);
seu inventário PostgreSQL está em
[`progress-live-original-v12`](../../data/runtime/research-flow-20261111/progress-live-original-v12/).

O supervisor de recuperação retomado está ativo na comparação web da seleção
original. No checkpoint de 17:51 UTC, havia examinado 3.611/30.927 candidatos
(11,68%), com 1.336 edições ambíguas, 2.224 sem texto web correspondente e um
metadado não resolvido. A comparação gerou 46 propostas (25 publicadas na fila
de revisão), 46 correspondências de texto no mesmo provedor e quatro textos
divergentes. Propostas não equivalem a aprovação. Aprovações e prontidão para
classificação seguem em zero, sem chamada paga. A aquisição terminou com 424 candidatos pendentes de
validação, 3.696 sem resultado verificado e 512 reutilizados pendentes. O
coletor só adiciona resultados a staging; não aprova identidade, completude ou
direitos.

A retomada do coletor oficial YouTube reconsultou 100 rotas e concluiu em estado
pendente de revisão. O checkpoint aumentou de 498 para 539 gráficos semanais
(53.900 linhas preservadas), mas continuou com 59 rotas históricas não
resolvidas. O relatório congelado
[`report-0003`](../../data/runtime/worldwide-chart-recovery-20261111-r2/report-0003/)
encontrou uma célula com calendário completo até o corte, KE/2026; nela ainda há
cinco identidades de exibição ausentes, 268 conflitos de metadados e três
semanas ambíguas. O resultado acrescentou zero posições anuais. Não transferir
resultados da seleção original à v3 sem vínculo exato por identidade e hash.

Auditoria integral de qualidade para o run
`5934140101c143da9e2059264ceb56571873395fd1d19531afc08095522023d3`:

- 30.927 candidatos; 27.607 com corpo no PostgreSQL; 0 verificados como
  completos e 0 prontos para classificação.
- Estados: 26.586 adquiridos sem verificação, 710 pendentes de adjudicação,
  3.320 indisponíveis, 250 conflitos de identidade e 61 suspeitos de truncamento.
- Flags incluem 702 casos sem evidência integral do performer, 652 escopos de
  página sem verificação e 585 sem evidência de identidade da fonte. São sinais
  de revisão, não taxas confirmadas de erro.
- 27.120 hashes do texto do banco coincidem com o store local; 397 não têm
  versão local, 90 diferem em hash e 11 são locais sem correspondência exata.
  Dos 90, 85 tinham hash legado igual ao banco antes de substituição no store.
- Nas 487 divergências, 110 respostas cruas reproduzem bytes exatamente e estão
  em quarentena técnica não canônica; outras 67 reproduzem bytes, mas mantêm
  flags de metadados; 310 não têm evidência crua suficiente. Nada foi promovido.

Os detalhes e filas sem letras estão em
[`audit-0002`](../../data/runtime/lyrics-quality-20261111/audit-0002/),
[`db-local-mismatch-0005`](../../data/runtime/lyrics-quality-20261111/db-local-mismatch-0005/)
e [`reconciliation-quarantine-0001`](../../data/runtime/lyrics-quality-20261111/reconciliation-quarantine-0001/).
O ciclo integral mais recente de triagem de qualidade, no run corrente
`2b7301232af15ac3ac5acf64c1226d78e9b1f5feb41875e16f95c501d28c3a77`, examinou
30.927 candidatos: 27.122 hashes iguais ao store local, zero textos verificados
como completos e zero prontos para classificação. O relatório declara que os
estados e flags são triagem, não taxas confirmadas de erro. A comparação
independente entre esse run e `5934140101c143da9e2059264ceb56571873395fd1d19531afc08095522023d3`
provou igualdade de 30.927 IDs, memberships, hashes e corpos byte a byte; 20
rótulos de fonte diferem somente em itens sem texto e um campo auxiliar `audit`
difere em uma linha cujo ID, payload, fonte, hash e corpo são iguais. Nenhuma
dessas diferenças afeta a reprodução de texto.

O pass source-chain do run `593414...` está concluído e verificou 30.927/30.927
registros. Reproduziu 26.585 respostas byte a byte e uma somente após
normalização; 129 outras coincidências exatas aguardam metadados, 892 não têm
evidência bruta resolvida e 3.320 estão indisponíveis. O ledger passou a
integridade (`PRAGMA integrity_check=ok`), com fila/ledger/status e hashes
conferidos. A correspondência de bytes comprova fidelidade à resposta preservada,
não identidade musical, completude, direitos ou aprovação científica. Foram
validados como completos, aprovados por identidade e prontos para classificação:
zero.

## Contrato de classificação e Vertex AI

O controlador v4 e `research-evidence-v4` mantêm evidências antigas sem conversão
silenciosa. G2 exige identidade, integridade, completude, truncamento,
contaminação, idioma, competência declarada, evidência hashada de competência e
autorização de armazenamento. Direitos separam armazenamento, processamento e
publicação. Qualquer uso futuro do Vertex também exige concessão explícita para o
provedor, modelo, versão resolvida, região e retenção exatos. G4 exige manifesto
de split de desenvolvimento/validação hashado e disjunto por grupo de
equivalência, texto normalizado, gravação e obra, ligado às requisições e à
cobertura exata da validação. A tabela só deriva `topic.present` de `score >= 2`
após G4 aprovado e resposta classificada; antes disso, escores e presença são
nulos.

Não houve envio, upload, canário ou inferência Vertex. A [Política oficial de
Desenvolvedores do Spotify](https://developer.spotify.com/policy) restringe a
análise de Spotify Content/Service e seu uso ou ingestão em modelos de IA/ML;
os [Termos de Desenvolvedor](https://developer.spotify.com/terms) incorporam
essas condições. A incidência sobre cada arquivo histórico e sobre cada campo
do payload futuro requer revisão específica de direitos. A configuração do
projeto/modelo também deve ser revisada para os dados exatos do payload. A
[documentação Google Cloud de ZDR](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention)
descreve logging de prompts para abuso e configuração/aprovação específicas.
Direitos sobre letras, retenção, modelo, região, custos e permissões continuam
bloqueadores explícitos.

## Verificações de software e reprodução

- `pytest tests/unit -q --basetemp=data/runtime/pytest-basetemp-20261111-delivery-v9`:
  **1.178 passaram**, 2 avisos de depreciação. A suíte focada nos gates v4
  passou 166 testes; oito testes validam o schema de cobertura e um confirma que
  o auditor rejeita um arquivo malformado mesmo com hash correto. Ruff passou
  nos arquivos alterados. O JUnit está em
  `data/runtime/research-flow-20261111/pytest-unit-v4-final-0003.xml`.
- A primeira tentativa usou o diretório temporário padrão em `C:` e falhou em
  19 testes porque campanhas/arquivos batch exigem o disco `D:`. O resultado
  está preservado em `pytest-final-delivery-v3.xml`; a repetição correta no
  disco do projeto passou.
- `tests/integration/research`: **3 passaram** usando somente o cluster isolado
  `research-flow-test_9842267ee48e47b7a6c6ecf06d487f86`, porta 60687; o cluster
  foi parado ao final. JUnit:
  `data/runtime/research-flow-20261111/pytest-integration-v4.xml`.
- A checagem ao PostgreSQL de pesquisa e as auditorias usaram transações
  somente leitura; nenhuma chamada Vertex paga ou escrita de produção ocorreu.

O pacote local versionado foi montado em `data/runtime/research-flow-20261111/packages/`.
Sua verificação ZIP passou, os arquivos conferem com o manifesto vinculado à
seleção v4 e nenhuma letra bruta está incluída. O estado correto do pacote é
`blocked_preparation`, pois G1–G5 não foram aprovados.

Para repetir o gate v4:

```powershell
.venv/Scripts/chart-observatory.exe research verify --audit data/runtime/research-flow-20261111/audit-v4-final-0003
.venv/Scripts/chart-observatory.exe research require --audit data/runtime/research-flow-20261111/audit-v4-final-0003 --gate G1
```

O pacote local de preparação permanece bloqueado enquanto G1–G5 e os termos de
processamento não estiverem aprovados. A limitação de fontes e a recuperação
necessária estão detalhadas em
[`research-source-availability-20261111.md`](research-source-availability-20261111.md).
