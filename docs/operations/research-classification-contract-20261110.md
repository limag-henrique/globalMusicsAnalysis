# Contrato de classificação para a pesquisa verificável

O contrato `research-26-topics-v1` preserva os 26 tópicos da revisão, escala inteira
0–3 e presença derivada de escore ≥2. Não soma tópicos, não migra snapshots legados
e não inicia chamadas Vertex. As 104 miniaturas de calibração são textos sintéticos
originais, propostas para revisão científica; não são rótulos humanos reais.

## Atualização de 15/11/2026

O esquema exportado agora nomeia os 26 tópicos e os marcadores auxiliares permitidos.
O ramo `classified` exige todos os tópicos; os demais estados exigem `topics={}`.
Essa regra já existia na validação de importação e agora está explícita também no
JSON Schema fornecido à geração. A mudança altera o hash do schema, os perfis e
as assinaturas das novas requisições; snapshots anteriores conservam seus hashes.

`lyrics/research_vertex_payload.py` prepara localmente o corpo REST de
`generateContent`, usando `responseJsonSchema`, o modelo resolvido, o prompt e a
rubrica exatos, o ID da requisição, idioma e segmentos sem perda. Configurações
congeladas sem mapeamento são recusadas, em vez de ignoradas. Região e retenção
permanecem no alvo de despacho e não são enviadas como parâmetros de geração.
O módulo não cria cliente nem realiza rede, upload ou inferência.

`ResearchClassificationService.prepare_batch(..., output=...)` grava, além do
manifesto interno, `vertex-input.private.jsonl` no formato de entrada em lote e
`vertex-bindings.private.jsonl` com os IDs e hashes de cada corpo de requisição.
Os resultados continuam associados por `request_id`. A produção e a submissão
ainda exigem os gates e a elegibilidade atual de cada item.

O pacote da rubrica passou a incluir `topic-dictionary.csv`,
`preparatory-table-template.csv` e `prompt-draft.txt`. O template tem 59 colunas
e nenhuma linha, preservando a ausência de escores até existir classificação
aceita. O dicionário deriva diretamente do mesmo contrato.

Para empacotar preparação, fontes de implementação e verificações locais:

```powershell
.venv/Scripts/python.exe scripts/audit_classification_preparation.py --output data/runtime/classification-preparation-NOVO --validation-report data/runtime/RELATORIO-TESTES.xml
```

O comando exige relatório sem falhas nem testes ignorados dos componentes
principais. Seu resultado declara preparação local e pendências científicas;
não substitui a auditoria G1–G5. A execução de 15/11 passou 90 testes, incluindo
serialização validada pelo SDK, tópicos ausentes/desconhecidos, abstenções,
UTF-8, hashes, idempotência, resultado fora de ordem, revogação e envio incerto.

