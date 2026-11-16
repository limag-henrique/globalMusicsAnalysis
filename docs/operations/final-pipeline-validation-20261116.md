# Verificação local da entrada consolidada — 16/11/2026

## Execução observada

- Seleções históricas preservadas: v4, 90.600 posições de 277.650; v5,
  91.480 de 277.650. São versões distintas, não uma soma de cobertura.
- Rankings atuais coletados: 13.975 posições Spotify em 71 mercados e 5.001
  posições YouTube em 50 mercados. A antiguidade das fontes foi conferida.
  Páginas antigas, indisponíveis e profundidades inferiores a 200 ficaram
  explicitamente pendentes no relatório.
- Catálogo conjunto: 37.291 candidatos; 29.110 com texto referenciado.
- A integração acrescentou 25.079 referências aos runs imutáveis do staging.
  Não duplicou seus corpos de letras nem o banco PostgreSQL.
- Conferência executada com `lyrics --limit 0 --audit-limit 100`: cem textos
  auditados, 85 com integridade do campo/identidade do provedor aprovada,
  quinze pendentes e 29.010 textos ainda não auditados por esta execução.
  A seleção foi determinística, não uma amostra aleatória; não se extrapola
  esse resultado para o corpus. Nenhuma aprovação científica foi concedida.
- Vertex: contrato local produzido; zero requests executáveis, zero uploads
  e zero inferências. Faltam auditoria G3 e requests aprovados correspondentes.
- Catálogo novo compactado de 212,69 MiB para 120,63 MiB. As bases anteriores,
  o PostgreSQL externo e as saídas do AntiGravity foram preservados.

## Verificação de software

Passaram 50 testes dos arquivos `test_final_pipeline.py`,
`test_research_vertex_payload.py` e `test_research_contract.py`.
Ruff passou nos arquivos novos. Os testes incluem bloqueio de escritor
concorrente, rejeição de rankings antigos/futuros e posições inconsistentes,
rejeição de texto corrompido, referência ao staging sem cópia, alteração de texto
canônico antes do preparo, limite cumulativo e idempotência da preparação.
Não foi executada a suíte inteira do projeto.

## Artefatos operacionais

Os relatórios e filas atuais estão em `data/runtime/final-pipeline/`:
`rankings-report.json`, `lyrics-report.json`, `lyric-review-queue.jsonl`,
`vertex-report.json` e `vertex/704230540e0240f7b04428a88e504d92/`.
Dados privados não são incluídos nesta documentação versionada.

A implementação fornece uma entrada consolidada; estes resultados ainda não
constituem conclusão científica do projeto. Permanecem as lacunas históricas,
as fontes atuais indisponíveis, a auditoria integral das letras e os gates de IA.
