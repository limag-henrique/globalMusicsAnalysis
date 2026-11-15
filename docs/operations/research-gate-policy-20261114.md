# Critérios executados — 14/11/2026

Novas auditorias usam `gate_policy_version=complete-rankings-lyrics80-v1`:

| Gate | Meta global e em cada país/ano |
|---|---:|
| G1 — posições comprovadas / posições previstas | 100% |
| G2 — posições com letra aprovada / posições aprovadas G1 | 80% |
| G3 — posições preparadas / posições aprovadas G2 | 100% |
| G5 — resultados aceitos / posições liberadas | 80% |

G4 conserva os critérios de homologação científica independente. Denominador
indefinido ou vazio não aprova; nenhuma célula é removida automaticamente.
`legacy80-v4` permanece disponível explicitamente para reproduzir cálculos
históricos. O schema de evidências v4 continua compatível; a mudança de meta
é registrada separadamente no relatório e no progresso, sem editar snapshots.

O auditor agora integra `verify_published_annual`: confere profundidade,
posições, IDs, fonte, período e metadados. `metric_value=null` é permitido para
ranking publicado; não são criados valores de streams. A modalidade calculada
continua exigindo métricas numéricas e reconstrução independente. O vínculo
documental, a revisão da fonte e os direitos continuam verificados pelo fluxo.
Não existe promoção científica automática por concluir uma extração.

Autorização institucional declarada pelo usuário: **MG.202652246900**,
atribuída ao Ministério da Educação e ao Comitê de Ética e Uso Responsivo de
Dados da UFMG. Esta entrada registra a referência informada; não constitui
parecer de identidade/completude de letras nem autenticação do documento.

## Evidências produzidas

- `data/runtime/research-execution-20261114/audit-policy-v5-0001/`:
  auditoria real da seleção `global-rescan-2018-2026-20261111-v4-final-0002`.
- `data/runtime/research-execution-20261114/progress-policy-v5-0001/`:
  progresso congelado com a política nova e metas explícitas.
- `research verify` confirmou a integridade. 90.600/277.650 posições
  observadas, 187.050 faltantes para a nova meta; zero aprovações G1/G2.
- 106 testes de flow/progress/CLI passaram; posteriormente 71 testes flow
  passaram incluindo o novo ramo anual sem métricas sintéticas. Mais um teste
  confirmou que a política padrão reprova uma seleção comprovada em apenas
  80%, mantendo G2 pendente. Ruff passou nos módulos alterados.

## Limitações que permanecem explícitas

O adaptador mantém o recorte congelado: janeiro–dezembro e 2026 até 15/10.
Uma publicação com ano comercial diferente não é automaticamente equivalente.
Entrada de chart que agrega gravações não identifica uma edição textual única.
Publicação de rádio, vendas ou performance não se transforma em streams: a
definição de fonte precisa declarar a métrica real e a seleção metodológica
precisa manter esses estratos visíveis. A validação estrutural não autentica
uma declaração falsa de fonte ou uma identidade humana.

Auditorias antigas aprovadas conservam suas políticas históricas; automações
da campanha atual devem utilizar exclusivamente auditorias com a policy nova.
Qualquer alteração posterior do código de reconstrução exige nova auditoria;
os diretórios acima permanecem preservados como evidência da execução.
