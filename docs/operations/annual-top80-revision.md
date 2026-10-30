# Correção da seleção anual — 24 de outubro de 2026

A revisão histórica deve selecionar 80 gravações distintas por mercado de
circulação e ano, antes de avaliar disponibilidade de letras e classificações.
Mercado não significa nacionalidade do artista. A etapa histórica termina em
2025; a janela de 2026 será especificada na etapa posterior.

O protocolo `annual-observed-streams-top80-v1` soma streams de paradas diárias
Spotify dentro de cada país/ano. Usa um fornecedor por célula: maior número de
dias observados, depois maior número de observações e, em empate, nome do
fornecedor em ordem alfabética. Não soma fornecedores espelhados nem períodos
semanais com diários. Empates de streams usam o identificador Spotify.

Este é um ranking de streams observados nas paradas disponíveis. Cobertura de
menos dias que o ano calendário deve aparecer como parcial, mesmo com 80 músicas.
Sem dados suficientes, a célula tem déficit explícito, nunca preenchimento
artificial. Sem letra validada, a posição continua pendente: não entra a 81ª
música para esconder a ausência. Países/anos ausentes no intervalo histórico
aparecem no relatório de cobertura.

A fila percorre primeiro as posições 1 de todos os países/anos, depois as
posições 2, até 80. Desempates de agendamento usam país e ano. Uma gravação
compartilhada é adquirida uma vez, preservando suas associações com as células.
A submissão de requisições segue essa ordem; respostas podem concluir fora de
ordem pela concorrência. Identidades canônicas ambíguas permanecem pendentes.

Comando reproduzível, sempre com um diretório de saída novo:

```powershell
.\.venv\Scripts\python.exe scripts/build_annual_top80_revision.py --output data/derived/research_quality/annual-top80-20261024
```

Artefatos: `annual-top80.parquet`, `annual-top80.csv`,
`country-year-coverage.csv`, `recovery-targets.jsonl`, `manifest.json`.
O manifesto registra hashes das entradas, protocolo e contagens. O pacote
anterior do artigo permanece congelado. A nova seleção substitui a seleção ampla
da revisão; o artigo só poderá ser regenerado após as validações já previstas.

Verificações: limite de 80 por célula, prioridade de streams, duplicação diária,
escolha de fornecedor, conflitos de valores e desempates reproduzíveis.
