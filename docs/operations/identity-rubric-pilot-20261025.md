# Identidade, letras e validação — 25/10/2026

Estado: preparação local concluída; adjudicação, piloto temático e produção
continuam pendentes. Nenhuma chamada paga e nenhuma alteração no banco histórico.
Branch `main` preservada, sem commits. A coleta convencional anterior continua
separada; seu estado atual deve ser consultado nos logs.

## Arquivos para trabalhar

Pacote vigente: `data/derived/annual_revision/20261025-review-v2/`.

- `integrity-review-A.jsonl` e `integrity-review-B.jsonl`: 80 fichas por avaliador,
  referentes às mesmas músicas, com identificadores e ordens diferentes. As
  variantes permanecem separadas. Há ficha sem transcrição disponível para
  confirmação de identidade, sem preencher versos ou atribuir zeros.
- `rubric-v2-draft.json`: dicionário dos mesmos 26 tópicos, escala 0–3, presença
  >=2, definições, exemplos de fronteira e marcadores auxiliares separados.
- `quality-criteria-proposal.json`: proposta não aceita; deve ser decidida antes
  de avaliar resultados e escolher modelos.
- `blind-assessment-template.json` e `adjudication-template.json`: instrumentos
  para a etapa temática e para resolver divergências, sem respostas preenchidas.
- `identities-and-equivalences.jsonl`: 19.786 candidatos com IDs, associações e
  estados separados de aquisição, identidade, integridade e aplicabilidade.
- `eight-case-diagnostics.jsonl`: diagnóstico individual dos oito casos
  contestados, preservando comentários humanos como evidência, sem torná-los
  automaticamente adjudicações definitivas.
- `classification-profile-template.json`: configuração ainda não resolvida,
  intencionalmente incompatível com preparação de uma chave reutilizável.

O subdiretório `private/` contém as correspondências entre fichas, hashes e fontes.
Não fornecê-lo aos avaliadores. Os arquivos com letras e essas correspondências
ficam locais; a pasta de revisão foi acrescentada ao `.gitignore`.

Os avaliadores devem trabalhar independentemente, sem consultar respostas
anteriores, o outro avaliador ou a tabela privada. Na triagem, registrar a versão,
o idioma, identidade e integridade de **cada variante** e os links da evidência
oficial ou da gravação conferida. Não escolher o texto mais longo ou a maioria
entre sites como se isso comprovasse fidelidade.

## Dois conjuntos diferentes

As 80 fichas preenchidas com candidatos são uma **triagem de integridade**, não
o piloto temático. Ela prioriza os oito casos, divergências textuais e músicas
com mais associações país/ano, diversificando fontes, períodos e risco quando
há metadados disponíveis. Idiomas desconhecidos aguardam avaliação humana.

`pilot-A/B.jsonl` e `validation-A/B.jsonl` estão vazios: ainda não há edições
textuais adjudicadas fornecidas a essa preparação. Os déficits são 80 e 240,
respectivamente. Não foram preenchidos com músicas suspeitas ou fictícias.

Ao fornecer edições validadas, a seleção usa idioma, fonte, período e risco.
Exige declaração explícita de ausência de exposição prévia e de revisão histórica,
texto original e grupos de equivalência confirmados. Equivalências, textos
normalizados idênticos e vínculos confirmados de obra/gravação não atravessam os
conjuntos de desenvolvimento e validação. Esse bloqueio de avaliação não funde
identidades musicais. Os oito casos antigos ficam fora da validação independente.

## Correções verificadas

O seletor anual somava dois itens com IDs reais diferentes quando título e artista
coincidiam. O teste reproduziu essa soma incorreta e agora confirma a conservação
dos dois itens. Somente a repetição de um mesmo item pode ser agregada por ID;
duplicação contraditória do item dentro de uma captura é rejeitada.

Os agrupamentos baseados apenas em metadados continuam sendo candidatos
provisórios, sem confirmação de identidade ou integridade. IDs `web-derived`
permanecem identificadores locais; não viram IDs nativos YouTube. A seleção de
popularidade anterior e as capturas originais permanecem preservadas.

No caso **Culpable**, o endpoint público oficial Spotify retornou:

- `4nxTe3aVTD3tpxjfxdITkv`: **Culpable**;
- `6n5NCZLglzqbYFgadmcOqP`: **Culpables**.

As respostas e seus hashes foram preservados e incluídos no diagnóstico. Isso
estabelece os títulos dos itens de plataforma, não prova equivalência musical,
autoria de uma transcrição ou qual letra deve substituí-la. O caso continua
bloqueado até confirmação da gravação e da edição textual correta. Nos outros
sete, os candidatos recuperados também aguardam essa confirmação.

O cache anterior reconstituía respostas com outra codificação em UTF-8,
alterando os bytes. A correção preserva os bytes e a codificação: texto UTF-8 com
hash verificado dispensa uma segunda cópia; outras codificações guardam bytes em
base64. Um cache antigo só comprova seus bytes originais se a reconstrução
confere com o hash registrado. Caso contrário, continua útil como candidato,
com essa limitação explícita, sem nova consulta automática apenas para regravá-lo.

