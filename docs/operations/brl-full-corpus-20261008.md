# Classificação de todo o corpus — orçamento em reais

Esta operação substitui os tetos históricos em USD e a suspensão de LETRAS para
classificação exploratória. Teto acumulado: **R$3.500**, incluindo histórico,
falhas, reanálises e custos acessórios. Troca de conta não reinicia custos.
Sem commits, troca de branch, reset de Docker ou geração online.

## Evidência financeira autenticada

Consulta somente de leitura ao Cloud Billing na aba autorizada pelo usuário:

- Conta vinculada: `0169AF-BC9CE9-C4CC1C`. Crédito inicial R$1.761,10;
  restante R$848,20; utilizado R$912,90.
- Fatura setembro `5711602546`, de 30/09/2026: tabela R$1.517,573479;
  após desconto confirmado R$759,119447, antes de créditos promocionais.
  Valor a pagar zero não significa custo econômico zero.
- Câmbio da fatura: 5,8703. Não é usado para estimar outubro.
- SKUs batch vigentes: entrada R$4,448206053/milhão; saída
  R$22,241030268/milhão. Oferta introdutória Gemini de 50% confirmada resulta
  em R$2,2241030265 e R$11,120515134/milhão. Crédito gratuito não é esse desconto.
  Preços exigem revisão em 01/11/2026.

Fontes: [fatura](https://console.cloud.google.com/billing/0169AF-BC9CE9-C4CC1C/reports/tabular),
[créditos](https://console.cloud.google.com/billing/0169AF-BC9CE9-C4CC1C/credits/all),
[tabela da conta](https://console.cloud.google.com/billing/0169AF-BC9CE9-C4CC1C/pricing),
[oferta oficial](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing).
Metadados locais: `data/derived/lyrics/budget-20261008/billing-policy.json`.
Nenhuma credencial foi salva nesse arquivo.

## Contabilidade e projeção

Os 22 runs terminais comprovadamente anteriores ao fechamento de setembro são
cobertos pela fatura. Snapshots e reservas originais permanecem inalterados.
Outros runs continuam no ledger. Resposta sem uso registrado retém sua parcela
conservadora de entrada e saída. A parcela só substitui a reserva integral após
conferir todos os hashes de requisição e o tamanho original reconstruído do JSONL.
Sem conferência, mantém-se a reserva integral; saída expirada não tem custo zero.

Entrada reservada usa, no mínimo, um token por byte do JSONL completo; saída usa
1.024 tokens por documento. O piloto informa a estimativa esperada e não reduz
esse limite conservador. Oferta, modelo ou câmbio diferentes exigem nova política.

Restam 76.933 documentos: 57.946 GENIUS, 15.289 LETRAS, 3.394 LRCLIB e 304
LYRICS_OVH. Resultados válidos são reutilizados; texto ausente e instrumentais têm
desfecho local explícito. A projeção não garante que toda resposta seja válida.

| Componente | Reais |
| --- | ---: |
| Histórico e compromissos anteriores conciliados | 913,32 |
| Restante esperado pelo piloto | 837,24 |
| Restante conservador por bytes e máximo de saída | 2.235,07 |
| Reanálise: 5% do restante conservador | 111,76 |
| Custos acessórios reservados | 35,00 |
| Total esperado com reservas | 1.897,32 |
| Total conservador com reservas | 3.295,15 |

A reserva de 5% é planejamento, não garantia da taxa de falha. Falhas superiores
continuam sujeitas ao teto. Créditos atuais também limitam cada submissão: R$35
do saldo exibido protegem contra atraso de faturamento/uso histórico incerto,
além das reservas acima. Inicialmente R$666,44 podem ser comprometidos em novos
jobs. Segunda conta não é saldo disponível até verificar vínculo e créditos;
troca continua humana e não reinicia o teto. Parada financeira preserva checkpoint.

## Execução e recuperação

Controlador exclusivo `scripts/run_continuous_lyrics.py`, Python `.venv`, até
quatro jobs e consultas a cada 30 segundos. Gemini 3.8 Flash, LOW, saída máxima
1.024, GCS privado, PostgreSQL 16 em `127.0.0.1:56433`. Preflight confirmou
ausência de runs preparados/uploaded/submitted/running antes desta retomada.
`quality_hold` e `controller_stop_requested` bloqueiam novos envios.

Plano: corpus ainda não tratado, runs históricos com erros técnicos e etapa final
de reanálise limitada. Nesta execução: tentativa principal e no máximo uma nova
tentativa por documento para os códigos de `TECHNICAL_RESPONSE_ERRORS` em `continuous.py` (inclui resposta
incompleta, schema individual inválido, uso ausente e erro individual do provedor).
Nunca repetir submissão ambígua. IDs e `submission_attempted` são persistidos
antes da chamada. Erros de autenticação, esquema ou integridade exigem inspeção.
Importar terminais prontamente e finalizar uma vez; não consultar Google para
importados/cleaned. Preparação interrompida exige inspeção antes de reiniciar.

Estado anterior preservado em `prior-status-preserved.json`; estado atual no
caminho habitual `data/derived/lyrics/overnight-20261007/status.json`. Contagens
por execução e run evitam confundir progresso do job com o corpus. Ao terminar,
gerar auditoria local em diretório novo e pausar monitor após preservar pendentes.

LETRAS e alertas de identidade autorizam análise do texto fornecido, sem validar
ligação à música/ranking. Quarentena e seleção científica estrita permanecem.
Classificação exploratória não comprova preferência ou valores da população
geral; validação metodológica continua pendente.

Validação: 181 testes passaram; regressões cobrem reserva parcial, âncora da
fatura, inclusão exploratória preservando direitos/quarentena e bloqueio antes
de upload/submissão. Ruff e mypy passaram.


A revisão de cobertura adicionou os 197 erros individuais fora da whitelist antiga.
Três jobs já enviados (22.749 documentos) foram preservados durante recarga
graciosamente, sem cancelamento ou nova submissão. Para parada concorrente, o
marcador independente `controller.stop` também pode ser criado junto ao estado;
remova-o somente após autorização explícita de retomada.
