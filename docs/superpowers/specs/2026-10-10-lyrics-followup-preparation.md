# Preparação local da chamada posterior

Usuário autorizou preparar a próxima chamada após a execução atual, com planejamento
separado de reanálise dos textos corrigidos. Testar o comando público de preparação:
seleção, jobs ativos, tentativas e orçamento BRL.

- Controlador vivo exclusivo; sem uploads/submissões, reservas no banco ou alteração
  de checkpoint, política financeira e originais.
- JSONL privado local, UUIDv4, hashes e manifesto prévios à eventual submissão.
  JSONL é rascunho, não job reservado/submetido.
- Pendentes: sem resultado válido, erro técnico individual permitido ou sem snapshot;
  tentativa disponível na execução original. Novo hash/ID não zera tentativas.
- Reservas ativas, preparação/submissão ambígua, job global não reconciliado,
  reanalysis_run_ids e duas tentativas impedem nova tentativa técnica.
- Resultado válido com texto corrigido vai exclusivamente ao plano separado de
  reanálise. Planejamento não autoriza despesa nem altera a whitelist vigente.
- Preservar direitos, hashes e proveniência. Texto vazio, muito curto, provável
  fragmento ou exclusão conhecida continua impedindo uma nova chamada.
- gemini-3.8-flash, LOW, 1024, prompt/taxonomia vigentes, seleção científica estrita.
- Reserva BRL por bytes completos de JSONL mais 1024 tokens de saída, somente SKUs
  autenticados. Sem câmbio arbitrário, liberação de reserva ou crédito não verificado.
- Antes de envio: controlador encerrado, estado terminal seguro, runs reconciliados,
  filas reconsultadas, crédito/vínculo/SKUs atuais e BrlBudgetPolicy.guard em todos os
  uploads/submissões. Comando não oferece upload/submissão nem autoridade de gasto.
- Repreparar depois do término em diretório novo; resultados atuais podem invalidar
  os rascunhos. PostgreSQL 16 em 127.0.0.1:56433, somente leitura e snapshot consistente.