Novas execuções também registram hash da extração original, versão do derivado,
transformações e método. O processo de aquisição iniciado anteriormente já
havia carregado o código antigo: não foi interrompido e não ganhou metadados
retroativos inventados. Seus caches e respostas continuam preservados.

## Reutilização e concorrência

O registro persistente local é
`data/derived/annual_revision/revision-registry.sqlite`. Não inicia outro serviço
na máquina nem substitui o PostgreSQL histórico, que estava indisponível.

O esquema separa obras, gravações, edições textuais e alegações de identidade de
plataforma, além dos vínculos com evidência. Onde não existe prova, as tabelas de
identidades confirmadas permanecem vazias. Não foram inventados ISRCs ou vínculos.

A chave de revisão inclui identidade textual validada, hash normalizado, versão
da normalização, rubrica, prompt, modelo e configuração resolvida. A configuração
deve descrever os parâmetros efetivos, versão do provedor, modo de execução,
schema e instruções usados; o marcador `resolved` exige decisão explícita.
O sistema não preenche padrões desconhecidos para simular compatibilidade.

Normalização em proposta: `lyrics-normalization-v2-draft1`. Uniformiza NFC,
quebras de linha e espaçamento horizontal e remove excesso de linhas vazias;
conserva palavras, pontuação, caixa, seções e repetições. Não reconstrói versos
nem une linhas por inferência. Original e normalizado têm hashes separados.

Restrições SQL e transação permitem um único proprietário por chave. Uma resposta
desconhecida continua reservada, sem retentativa por expiração automática.
Um resultado humano adjudicado e validado no contrato pode completar a reserva
sem chamada ao provedor. A preparação pesquisa esse registro sem consulta agêntica
e separa resultados compatíveis, pendências e requisições novas.

Os snapshots antigos não registram todos os componentes dessa chave. Portanto,
o preparo anual deixou de inferir compatibilidade apenas de modelo/rubrica/prompt.
Sua fila histórica é marcada `not_for_submission` quando não há assinatura v2
completa. Os snapshots permanecem como histórico comparativo. O prompt de produção
v3 não foi alterado nem substituído silenciosamente pelo rascunho v4.

O registro e as funções de preparação v2 não enviam lotes. O futuro remetente
deverá obter a reserva dessa chave antes de cada envio e reconciliar respostas
desconhecidas. Os executores legados não foram migrados para esse protocolo.

## Proposta de qualidade, ainda para decisão

- Cobertura de avaliações pontuadas >=98%.
- Por tópico: kappa ponderado quadrático >=0,80; precisão e sensibilidade >=90%.
- Limites inferiores dos intervalos de 95% para precisão e sensibilidade >=80%.
- Pelo menos 30 positivos e 30 negativos adjudicados por tópico; suporte insuficiente
  exige mais exemplos ou resultado identificado como exploratório.

Esses valores são uma proposta, não um padrão externo nem um resultado observado.
Um piloto de 80 ou validação de 240 pode ser insuficiente, especialmente por
idioma e para temas raros. Os critérios não devem ser relaxados após observar
resultados apenas para aprovar um modelo. Enriquecimento diagnóstico não estima
frequências do corpus nem prevalências nos mercados.

`compare_scores` calcula kappa ordinal, confusões no limiar 2, precisão,
sensibilidade, intervalos de Wilson e suporte por dimensão. Valores desconhecidos
não se tornam negativos. Precisão/sensibilidade pressupõem referência adjudicada;
não interpretar uma discordância entre dois avaliadores como erro contra verdade
definitiva antes da adjudicação. Instrumentais e textos sem evidência suficiente
recebem estado próprio, sem 26 zeros automáticos.

A comparação entre modelo econômico e mais capaz usará a mesma parte do piloto,
com textos e configurações fixados. Nenhum modelo, preço ou tamanho de lote foi
escolhido agora; isso depende dos critérios aceitos e dos dados validados.

## Reproduzir sem novas chamadas

```powershell
.venv/Scripts/python.exe scripts/prepare_review_protocol.py --prepared data/derived/annual_revision/20261025-final --output data/derived/annual_revision/NOVO-PACOTE
```

Para etapas posteriores, `--validated-editions` recebe JSONL com texto, hashes,
identidade textual, equivalência, versão, idioma, proveniência, declarações de
exposição e validação. `--classification-profile` recebe a configuração resolvida.
`--registry` permite reutilizar o mesmo registro persistente; não apontar para
um SQLite novo se a intenção é consultar decisões e resultados existentes.

Fluxo principal: `domain-modeling`, necessário para as quatro identidades.
Complemento: `diagnosing-bugs`, para reproduzir e corrigir a fusão de IDs e o
cache de bytes. A especificação está em `research/identity-rubric-pilot-v2-spec.md`.
Testes verificam essas fronteiras, cegamento, separação dos conjuntos, unicidade,
reutilização, preservação textual e métricas; não certificam letras reais sem
adjudicação nem substituem a validação humana.

Verificação consolidada: 69 testes passaram; Ruff passou. A verificação dos
artefatos confirmou 80 fichas por avaliador, IDs cegos distintos, oito diagnósticos,
19.786 alegações de identidade e nenhum vínculo musical confirmado inventado.
