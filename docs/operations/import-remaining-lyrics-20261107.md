# Continuação da recuperação — 07/11/2026

Conferência às 10h48 BRT: campanha anterior encerrada normalmente às 1h25,
com aquisição, staging e auditoria retornando código zero. Seleção preservada:
28.373 candidatos, 25.495 com texto e 2.878 sem texto local. O snapshot final
é `fcab318e321b8c3fc4e4fb5a080c77f1d2596f372e3052ed88be21a2fa7a4c74`.

Há 990 candidatos com texto e alertas no screening (693 pending_adjudication,
250 identity_conflict, 47 suspected_partial). Todos os textos continuam sujeitos
à validação humana, mesmo os sem alertas. Uma das músicas sem texto também está
sem metadados suficientes; não foi inventada identificação.

As recusas anteriores incluem edições divergentes LRCLIB, declaração de letra
incompleta Genius e respostas Musixmatch 202/404/405. Não havia pausas ativas na
conferência inicial. Na retomada houve resposta 429 Genius, com pausa persistente
respeitada; verificar o prazo atual no cache de cooldowns, não deduzir de logs antigos.

Continuação efetivamente iniciada às 10h52, sem outro coletor em execução:

```powershell
.\.venv\Scripts\python.exe scripts/import_all_quota_lyrics.py --state-root data/runtime/import-all-lyrics-20261107 --hours 12 --candidate-ids-file data/runtime/import-all-lyrics-20261107/missing-candidates.jsonl --search-cache-max-age-hours 6
```

O filtro contém somente os 2.878 candidatos sem texto. Os 25.495 existentes são
preservados. A seleção/cotas não mudam; staging e auditoria continuam abrangendo
toda a seleção. A nova execução termina, no máximo, em 07/11 às 22h52 BRT,
sem autorização de chamadas pagas ou aprovação automática de completude.

Buscas LRCLIB/Genius com mais de seis horas podem ser atualizadas em cache
separado. Respostas e blobs antigos ficam intactos; páginas/textos já obtidos
continuam reutilizáveis. Cooldowns são compartilhados com o cache original:
atualizar busca não contorna 429, controle de acesso ou pausa de fonte.

A importação intermediária também foi retomada em processo independente,
reutilizando o checkpoint do snapshot final anterior. Estados e logs atuais:
`data/runtime/import-all-lyrics-20261107/`, especialmente `acquisition/status.json`
e `validation-updates/status.json`. Não usar os PIDs/status da campanha encerrada.

Verificação: 68 testes de aquisição/descoberta/campanha/filtro/atualização passaram,
incluindo cache antigo preservado, atualização de buscas e respeito ao cooldown.
Ruff passou. Processos de supervisor, coletor e atualização foram observados vivos;
tentativas novas e respostas HTTP novas foram registradas, sem classificação Vertex.
