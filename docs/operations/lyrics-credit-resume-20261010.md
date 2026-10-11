# Retomada com o crédito corrente — 10/10/2026

Autorização: usuário solicita continuar usando o saldo restante da mesma conta. Não houve troca de conta.

Evidências preservadas em `data/derived/lyrics/budget-20261008/resume-20261010-210654/`: checkpoint e política anteriores, inspeção local do ledger, prefixes GCS, conciliação financeira e checkpoint de ativação. A UI autenticada confirmou conta `0169AF-BC9CE9-C4CC1C`, projeto `project-bae72195-c4bf-4177-bca`, crédito original R$ 1.761,10, saldo R$ 438,41, débito acumulado R$ 1.322,69.

Os 92 runs da execução estavam importados, com todos os snapshots vinculados. Não havia job enviado pendente, preparação interrompida ou upload aguardando submissão. As 61 preparações falhas não tinham submissão, job ou objetos nos prefixes exatos `runs/<run_id>/`; o histórico e os IDs permanecem preservados e não foram repetidos. A política de preços autenticados continua válida até 01/11/2026, sem conversão arbitrária de câmbio.

A observação da mesma conta foi reconciliada aos custos conhecidos de R$ 1.322,43, cobertos pelo débito acumulado autenticado. Runs terminais importados passam a integrar a referência dessa observação do saldo; não são retirados do ledger global nem da âncora da fatura. A conferência integral de hashes e bytes manteve o compromisso global exatamente em R$ 1.323,14127000403245925248. A parcela desconhecida/retida de R$ 0,70748051593644725248 permanece nesse compromisso e é também deduzida do crédito utilizável, arredondada conservadoramente para R$ 0,71. Não foi liberada uma reserva desconhecida.

| Componente | BRL |
| --- | ---: |
| Saldo autenticado da conta | 438,41 |
| Proteção de segurança do crédito | 35,00 |
| Componente desconhecido retido adicionalmente no crédito | 0,71 |
| Reserva de retry | 111,76 |
| Reserva acessória | 35,00 |
| Margem conservadora para novas reservas na retomada | 255,94 |

O teto global segue R$ 3.500; a segunda conta segue sem crédito verificado e exige transição humana. As guardas públicas validaram a margem e uma reserva local de R$ 1 antes da ativação; não houve upload nesse teste. Os 15 testes de orçamento, continuidade e checkpoint passaram.

O controlador foi relançado por `.venv/Scripts/python.exe`, `Start-Process -WindowStyle Hidden`, sem `-Wait`, com `--poll-seconds 30 --max-inflight 4`. Wrapper PID 17016; Python real PID 17040, ambos conferidos via Windows. O lock continua exclusivo. Durante a inicialização, o checkpoint pode conservar o PID antigo até a primeira gravação: verificar a linha de comando Windows antes de concluir que o processo desapareceu; não iniciar concorrente.

Esta é retomada da execução técnica existente, que mantém os documentos originais e os limites de tentativas. Os rascunhos de texto corrigido e o planejamento separado de reanálise em `followup-20261010-final` não foram registrados nem enviados por esta ativação. Não pressupor que a retomada consome esses JSONL locais ou que altera os textos dos jobs. `quality_hold`, parada solicitada, ambiguidades, falhas globais e falta de margem seguem bloqueantes.

## Recuperação da conexão na primeira partida

A primeira partida encerrou com `OperationalError`, antes de preparar/submeter qualquer job. `pg_ctl status` confirmou servidor desligado e `pg_isready` confirmou ausência de resposta em 56433; o PID18088 estava ausente no Windows. O arquivo de PID obsoleto foi preservado com sufixo `interrupted-20261010-183243`. O mesmo cluster foi iniciado em janela oculta, sem alterar dados ou configurações; PostgreSQL16.15 recuperou o WAL e confirmou prontidão. A causa externa do desligamento interrompido não foi estabelecida; não confundir esse evento com falha financeira.

`database-connection-failed-checkpoint.json` preserva a falha. `database-recovery-reconciliation.json` comprova versão160015, os mesmos92 jobs/36449 requests importados, zero jobs pendentes e61 preparações falhas preservadas. Só após essa reconciliação o checkpoint foi reativado e o controlador relançado: wrapper14100/Python real2992, linha de comando Windows confirmada. O monitor foi reativado pela ferramenta do aplicativo com sucesso, mantendo seu intervalo e destino existentes.

Novo envio confirmado no checkpoint às 18:34:48 BRT: run `88bdb5a3-88a9-481f-9844-a64927339149`, 7.412 documentos, estado `submitted`, job Vertex `4529289304236621824`. `submission_attempted=true` e IDs foram salvos antes da chamada. `submission-confirmation.json` preserva a observação e a situação do monitor. A margem de R$255,94 acima é a margem anterior a este envio, não o saldo livre posterior à reserva do novo job. Enquanto o controlador estiver vivo, não editar seu checkpoint nem iniciar outro processo; acompanhar estado/logs e preservar/importar terminais normalmente.
