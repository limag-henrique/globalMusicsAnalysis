# Recuperação da classificação contínua

Escopo confirmado pelo usuário: reparar a gravação pública `write_state` e testar
o comportamento sob bloqueio temporário de leitura no Windows, antes da retomada.

O checkpoint deve continuar sendo substituído atomicamente. Um leitor que impede
exclusão por pouco tempo não deve encerrar o controlador. Tentativas limitadas de
gravação podem repetir somente a substituição local, nunca preparação, upload ou
submissão. Bloqueio persistente deve preservar o checkpoint anterior e propagar
o erro, impedindo novos envios. O marcador independente de parada permanece ativo.

Teste na interface acordada: leitor real do Windows sem compartilhamento de
exclusão, liberação após uma tentativa comprovadamente bloqueada, seguida de
leitura do checkpoint completo; outro cenário mantém o bloqueio e verifica a
preservação do checkpoint anterior. Não há mudança de modelo ou de taxonomia.

A retomada operacional exige Docker e PostgreSQL 16 em 127.0.0.1:56433,
reconciliação de todos os runs e ausência de submissão/preparação ambígua.
O saldo autenticado de 10/10 é R$591,60 na conta original; preços de outubro
continuam válidos até 01/11. Preservar reservas e histórico cumulativo.
Créditos da segunda conta só entram após vínculo verificado e troca humana.

Não publicar issue: este reparo local não requer comunicação externa.

## Redução de leitura financeira

O usuário também confirmou reduzir as colunas lidas na conferência financeira,
testando a interface `cumulative_cost_commitment` (pela proteção de custo
existente). Não se usa cache nem se dispensa reconstrução de hashes/bytes.
Snapshots contribuem apenas identidade e custo; o documento contribui texto,
identidade, hash e idioma. Payloads de resposta e metadados permanecem intactos.

Medição local no mesmo lote de 14.051 documentos: leitura anterior 15,86 s,
leitura reduzida 5,84 s; compromisso idêntico 26,6983020000 no ledger canônico.
As medições sequenciais não controlam o cache, portanto não provam ganho universal.
O teste verifica também que hash divergente conserva a reserva integral.

A auditoria de retomada registra 159.111 documentos, 204.493 snapshots,
103.410 documentos com classificação mais recente válida e 54.188 com erro.
Os 12 jobs da execução atual foram integralmente importados. Os runs históricos
terminais também têm todos os itens reconciliados e resumo durável; não repetir
finalização apenas por terem estado histórico `failed` ou `succeeded`.

A política atual mantém a baseline de crédito anterior conservadoramente:
R$153,20 podem ser comprometidos, além de R$111,76 para novas tentativas,
R$35 de acessórios e R$35 de margem para atraso de faturamento. O compromisso
global de R$1.169,95 inclui R$0,70748 de custo desconhecido ainda reservado.
O saldo observado de R$591,60 não libera nenhuma dessas reservas.
