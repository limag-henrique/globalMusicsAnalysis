# Execução noturna autorizada — 7 de outubro de 2026

O usuário autorizou a execução sem supervisão, a continuidade do plano aprovado e
uma única nova tentativa por erro técnico, respeitando o teto acumulado de US$ 600.
Essa autorização não permite descartar análises, mudar de branch ou criar commits.
O contrato científico, LOW, 1.024 tokens, quarentena e suspensão de LETRAS continuam
vigentes. Após discutir a margem histórica de US$ 5, o usuário reafirmou o teto
operacional de US$ 600 nesta execução; não autorizou aumento além desse valor.

## Ambiente recuperado

Docker Desktop foi recuperado isolando, com seus processos encerrados, as pastas
de sockets Docker/run e docker-secrets-engine. Não foi solicitado outro factory
reset. O volume Docker e seus 151.153 snapshots foram preservados. O PostgreSQL
18 do Windows permanece intacto; sua configuração de autenticação foi restaurada
byte a byte depois de uma tentativa de recarga recusada pelo Windows.

A base de trabalho mais atual é PostgreSQL 16 em
`data/recovery/postgres16-cluster`, escutando somente em 127.0.0.1:56433. O `.env`
agora aponta explicitamente para ela. Foi feita uma cópia física antes de iniciar
a recuperação WAL; os 167.932 snapshots existentes sobreviveram à inicialização.
As cópias estão em `data/backups/docker-recovery-20261007`, excluídas localmente do
Git, junto com dump do banco Docker e cópia do disco Docker de 10 GB.

Docker e o PostgreSQL recuperado estão ativos. Não é necessário iniciar Streamlit
ou o classificador online para operar o batch. Não execute ambos classificadores
simultaneamente. ADC e o preflight de banco/bucket/modelo passaram.

## Estado financeiro e de resultados

O ledger registra US$ 128,86547925 de custos conhecidos e US$ 598,272392625 de
custos/reservas conservadores acumulados. Reservas de respostas sem telemetria
não podem ser liberadas apenas porque o job terminou. O total conservador já
deixa US$ 1,727607375 de disponibilidade conservadora sob o teto de US$ 600.
Somente pequenas tranches que caibam nesse saldo podem ser submetidas. A aplicação
agora mantém reserva também quando arquivos de resultados expiraram; ausência do
arquivo não comprova ausência de cobrança. O teste de regressão falhou antes da
correção e passou depois, junto dos demais 81 testes batch.
Exportação detalhada de faturamento poderá permitir reconciliação futura, mas
não se pode inventar custo zero nem alterar snapshots/reservas para desbloquear.

O job `6e7ca60b-4a2e-4fca-a1c5-0be99f3af44d` terminou com 20 sucessos no Vertex.
Seus objetos GCS já expiraram; importação não encontrou linhas e finalização
registrou 20 snapshots `batch_missing_output`. Não são resultados classificados.
Os demais snapshots foram mantidos. O arquivo de estado e a lista de runs da
execução estão em `data/derived/lyrics/overnight-20261007/status.json`.

## Continuidade automatizada

O acompanhamento deve usar a base 56433, o ledger e os comandos existentes em
`gemini-batch-lyrics.md`. A autorização substitui o checkpoint operacional manual,
mas não substitui validação do canary/piloto, esquema, segurança ou orçamento.

1. Consulte o estado persistido antes de qualquer mutação. Verifique o processo e
   o endpoint correto, ADC, preflight e reservas; não imprima letras ou segredos.
2. Inspecione somente jobs ainda não reconciliados. Para terminal confirmado,
   importe e finalize uma vez. Nunca consulte `status` de runs já importados ou
   limpos: o comando atual pode sobrescrever seu estado local com o do provedor.
3. Preserve o histórico. Limpeza GCS exige todos os snapshots e resumo durável;
   não limpe evidências necessárias nem delete buckets ou volumes.
