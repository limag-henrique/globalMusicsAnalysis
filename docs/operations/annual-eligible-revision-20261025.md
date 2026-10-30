# Preparação anual e recuperação — 25/10/2026

Extensão posterior: as regras de identidade, assinatura completa e piloto foram
detalhadas em `identity-rubric-pilot-20261025.md`. A compatibilidade baseada apenas
em modelo, taxonomia e prompt não autoriza reutilização no novo protocolo v2.

Branch mantida: `main`. Nenhum commit, chamada paga, alteração de banco ou
regeneração do artigo. Preservadas as alterações que já existiam no projeto.

Saída vigente: `data/derived/annual_revision/20261025-final/`.
Os diretórios `20261025` e `20261025-prepared` são estágios anteriores preservados.

## Inventário observado

- Histórico recontado: 30.160 posições, 377 células país/ano, 8.530 alvos na fila
  histórica. Há 172 células Spotify com calendário anual completo e 205 parciais.
- Seleção recente recontada: 7.840 posições em 98 células, todas YouTube.
- O manifesto bruto ainda contém 924 registros de falha; isso não comprova que
  sejam 924 períodos distintos ainda ausentes. A cobertura efetiva está no CSV.
- Novo universo: 108.006 associações de candidatos, incluindo reservas e janelas
  equivalentes; 19.786 identidades de candidatos. Estas não são necessariamente
  19.786 gravações canônicas: vínculos entre plataformas continuam pendentes.
- Para a aquisição inicial: reutilizados 5.333 candidatos já recuperados e 236
  buscas sem resultado. As perdas conhecidas acionam reservas sequenciais em
  359 células. Há 5.114 alvos novos ou com erro transitório para recuperação.
- Outras 9.103 identidades ficam adiadas por reserva ainda desnecessária ou
  cobertura incompleta. Não são excluídas do inventário.
- Zero letras elegíveis e zero itens para classificação sob o novo contrato.
  Isso registra ausência de evidência aceita/reconciliação, não prova que todas
  as letras históricas estejam erradas.

O PostgreSQL local em 15433 não respondeu. O daemon Docker também está ausente;
não foi iniciada infraestrutura adicional na máquina com pouca RAM disponível.
Contagens históricas do banco e vínculos atuais não foram certificados nesta execução.

`inventory-summary.json` registra contagens, recursos e hashes dos artefatos.
`country-year-platform-coverage.csv` inclui o calendário de todos os 68 mercados,
2017–2026, por plataforma e janela. Ausência de dados não vira um ranking completo.
`inventory-by-country-year-platform.csv` contém 2.584 linhas com as janelas,
contagens de candidatos, posições originais e estados de aquisição. Identidade
canônica e classificações aparecem como `DATABASE_UNAVAILABLE`, sem confundir
falta de reconciliação com contagem zero de documentos existentes.

## Janelas e seleção

Anos completos: 2017–2025. Corte parcial efetivo: 15/10/2026, última semana
disponível no inventário até o corte solicitado de 21/10. Comparações equivalentes
terminam em 15 de outubro de cada ano. Semanas pertencem ao ano de encerramento;
não são repartidas. As datas delimitam calendários; não garantem dados disponíveis.

Dois adaptadores existentes alimentam o mesmo contrato de elegibilidade:
`annual_cohort.py` para observações diárias Spotify e `annual_selection.py` para
capturas semanais. Os comportamentos antigos continuam sendo o padrão para os
chamadores históricos. O novo preparo solicita reservas de 120 e ambas plataformas.

`original_top80.jsonl` conserva as posições originais e os motivos de pendência.
`eligible.jsonl` contém somente as melhores 80 gravações validadas por célula.
`coverage.jsonl` contabiliza perdas, reservas e déficits nas células com candidatos.
O CSV de calendários também inclui células sem nenhum candidato.

## Recuperação convencional em andamento

O piloto de cinco alvos terminou com cinco candidatos, todos pendentes de validação.
Foi iniciado um processo oculto, com dois trabalhadores, para a fila de 5.114 alvos.
Seu PID, comando e horário estão em `acquisition/process.json`. Consulte o processo
e os logs: o registro de início não prova que ele continua ativo.

O coletor usa LRCLIB e scraping do Genius, sem IA; reutiliza o cache anterior,
mantém variantes e proveniência, e não importa automaticamente. Não se considera
nenhum desses provedores uma certificação da transcrição original. Uma busca sem
resultado já executada na mesma estratégia não é repetida a cada preparação;
as reservas absorvem essa perda sem esconder a posição original.

```powershell
.venv/Scripts/python.exe scripts/report_lyrics_recovery.py --targets data/derived/annual_revision/20261025-final/recovery-targets.jsonl --ledger data/derived/annual_revision/20261025-final/acquisition/acquisition.jsonl --output data/derived/annual_revision/20261025-final/acquisition/progress.json
```

Após confirmar que o processo terminou, é possível retomar o mesmo coletor,
diretório e cache usando o comando registrado em `process.json`. Não iniciar
um segundo escritor simultâneo no mesmo ledger.

## Validação antes do Vertex

A evidência JSONL deve registrar `candidate_id`, `recording_id`, `document_id`,
`lyrics_hash`, `identity_verified`, `integrity_verified`, `method`, `evidence_url`,
`evidence_sha256` e `verified_at`. Métodos aceitos: `official_transcription` ou
`human_audio_verification`. Registrar uma decisão real e sua evidência; nunca
preencher esses campos como verdadeiros a partir de concordância entre sites.

Os vínculos são conferidos contra os documentos atuais do banco, respeitando
direitos, fontes suspensas e bloqueios de revisão. Evidências duplicadas ou com
hash divergente não liberam o texto. Na ausência do banco, o preparo falha fechado.

Para reaproveitar os rankings sem repetir o processamento de paradas:

```powershell
.venv/Scripts/python.exe scripts/prepare_annual_revision.py --output data/derived/annual_revision/NOVA-SAIDA --rankings-from data/derived/annual_revision/20261025-final
```

Com `--validations`, informar também `--model-id`, `--taxonomy-version` e
`--prompt-version`. Classificações existentes só são reaproveitadas quando o
contrato e o hash coincidem. O preparo não envia a fila ao Vertex.

Usar `--candidate-limit 200` para reconstruir uma reserva ampliada quando as
perdas comprovadas exigirem; ampliar não transforma cobertura parcial em completa.

## Verificação

Fluxo principal: `diagnosing-bugs`; alinhamento e critérios registrados em
`research/annual_eligible_revision_spec.md`. Testes de regressão verificam as
fronteiras de seleção, integridade, deduplicação e retomada. Testes locais não
certificam a correção de transcrições musicais reais.

Verificação final: 41 testes passaram; Ruff passou. `graphify update . --no-cluster`
concluiu sem IA, com 27.538 nós e 39.710 arestas; preservou nós históricos que
saíram da enumeração em vez de removê-los automaticamente.
