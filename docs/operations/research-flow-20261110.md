# Fluxo verificável da pesquisa — versão 4, 11/11/2026

O comando `research` integra os cinco portões com a seleção mundial congelada,
revisões de letras, contrato dos 26 tópicos e validação independente. Todos os
comandos desta entrega são locais. Não fazem upload, inferência ou reserva de
orçamento. O contrato novo não é convertido em snapshots do schema legado.

## Compatibilidade do esquema de evidências

O controlador e o formulário de evidências usam agora
`worldwide-research-flow-v4` e `schema_version="research-evidence-v4"`.
Evidências antigas sem essa versão, sem o checklist G2 novo, sem o manifesto
hashado de split para G4 ou sem o esquema explícito de direitos não são convertidas
nem aceitas como equivalentes. Preserve os artefatos e as auditorias anteriores;
para avaliação nova, crie evidência v4 e uma auditoria em diretório novo. Essa
migração exige novas declarações e evidências dos revisores, não uma edição
retroativa dos arquivos anteriores.

## Executar e bloquear o avanço

Na raiz do projeto, no PowerShell:

```powershell
.venv/Scripts/chart-observatory.exe research audit --selection data/derived/annual_revision/global-2018-2026-20261108 --output data/runtime/research-flow-20261110/audit-nova-versao --actor Codex
.venv/Scripts/chart-observatory.exe research verify --audit data/runtime/research-flow-20261110/audit-nova-versao
.venv/Scripts/chart-observatory.exe research require --audit data/runtime/research-flow-20261110/audit-nova-versao --gate G1
if ($LASTEXITCODE -ne 0) { throw 'G1 não aprovado: tratar a fila de recuperação antes de avançar.' }
```

`audit` retorna sucesso técnico quando consegue produzir o diagnóstico, inclusive
quando a pesquisa está reprovada. `verify` comprova integridade, sem conceder
aprovação científica. **Automação deve executar `require`**: ele retorna código
diferente de zero se o portão não estiver aprovado ou se dados/aprovações tiverem
mudado. `prepare` aplica obrigatoriamente essa mesma verificação para G2.

Nunca reutilizar um diretório de saída. Cada execução gera nova versão imutável;
arquivos de uma execução anterior permanecem preservados. Mudanças de fonte,
seleção, código, rubrica ou evidência exigem nova auditoria.

O arquivo `research-stage-history.sqlite`, no diretório pai das auditorias,
mantém eventos append-only de `pendente` → `em_execucao` → resultado final
por portão. O relatório identifica a execução e o ledger. Triggers impedem
UPDATE/DELETE do histórico; a conclusão dos cinco portões é transacional.
Falhas técnicas preservam a tentativa e apenas o tipo do erro, sem credenciais.

## Saídas e denominadores

| Arquivo | Uso |
| --- | --- |
| `report.json` | G1–G5, responsável, versões, universo, numeradores, denominadores, razões e hashes |
| `gates.csv` | G1/G2/G3/G5 em todas as células, inclusive reprovadas e pendentes |
| `items.jsonl` | Posição e candidato exatos, hash da linha e resultado de cada verificação |
| `ranking-recovery-queue.jsonl` | Primeiro resolver aplicabilidade das cotas; depois células vazias e déficits |
| `lyric-review-queue.jsonl` | Candidatos sem aprovação canônica comprovada |
| `preparatory-table.csv` | Metadados e 26 colunas; escores nulos antes de G4 e de resultado aceito |
| `local-statuses.json` | Fotografias históricas separadas por run; não são estado certificado do PostgreSQL |
| `evidence-schema.json` / `evidence-template.json` | Contrato e formulário vazio de evidências, sem aprovações fabricadas |
| `manifest.json` | Hashes de entradas, implementação e saídas para reexecução independente |
| `environment.json` | Python, sistema e versões das dependências; pyproject/lock também vinculados por hash |

G1 usa as posições previstas. G2 usa posições aprovadas em G1. G3 usa posições
aprovadas em G2. G5 usa posições preparadas e depende de G4. O mínimo é 80%
global **e em cada célula**. Zero/denominador indefinido não aprova. Os oito
territórios sem cota continuam explícitos. A presença de 80% de textos brutos
não aprova G2. Reutilização de uma edição reduz chamadas, não os denominadores
por posição. A cobertura final também é mostrada sobre o universo original.

## Evidências para G1

Preencher um arquivo conforme `evidence-schema.json` e passar `--evidence` ao
comando `audit`. Cada aprovação de posição exige hash da linha congelada,
revisão datada, definição da fonte, fontes preservadas e linha reconstruída.
Todos os caminhos de evidência devem resolver dentro do projeto e seus bytes
devem corresponder ao SHA-256 informado.

A definição de fonte deve conter `country_code`, `platform`, `provider`,
`frequency` (`daily` ou `weekly`), `metric`, `period_start`, `period_end`, `depth`,
`source_url`, `retrieved_at`, `ranking_kind`, `quota` e `observation_artifact`
(`path`/`sha256`). Também deve registrar decisões explícitas de
`calendar_verified`, `depth_verified`, `identity_verified` e
`boundary_tie_resolved`. A projeção de observações precisa constar de
`source_files`, junto das fontes brutas que fundamentam a extração revisada.
O programa reconta calendário, profundidade e somas: as declarações não
substituem a reconstrução.

