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

## Retomada após auditoria — 7 de outubro de 2026

O usuário solicitou expressamente continuar a classificação noturna após ler o
relatório de qualidade. A pausa metodológica foi retirada para a classificação
exploratória; a exigência de validação da amostra científica permanece. Fontes
suspensas, quarentena, direitos, hash e exclusão de resultados válidos/reservas
continuam vigentes. Não se promove resultado da IA a evidência populacional.

O retry anterior `ba5cb6d8-a480-4869-91c5-c7e86fd5474c` foi importado com 200
classificações e nenhum erro individual, custo com telemetria US$ 0,379518375.
O novo retry `840b0dd8-ef79-4f80-b246-22932e0bf158` tem 200 documentos distintos,
sem sobreposição com a tentativa anterior desta noite. Foi submetido ao job
`projects/186052082420/locations/global/batchPredictionJobs/356779016268546048`.
Reserva do novo lote: US$ 0,71669025. Compromisso acumulado após reserva:
US$ 599,36860125; custos conhecidos US$ 129,244997625. O ledger atual do banco
prevalece sobre estes valores históricos para as próximas tranches.

`quality_hold=false`, automação ativa a cada 15 minutos e helper de suspensão
reiniciado por até 12 horas. Consulte `status.json` para IDs, processo e estado
mais recentes. Ao encerrar, regenere a auditoria local para atualizar a tabela de
elegibilidade e proveniência, sem chamadas pagas. O percentual do job atual não
mede a conclusão do corpus inteiro. Confira tentativa única por documento em
todos os `retry_run_ids`, independentemente da baseline de origem.

## Coordenação contínua — orientação operacional vigente

O usuário solicitou remover a tranche fixa de 200. A execução passa a usar
`scripts/run_continuous_lyrics.py`, com consultas a cada 30 segundos e até quatro
jobs simultâneos. O tamanho é calculado pelo saldo/reserva por documento e limitado
a 190.000 requisições por shard; a verificação definitiva do ledger ocorre antes
de uploads e submissões. Se a estimativa não couber, reduz-se a quantidade, sem
repetir uploads. O teto continua US$ 600. A inferência usa a infraestrutura Google;
CPU/GPU local não executam o modelo. Esta seção substitui a orientação de lotes
fixos e o uso do heartbeat como responsável direto por novos envios.

Iniciar em PowerShell a partir do repositório, mantendo a janela escondida:

```powershell
$continuousPython = (Resolve-Path '.venv/Scripts/python.exe').Path
$continuousScript = (Resolve-Path 'scripts/run_continuous_lyrics.py').Path
Start-Process -FilePath $continuousPython -ArgumentList $continuousScript -WindowStyle Hidden
```

O arquivo `continuous.lock` mantém exclusão de processo: iniciar uma segunda
instância não duplica trabalho. `status.json` registra PID, timestamp de atividade,
IDs, estado por run, reserva/custos e totais desta noite. Escritas são atômicas.
IDs preparados são registrados antes da submissão; o flag `submission_attempted`
é salvo antes da chamada. Preparação interrompida ou resultado de submissão
ambíguo interrompem o controlador para inspeção. Nunca relançar cegamente se
`status=failed` ou se `preparation_in_progress` estiver presente. Uma preparação
recusada por orçamento não libera as reservas históricas.

O monitor Codex consulta a cada cinco minutos. Com o controlador vivo, apenas
observa o estado e não prepara/submete/importa em paralelo. Verifique a linha de
comando do PID, não apenas o número. Se ele parar, investigue checkpoints e banco
antes de qualquer recuperação. Estados científicos/quarentena não são removidos.
Jobs já submetidos podem ser reconciliados mesmo após falha do coordenador;
nenhuma submissão ambígua é repetida. Ao concluir/esgotar orçamento, o controlador
recalcula a auditoria local; o monitor pausa o agendamento e informa o resultado.

Para solicitar parada reversível, grave `controller_stop_requested=true` no
estado, com o controlador ocioso. Isso não cancela jobs no Google. Preserve os
IDs e importe resultados pendentes pelo monitor antes de encerrá-lo.

Validação da coordenação contínua: 177 testes, incluindo PostgreSQL real, Ruff e
mypy passaram. O teste de PostgreSQL reproduziu um advisory lock que permanecia
no pool depois de commit. A guarda agora usa conexão física dedicada e suporta
escopos aninhados; a liberação usa a mesma conexão. O teste confirmou concorrente
bloqueado durante a guarda e desbloqueado após sua saída. No Windows, o teste e
uma segunda invocação real confirmaram exclusão de processo sem duplicar jobs.

A primeira rodada contínua calculou lotes de 164 e 1 documento pelo saldo;
rodadas seguintes continuam automaticamente após importações com telemetria.
Os tamanhos pequenos atuais resultam do teto financeiro quase esgotado, não de
um limite fixo de 200. Um erro individual registrado não autoriza retry de retry.
O controlador mantém os snapshots e contagens separados por estado.


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


## Operação vigente: orçamento em reais e corpus completo

A autorização posterior do usuário substitui os tetos USD e permite LETRAS
na classificação exploratória. Consulte [operação BRL](brl-full-corpus-20261008.md)
e `data/derived/lyrics/budget-20261008/billing-policy.json`. Quarentena e
elegibilidade científica permanecem estritas; não usar classificações como
validação da ligação ao ranking ou evidência da população geral.