4. Enquanto o compromisso conservador não comportar uma nova tranche sob US$ 600,
   não submeta nada. Use o cálculo existente `enforce_cumulative_cost_cap`.
   Notifique o bloqueio uma vez e permaneça em silêncio sem mudança relevante.
5. Enquanto houver saldo conservador, use as proteções existentes para
   preparar tranches pequenas (no máximo 200 itens) de erros técnicos sem uso
   registrado (`batch_malformed_response` e `batch_missing_output`). Exclua LETRAS,
   quarentena, itens já resolvidos e reservados. Não reenvie canary/piloto válidos.
6. Grave cada novo ID no estado antes de submeter. Use `--max-cost-usd 600` em
   preparação e submissão. Não tente novamente submissão ambígua ou job falho;
   resolva o job existente pela identidade opaca e interrompa na dúvida.
7. A lista de runs baseline é fixa: não crie retries de retries criados nesta
   execução. Cada música recebe no máximo uma nova tentativa. Se faltarem saldo
   ou dados para garantir isso, pare e registre o motivo.
8. Importe resultados prontamente, antes do lifecycle de sete dias. Ao terminar,
   grave contagens, erros remanescentes e custos, e pause o acompanhamento.

As fontes fixas para uma nova tentativa são os runs principais `9361b92b-64b6-4cb5-adb9-1a23dd78ec50`
e `41934591-0444-4fce-bfde-238497f31e3a`, e o run antigo com objetos expirados
`6e7ca60b-4a2e-4fca-a1c5-0be99f3af44d`. Verifique candidatos com
`BatchRepository.error_retry_candidates`, excluindo qualquer resultado válido
posterior e documento já selecionado nesta execução. Nunca adicione novos IDs à
baseline. O primeiro retry desta execução é `ba5cb6d8-a480-4869-91c5-c7e86fd5474c`:
200 itens, reserva US$ 0,718473. IDs de novos runs ficam em `retry_run_ids`.

Se uma preparação exceder o saldo, inspecione o ledger antes de repetir e reduza
o limite para 100, 50, 20, 10 ou 1. Preparação recusada por orçamento não consome
tokens nem deve causar submissão. Outras falhas interrompem a execução. Não
reenvie automaticamente jobs falhos nem submissões de resultado ambíguo.

Para iniciar o PostgreSQL recuperado desligado, use `Start-Process` com
`-WindowStyle Hidden`, **sem `-Wait`**, apontando o `pg_ctl.exe` local para o cluster,
porta 56433 e host 127.0.0.1. Confirme identidade do cluster e ausência do processo
antigo antes de isolar eventual PID obsoleto; não altere o PostgreSQL 18.

## Crédito e acompanhamento

O usuário informou R$ 759 usados de R$ 1.761 na conta atual: saldo informado
R$ 1.002. Ele fará a troca de conta pessoalmente ao esgotar esse crédito. A troca
não reinicia o teto acumulado de US$ 600 nem libera reservas dos jobs anteriores.
Saldo informado não substitui conciliação por job nem conversão verificada.

A automação `classifica-o-noturna-das-m-sicas` está ativa neste chat, a cada
15 minutos. O Codex deve permanecer aberto e conectado. O helper local
`data/derived/lyrics/overnight-20261007/keep_awake.py` impede suspensão por até
12 horas, sem modificar o plano de energia. Para liberar o helper ao concluir,
grave `status` como `completed`, `budget_exhausted`, `failed` ou `stopped`.
Registre o motivo e pause a automação; não arquive o chat automaticamente.

A primeira tranche foi submetida ao job Vertex
`projects/186052082420/locations/global/batchPredictionJobs/5040522628733861888`.
Após submissão, compromisso conservador: US$ 598,990865625. Custos conhecidos
continuam separados de reservas; nenhum resultado válido novo foi importado
até esse registro. Ruff e mypy do arquivo alterado passaram.

81 testes unitários das interfaces batch e do contrato Gemini passaram. A
autenticação e o preflight reais passaram. Graphify foi atualizado localmente.