As observações normalizadas em JSONL têm `country_code`, `platform`, `provider`,
`period_start`, `period_end`, `candidate_id`, `position`, `metric_value`, `title`
e `artist`. Cada linha representa uma posição em um período nativo. Preservar
a relação dessa projeção com os arquivos brutos e o método de extração.

```powershell
.venv/Scripts/chart-observatory.exe research reconstruct --help
```

O reconstrutor usa decimais exatos, elimina duplicações idênticas sem somá-las,
rejeita conflitos e exige todas as posições da profundidade declarada em todos
os períodos. Para semanais, a agenda de encerramentos precisa ser fornecida
explicitamente e comprovada pela fonte; ano é atribuído pelo fim da semana.
2026 termina em 15/10. Empate no limite da cota bloqueia. Empates internos são
reportados como posições compartilhadas; o controlador conserva essas linhas
pendentes até haver evidência de ordenação, sem inventar posição exata.

O adaptador implementado certifica a **reconstrução de somas observadas nos
charts**. Rankings anuais oficialmente publicados permanecem bloqueados por
`published_annual_adapter_review_required` até existir um adaptador específico
revisado. Não tratar uma fotografia diária como ranking anual, nem as somas
censuradas de Top-K como total de consumo da plataforma.

Completar períodos requer reconstruir a seleção inteira numa nova versão. O
assembler legado preserva mercados congelados; não anexar posições novas à
lista histórica. O controlador rejeita múltiplas fontes principais por célula.

## Evidências para G2 e revisão humana

Cada `LyricApproval` identifica candidato, documento canônico e hash textual.
O documento precisa existir **no PostgreSQL atual**, passar pelo gate vigente e
registrar `metadata_json.research_candidate_ids` com o vínculo exato. A leitura
usa transação `REPEATABLE READ READ ONLY`; banco indisponível impede aprovação.
O staging de aquisição permanece separado e sem promoção automática.

São obrigatórios dois pareceres de responsáveis distintos, vinculados ao UUID
e hash do documento, com método `official_transcription` ou
`human_audio_verification`, data e artefato preservado. Cada parecer deve
registrar `identity_verified`, `completeness_verified`, `truncation_checked`
e `contamination_checked`, `language_code` igual ao idioma do documento,
`language_competence` e um `competence_evidence` com hash. Completude inclui o
confronto de toda a letra, incluindo repetições e seções finais, com a edição
exata; truncamento e mistura com outra faixa/versão precisam ser verificados
explicitamente. Divergências exigem terceiro adjudicador distinto e posterior
aos pareceres, com o mesmo checklist completo. `canonical_evidence`
precisa reproduzir o hash da evidência da adjudicação canônica. A evidência
`research-rights-v1` vincula UUID/hash textual e fonte HTTPS, com base e artefato
hashado separados para armazenamento, processamento e publicação. G2 exige
autorização de armazenamento; não presume autorização para processamento externo
nem publicação. Para despacho ao Vertex, são obrigatórias autorização de
processamento e concessão positiva específica para `provider=vertex_ai`, modelo,
versão resolvida, região e retenção em dias. Ausência, falso ou divergência
bloqueia o despacho.

O software verifica vínculos e bytes. Ele não autentica as identidades declaradas
dos avaliadores, não realiza escuta humana e não concede direitos autorais.
Uma declaração falsa não se transforma em verdade por passar no schema.

## G3, homologação e resultados futuros

O bundle de calibração, com os 26 tópicos e exemplos sintéticos 0–3, está em
`data/runtime/research-flow-20261110/contract-bundle`. É proposta de instrumento,
sem aceitação científica. A aceitação da rubrica é datada e vinculada ao hash
do conteúdo. Homologação empírica do classificador permanece separada.

Depois de G2, `research prepare` exige rubrica aceita e perfil resolvido, revalida
o estado canônico, produz requisições privadas por edição textual e mapeia todos
os vínculos país/ano. Ausência de idioma gera déficit. Segmentação preserva
palavras, repetições e quebras; o ID da requisição vincula texto, idioma,
rubrica, prompt, schema, pré-processamento, modelo e configuração completos.

Para G3, registrar `Preparation` com o arquivo da requisição individual, rubrica
e revisão. Para G4, fornecer JSONL em `validation` com identidades, split,
idioma e os escores de referência/predição/avaliadores descritos em
`research_validation.py`, mais `validation_split` apontando para um manifesto
privado hashado produzido em `prepare_blind_packets`. O manifesto registra IDs
de edição, hashes textual e normalizado, grupo de equivalência, gravação/obra
quando conhecidas, idioma, partição, algoritmo, seed, cotas e déficits. O
controlador exige cobertura exata das edições no conjunto de validação e
bloqueia grupos, textos, gravações ou obras declarados em ambas as partições.
O manifesto e o JSONL de validação devem ser artefatos separados, preservados e
incluídos em `ResearchEvidence` como referências `Artifact` com SHA-256. Não é
permitido omitir o split ou selecionar apenas uma parte das edições após
congelá-lo. Além deles, o controlador exige:

