# Importação integral da seleção para validação

Campanha iniciada em 06/11/2026, 22:53 BRT, para os 28.373 candidatos da seleção
congelada 2018–2026. Reutiliza os 22.293 candidatos com texto e recupera ausentes
ou suspeitos. Não amplia cotas, não classifica com IA e não certifica completude.

Execução independente: `scripts/import_all_quota_lyrics.py`, iniciada com janela
oculta, com subprocesso de aquisição efetivamente observado em `recovering`.
O supervisor mantém o handle do coletor e executa staging e auditoria final após
seu encerramento. Prazo máximo de despacho: 07/11/2026, 22:53 BRT. Não é uma
promessa de disponibilidade de todas as letras nem um agendamento de reboot.

Estado e logs: `data/runtime/import-all-lyrics-20261106/`.

- `campaign.json`: prazo e hashes das entradas congeladas, zero chamadas pagas.
- `backup.json`, `acquisition-before.sqlite`: backup consistente da aquisição.
- `status.json`: estágio do supervisor.
- `acquisition/status.json`: estágio/counters reais do coletor.
- `acquisition/process.json`, `exit.json`: PID, comando e término do processo.
- `staging/status.json`: snapshot resultante, quando essa fase terminar.
- `final-audit/summary.json`: disponibilidade e pendências posteriores.

Não executar dois coletores simultâneos. Há locks de supervisor e de escritor
da aquisição; cooldowns persistentes e rate limits continuam em vigor.
Textos anteriores e histórico de tentativas são preservados. Fontes que declaram
trechos incompletos, metadata divergente ou edições conflitantes não são
transformadas em letras verificadas. As pendências continuam visíveis.

Para retomar após falha, conferir processos vivos e logs antes de usar o mesmo
comando. O prazo não é estendido automaticamente; o manifesto antigo de novembro
foi preservado, e a nova campanha usa um override restrito ao subprocesso.

Verificação antes do início: 63 testes de campanha/supervisor/aquisição/descoberta
passaram; Ruff passou nos três arquivos desta alteração. O supervisor também foi
testado com um subprocesso real offline. Não houve chamada Vertex.
