# Classificação contínua com Vertex Batch

Solicitação: substituir o limite operacional fixo de 200 itens e a espera entre
heartbeats por coordenação local contínua. Permanecem: US$ 600 acumulados,
mesma taxonomia/modelo, uma nova tentativa por documento, exclusões e histórico.
A inferência ocorre no Google, não na GPU/CPU local.

Contrato do controlador público `ContinuousBatchController.tick`: reconciliar
jobs terminais antes de reservar novos; nunca consultar estado remoto de runs
importados; dimensionar até o limite existente de 190.000 requisições por shard
pelo saldo conservador, ajustando em caso de recusa de orçamento; manter até
quatro jobs simultâneos sujeitos ao mesmo ledger. Persistir IDs antes de submit;
submissão ambígua e preparação interrompida exigem inspeção, nunca repetição.
Checar sobreposição com todos os documentos já tentados nesta noite.

Um processo local exclusivo consulta progresso a cada 30 segundos. Arquivo de
estado atualizado por substituição atômica, com lock de processo. O heartbeat
do Codex atua como monitor e recuperação, sem produzir jobs concorrentes ao
controlador. Retomar controlador falho/ambíguo requer investigação. Após concluir
ou atingir orçamento, atualizar a auditoria local e pausar o monitor.

Interfaces de teste: tick do controlador com backend público controlável e
persistência observável. Exercitar avanço após reconciliação, limites financeiros,
interrupção antes/depois de submit, importados, quality_hold e concorrência.
Interfaces de batch/retry já estavam autorizadas para testes pelo usuário.
Não alterar preços ou liberar reservas sem telemetria; sem commit/troca de branch.

Diagnóstico real: o lock PostgreSQL por sessão era liberado via conexão ORM que
podia mudar após commit, deixando o advisory lock preso no pool. Fixar o lock em
conexão física dedicada, com escopos reentrantes na mesma Session; liberar nessa
mesma conexão. O pool deve comportar conexão de guarda e de trabalho. Regressão
com PostgreSQL real: dois slots no pool, commit e guarda aninhada; concorrente
permanece bloqueado durante o escopo e pode adquirir depois de sua saída.


## Retomada autorizada em 8 de outubro de 2026 — orçamento vigente

O usuário elevou o teto acumulado para US$ 650. A coordenação aplica US$ 645
antes de cada upload e submissão, mantendo US$ 5 de margem para custos acessórios.
Esta decisão substitui os valores históricos de US$ 600 deste documento, sem
reiniciar o ledger ou liberar reservas antigas sem telemetria. Na retomada,
custos conhecidos mais reservas somam US$ 599,996980875; saldo operacional
US$ 45,003019125. A margem não é autorização para cobrança além dos créditos.

Plano de entrega: continuar apenas os retries elegíveis das três baselines,
excluindo todos os documentos já tentados nesta execução e preservando direitos,
quarentena e suspensão de LETRAS. Reconciliar prontamente os jobs e produzir a
auditoria local ao finalizar. Não gastar com novas fontes, validações externas
ou novas tentativas dos retries. Manter até quatro jobs, dimensionados pelo saldo.
O monitor deve usar teto absoluto US$ 650 e operacional US$ 645.

Qualidade de entrega: histórico íntegro, erro individual explícito, proveniência,
seleção exploratória separada da amostra principal e relatório de cobertura.
A validação da identidade e da ligação aos rankings permanece pendente; completar
todas as músicas e validar inferências populacionais não está garantido pelo saldo.
O sistema deve parar seguro quando não houver candidatos ou saldo suficiente,
importar tudo que foi submetido e pausar o monitor. Sem commits ou troca de branch.