A [documentação oficial de `responseJsonSchema`](https://docs.cloud.google.com/java/docs/reference/google-cloud-vertexai/latest/com.google.cloud.vertexai.api.GenerationConfig.Builder)
documenta `anyOf`, propriedades nomeadas e campos obrigatórios, além de exigir
MIME JSON e exclusão de `responseSchema` nessa modalidade. A validação local
completa continua obrigatória, porque o provedor admite um subconjunto de JSON
Schema. [Modelo](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash)
e [preços](https://cloud.google.com/model-garden/pricing) foram consultados; essa
consulta não cria reserva financeira nem substitui a revalidação no envio.

## Gerar o instrumento de revisão

```powershell
.venv/Scripts/python.exe scripts/prepare_research_contract.py --output data/runtime/research-flow-20261110/contract-bundle-novo
```

O destino precisa ser novo. O comando produz rubrica, contrato, schema e manifesto
com hashes. A rubrica define quatro níveis e um contraexemplo por tópico. Cada nível
deve ser revisado por competência linguística e temática antes de qualquer produção.
Os exemplos distinguem menção de endosso, dinheiro de materialismo, agência de
objetificação e metáfora de arma literal. Um exemplo curto isolado não substitui
a leitura da canção inteira.

## Aceitação explícita da rubrica

`validate_rubric(rubric, require_accepted=True)` exige `status="accepted"` e o objeto
`acceptance` com `actor`, `at` (ISO 8601 com timezone, sem data futura) e
`rubric_sha256`. Esse hash é SHA-256 do `canonical_json` da rubrica sem a chave
`acceptance`, já com o estado `accepted`. O validador vincula uma declaração ao
conteúdo exato; não autentica a identidade, competência ou autoridade da pessoa.
A decisão e suas evidências devem permanecer na cadeia de revisão do projeto.

O contrato exportado conserva `scientific_acceptance=false`: gerar ou validar
estrutura local não declara a homologação empírica do classificador. A aprovação
da rubrica é uma das condições externas do controlador de etapas.

## Preparação e validação local

Em `lyrics/research_contract.py`:

- `build_profile(...)` vincula modelo resolvido, configuração, rubrica efetiva,
  prompt, schema, protocolo e segmentação usando o perfil de execução existente.
- `prepare_request(...)` recebe edição textual, texto, idioma, perfil e rubrica.
  O caller precisa validar os gates globais e a elegibilidade atual do documento;
  essa função apenas constrói o objeto local. Idioma e hash textual fazem parte
  da assinatura. Preparar não reserva nem envia.
- `segments(text)` mantém todos os bytes representados no texto Unicode, inclusive
  CRLF, espaços e repetições. Os offsets são posições de caracteres Unicode em
  Python, não bytes nem offsets UTF-16. A concatenação das partes recupera o texto.
- `verify_request(...)` reconstrói o objeto completo e recusa alterações no contrato,
  ID, texto, offsets, configuração ou assinatura.
- `validate_result(...)` usa o ID da requisição, exige os 26 escores inteiros para
  `classified` e valida justificativas e segmentos. Recusas e outros estados não
  classificáveis não podem carregar escores; evidência positiva precisa apontar
  para segmentos existentes e não vazios.
- `table_row(...)` exporta 26 escores e presenças derivadas, sem texto integral.
  Antes do resultado aceito, todos os escores e presenças são nulos. A tabela
  ainda exige a junção auditável às participações e proveniência pelo controlador.
  O CSV final do controlador mantém uma linha por participação e exporta as
  colunas `<topic>.present` somente após G4 aprovado e resposta classificada
  aceita; cada valor deriva de `score >= 2`.

`prepare_blind_packets(...)` reutiliza a separação e fichas existentes: duas pessoas
distintas, segredo privado, ~80 itens de desenvolvimento e ~240 de validação.
Só entram edições originais verificadas sem exposição prévia à IA/revisão histórica.
Obras, gravações, grupos equivalentes e textos idênticos não atravessam conjuntos.
Vagas não preenchidas aparecem como déficit. A saída contém `split_manifest`,
um manifesto privado com assignments, hashes de texto, grupos, seed, algoritmo,
targets, contagens e déficits. Esse manifesto deve ser preservado e referenciado
por SHA-256 como `validation_split` em `ResearchEvidence`; G4 rejeita ausência,
alteração, sobreposição ou cobertura parcial do split congelado. Mapas privados
ficam separados das fichas cegas. País, posição e fonte não aparecem nas fichas.

## Evidência G2 e migração do esquema

Cada `TextReview` da versão `worldwide-research-flow-v4` exige identidade,
integridade, completude, checagem de truncamento e contaminação, idioma igual ao
documento, nível/escopo de competência linguística e um artefato hashado de
competência. O terceiro adjudicador usa o mesmo checklist. O software valida
vínculos, hashes e campos; a coordenação ainda precisa revisar as credenciais e
o conteúdo das evidências.

O esquema de evidências novo exige `schema_version="research-evidence-v4"`.
Direitos são registros distintos para armazenamento, processamento e publicação,
cada um com base e prova hashada. G2 exige armazenamento autorizado. Vertex só
despacha quando processamento está autorizado e há concessão explícita para o
provedor, modelo, versão resolvida, região e retenção exatos. O alvo faz parte do
perfil imutável da requisição; transportes precisam confirmá-lo, e respostas em
lote são revalidadas contra a concessão antes da importação. Publicação não é
inferida de nenhuma outra permissão.

Snapshots antigos e aprovações sem esses campos não são convertidos
silenciosamente. Preserve-os como histórico e refaça a revisão aplicável na
versão nova; o contrato de classificação legado permanece intacto.

`complete_reserved_result(...)` adapta resultados novos ao `RevisionRegistry`
existente depois da validação completa, preservando o resultado original. O serviço
chamador deve revalidar direitos e adjudicação atuais e possuir a reserva exclusiva.
O registro existente mantém envios incertos reservados e impede duplicações por
concorrência. Este contrato não adiciona outro dispatcher pago nem substitui o
gate existente de produção.

## Verificação

Reconstrução independente local das métricas observadas em charts, antes da
avaliação G1:

```powershell
.venv/Scripts/chart-observatory.exe research reconstruct --observations data/runtime/observations-normalized.jsonl --output data/runtime/reconstruction-BR-2018-v1 --country BR --year 2018 --platform SPOTIFY --provider MGD --quota 230 --depth 200 --frequency daily
```

Cada linha de entrada exige `country_code`, `platform`, `provider`, `period_start`,
`period_end`, `candidate_id`, `position`, `metric_value`, `title` e `artist`.
Datas usam ISO `YYYY-MM-DD`; períodos diários têm início igual ao fim; semanais
têm sete dias e pertencem ao ano do encerramento. Para `--frequency weekly`, fornecer
`--expected-periods caminho.json` com uma lista de encerramentos ISO da janela.
O corte permanece `2026-10-15`. Fontes/plataformas diferentes não são somadas.

O comando produz `reconstruction.json`, `ranked_rows.jsonl` e manifesto de hashes.
Uma reconstrução com calendário incompleto, profundidade insuficiente, conflito,
métrica inválida ou empate na fronteira da cota permanece diagnóstica e retorna
`reconstruction_approved=false`. Um resultado técnico positivo não é aprovação
científica da fonte ou do ranking; permanece necessária a revisão vinculada ao G1.
Input malformado não cria uma pasta de resultado; pastas existentes não são sobrescritas.

Para automações, o término bem-sucedido de `research audit` significa que o
diagnóstico foi produzido, mesmo quando os portões reprovaram. O comando de
bloqueio obrigatório é:

```powershell
.venv/Scripts/chart-observatory.exe research require --audit data/runtime/research-flow-20261110/audit-v1 --gate G2 --project .
if ($LASTEXITCODE -ne 0) { throw "G2 não aprovado; próxima etapa bloqueada" }
```

`research require` valida hashes, estado do portão e documentos canônicos atuais,
saindo com código 1 se qualquer condição estiver bloqueada. Aceita G1–G5;
`research verify` apenas confere integridade dos artefatos. `research prepare`
executa a exigência G2 internamente antes de criar arquivos privados.

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/lyrics/test_research_contract.py -q
```

Os testes cobrem rubrica, alteração posterior à aceitação, perfis adulterados,
segmentação sem perda, mudança de versão/idioma/modelo, ausência de evidências,
escores com coerção ou fora da escala, associação por ID, abstenções, reserva
compatível, tabelas nulas e separação cega sem contaminação.
