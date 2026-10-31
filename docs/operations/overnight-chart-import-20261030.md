# Importação histórica em execução — 2018–2026

Autorização de 30/10/2026: importar as primeiras N músicas de cada país/ano,
respeitando as cotas já calculadas, com processamento durante a madrugada.
O pesquisador confirmou manter **15/10/2026** como corte de 2026.

## Regra congelada

- Janela: **2018–2026**, 68 países, **612 células** país/ano.
- Cotas principais de `country_quotas.csv`, sem expansão: Brasil 230,
  República Dominicana 130, Índia 440; demais países conforme o arquivo.
- Uma plataforma/fonte principal por célula. Somar métricas do mesmo item nos
  períodos observados; nunca somar cópias MGD/Kaggle nem Spotify/YouTube.
- Selecionar as posições de 1 até a cota após recomputar o ranking anual inteiro.
- Calendário incompleto não gera seleção anual definitiva; nenhum período ou
  reprodução ausente é inventado. 2026 é um acumulado parcial.
- Letras ausentes não deslocam a fronteira para posições inferiores.
- Se a união ultrapassar a meta de 30 mil candidatos, conservar a importação dos
  metadados e bloquear aquisição/classificação até revisar o volume. Não reduzir
  automaticamente as cotas. Esta execução não aciona aquisição de letras ou Gemini.

## Fontes efetivamente acionadas

1. MGD e Kaggle/Dhruvil locais: materializados anteriormente, com a precedência
   e agregação registradas no cálculo de 30/10. Mantidos como fontes candidatas;
   não baixados novamente como se fornecessem datas além de seus arquivos.
2. [Arquivo público Zenodo 23645386](https://zenodo.org/records/23645386):
   arquivos anuais YouTube Top Songs e Spotify Top 200, 2018–2026, além dos
   pacotes brutos e README. Downloads conferem tamanho e MD5 publicado;
   SHA-256 local adicional. O autor documenta YouTube semanal de 43 países
   desde maio de 2018. Isso não constitui um calendário completo de 2018.
   Spotify é amostrado a cada quatro semanas na maioria dos países; tal
   amostragem permanece incompleta no relatório, sem extrapolação.
3. [Kaggle/Gonzalo López Gil](https://www.kaggle.com/datasets/gonzalopezgil/spotify-charts-daily-updated),
   **versão 151**, publicada em 30/10: `charts_songs_daily.csv`,
   11.071.427.195 bytes, com data, país, posição, URI, título, artistas e streams.
   A descrição anuncia Top 200 diário. Completude será verificada nos registros,
   não inferida da descrição. Versão fixada para impedir troca durante a retomada.
4. YouTube web já coletado: preservado no snapshot anterior e comparado às novas
   fontes por calendário, cobertura e profundidade.

O endereço enviado como Chartmetric é do **Kworb**. Foram verificados ao vivo
`/spotify/country/br_daily.html` e `/spotify/country/br_daily_totals.html`.
O primeiro mostra um dia; o segundo soma o histórico inteiro. Não foram usados
como ranking de um ano. A API Spotify comum não fornece automaticamente esse
histórico de charts. Nenhum serviço pago Chartmetric foi contratado/acionado.

## Processo e acompanhamento

Orquestrador: `scripts/run_overnight_chart_import.py`.
Downloads paralelos de dois provedores; arquivo Kaggle usa quatro conexões
limitadas com faixas de 64 MiB. CSV bruto é normalizado para Parquet em streaming.
Agregação usa dois threads e processa um ano por vez.

Processo lançado em segundo plano, com janela oculta. Não depende de terminal
PowerShell aberto. Suspensão/desligamento interrompem o trabalho; a retomada
reaproveita os bytes completos já baixados.

Estado corrente e logs:

```powershell
Get-Content data/runtime/overnight-chart-import-20261030/status.json
Get-Content data/runtime/overnight-chart-import-20261030/execution.log -Tail 20
```

Saídas finais:

- `data/runtime/overnight-chart-import-20261030/result.json` — totais e lacunas.
- `data/derived/annual_revision/backfill-2018-2026-20261030/sources/` —
  Parquet de observações Kaggle, ranking recomposto e cobertura das fontes.
- `data/derived/annual_revision/backfill-2018-2026-20261030/selection/` —
  selecionados, cobertura das 612 células e candidatos à recuperação de letras.
- Banco local: novo snapshot imutável em `quota_import_runs` e
  `quota_import_memberships`, sem substituir snapshots anteriores.

Para retomar após falha/interrupção, iniciar primeiro o servidor local e rodar:

```powershell
. .\scripts\research_environment.ps1
uv run --frozen python -u scripts/run_overnight_chart_import.py
```

Um lock de arquivo impede dois orquestradores simultâneos. Não iniciar coletores
avulsos contra os mesmos arquivos enquanto o orquestrador estiver ativo.
O download mantém arquivos `.part` e faixas completas; não apagá-los para retomar.
Se o estado for `failed`, conferir o erro e os logs antes de repetir.

## Verificação antes de deixar rodando

34 testes de ingestão passaram, incluindo calendário exato, deduplicação por
item/período, conflitos de métricas, precedência de fontes e persistência
idempotente. Ruff passou. Os dois downloads foram observados em andamento,
com estado persistente `running` e ambos os processos filhos ativos.

Este registro confirma **início**, não conclusão da importação histórica.
O resultado só será completo para as células que satisfizerem calendário e cota.
