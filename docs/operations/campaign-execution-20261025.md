# Campanha de revisão: preparação e limites

Todos os arquivos de trabalho, caches, bancos locais, relatórios e temporários
devem permanecer fisicamente em `D:\PromiscuidadeMusical`. Não transferir arquivos
para C: por falta de espaço; interromper a etapa e registrar a insuficiência.
As configurações estão em `config/revision_campaign_budget.json`.

O teto global é US$180: piloto 10, principal 110, revisão 25, serviços 10 e
contingência 25. Anos de 2017 a 2026 compartilham a verba principal. Reservas de
lotes são atômicas e idempotentes; custos desconhecidos bloqueiam novos envios.
A declaração do pesquisador sobre ausência de despesas externas foi registrada.
O banco do provedor está indisponível: saldo utilizável permanece zero, e os
zeros do livro local não certificam ausência de custos históricos.

Entrada: `.venv/Scripts/python.exe scripts/revision_pipeline.py`.
Uma etapa isolada pode ser executada com `--only recuperar_letras`; a retomada
da coleta exige `--resume-collection`. Sem essa opção, o comando apenas audita.
`--through preparar_piloto` limita a sequência. Alterações de controle, código,
cobertura e insumos invalidam apenas os estados afetados. Um pacote isolado não
inclui diagnósticos antigos que não foram recalculados nesta execução.
Estado, hashes e relatórios ficam em `data/derived/annual_revision/runtime`.
O comando prepara e audita; não autoriza inferência paga. A migração do despacho
pago para a assinatura textual completa ainda não está concluída. Os bloqueios
de identidade, integridade, avaliação humana, piloto, preços e reconciliação
impedem a execução científica definitiva. O pacote atual contém apenas métodos,
critérios e diagnósticos agregados, sem letras ou resultados corrigidos.

Fluxo primário: diagnóstico de falhas e verificação de regressão. Validação:
124 testes relevantes passaram: 67 de orçamento, lotes, classificação, retomada
e rankings; 53 de seleção e protocolos; quatro do ponto de entrada, pacote e
armazenamento. Temporários permaneceram no D:. Ruff passou. A política de
branches e commits foi preservada. A conferência da migração de armazenamento
está registrada em `data/runtime/session-20261025/all-files-on-d-summary.json`
quando concluída; seu inventário SHA256 está no arquivo JSONL adjacente.

Armazenamento concluído: 47.447 arquivos têm correspondentes preservados no D:.
Os 576 arquivos fora do cache foram conferidos por SHA256. As 46.871 cópias
descartáveis do cache foram conferidas por tamanho e data exata contra os
originais, que nunca saíram do D:; houve ainda 31.423 verificações adicionais por
hash. O inventário final discrimina os métodos. As cópias desta sessão no C: e
as duplicatas transitórias criadas durante a conferência foram removidas.

A coleta convencional foi retomada com dois trabalhadores. No checkpoint,
2.397 de 5.114 documentos tinham resultado processado; 2.717 estavam pendentes.
Textos recuperados são candidatos, não validações. Estado e contadores podem
ser consultados reexecutando o comando; `running` não significa conclusão.
Os testes dos seletores estão registrados com hashes em `test-receipt.json`.
A reconciliação do provedor, identidade, integridade, avaliação independente e
aceitação do piloto permanecem pendentes. Nenhuma chamada paga foi realizada.