- `response_artifact`: resposta preservada no contrato novo; os escores precisam
  coincidir exatamente com `prediction` e com a requisição aprovada.
- `human_a_artifact`, `human_b_artifact`, `reference_artifact`: fichas contendo
  `request_id`, `text_sha256`, `scores`, `actor`; os responsáveis correspondem a
  `reviewer_a`, `reviewer_b`, `adjudicator` na observação.
- Todas as observações ligadas a requisições elegíveis do mesmo perfil/rubrica.
  Todos os idiomas preparados precisam estar representados na validação.

Não enviar dados de teste aos modelos antes de congelar desenvolvimento e
validação. `prepare_blind_packets` reutiliza a separação por equivalência,
texto, obra e gravação do protocolo existente e emite déficits sem inventar
amostras; as fichas privadas dos avaliadores e o mapa não são publicáveis.

G4 calcula macro-F1 binário com presença ≥2, kappa ponderado quadrático nos
escores 0–3 e alpha humano com distância quadrática fixa na escala (forma de
intervalo, que pressupõe distância entre níveis). Exige ≥0,80 em todos os
tópicos, globalmente e por idioma, com pelo menos 30 positivos e 30 negativos
de referência por tópico/idioma. Publica suportes, faltantes e recusas; não
aceita médias fornecidas pelo chamador. Suporte insuficiente bloqueia, inclusive
quando a amostra inicial de 240 itens não bastar.

G5 recebe `ResultApproval` com candidato, `request_id`, resposta e revisão.
O vínculo é por ID, nunca por ordem das linhas. Escores, segmentos citados,
schema e hash são conferidos. A tabela final mantém uma linha por participação
país/ano/posição, com as 26 colunas de escore e 26 colunas `.present` derivadas
de `score >= 2`. Escores e presenças ficam nulos antes da aprovação de G4 e de
um resultado classificado aceito; uma abstenção nunca vira zero.

## Limite de execução desta entrega

`ResearchClassificationService` integra o contrato novo ao processamento online,
à preparação/submissão de lotes, ao cache e à importação por ID. O transporte é
injetável; não foi conectado a credenciais ou a uma CLI paga nesta execução.
As rotas legadas conservam seu contrato e histórico, sem migração silenciosa.
O serviço exige G3 para piloto e G4 para produção, confere a requisição exata na
tabela auditada, revalida documento/idioma e obtém reserva exclusiva no
`RevisionRegistry`. Usa o ledger financeiro compartilhado declarado, conciliado,
com teto efetivo de no máximo US$150, e autorização de transporte desabilitada
por padrão. Resultados incertos conservam a reserva, sem reenvio automático.
O diário privado grava manifesto, responsáveis pelas reservas e resposta/job
com `fsync` e renomeação atômica antes/depois do transporte. A retomada consulta
esse diário; perder a resposta não concede permissão para submeter novamente.
O caminho do registro de identidades também precisa corresponder ao registro
compartilhado declarado, impedindo a criação acidental de filas independentes.
Respostas são importadas por `request_id`, preservando versões e recusando
duplicações/conflitos. `complete_reserved_result` valida o contrato completo
antes de concluir a reserva. Um transporte Vertex deve respeitar o modelo,
schema e configuração resolvidos, sem resolver aliases por conta própria.

O perfil da requisição fixa provedor, modelo/versão resolvida, região e retenção;
o dispatcher compara esses valores com os direitos antes de reservar orçamento
e exige que o transporte confirme o mesmo alvo. A submissão em lote e a
importação de respostas repetem as verificações. A permissão de publicação é
independente e não concede processamento.

Canário+99, fatura externa, preços/permissões atuais e aceitação da coordenação
continuam pendentes. US$150 é teto de planejamento, não autorização de gasto.
O sucesso da implementação não declara sucesso científico das etapas.

## Publicação e recuperação

O relatório e CSVs não contêm letras integrais. Os requests e fichas cegas são
privados. Para citar a pesquisa, preservar manifesto, fontes, código, ambiente,
decisões e resultados por run. Separar plataformas e 2026 parcial, publicar
denominadores/faltantes e analisar sensibilidade ao Top100 comum quando houver
suporte. Nenhum desses diagnósticos estabelece representatividade populacional.

Ver também a avaliação independente das fontes e os comandos condicionais em
[research-flow-source-assessment-20261110.md](research-flow-source-assessment-20261110.md)
e o contrato em
[research-classification-contract-20261110.md](research-classification-contract-20261110.md).

O pacote local é construído por lista explícita de arquivos, excluindo letras,
requisições privadas, fichas e credenciais. A condição de pesquisa bloqueada é
preservada no manifesto, sem publicar o pacote em serviço externo:

```powershell
.venv/Scripts/python.exe scripts/build_research_flow_package.py --audit data/runtime/research-flow-20261110/audit-0003 --output data/runtime/research-flow-20261110/research-preparation-package-v2.zip --validation-report data/runtime/research-flow-20261110/unit-tests-delivery.xml
```
