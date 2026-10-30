# Extração de títulos pela interface web

## Seleção anual limitada — 24/10/2026

A regra vigente do artigo é **até 80 músicas distintas por país/ano**, em ordem
decrescente da soma de reproduções observadas. Spotify tem prioridade quando há
um calendário anual completo; YouTube é a alternativa. Nunca somar streams com
views nem usar totais históricos, posições ou uma captura diária como consumo
anual. Ver `research/annual_top80_spec.md`.

```powershell
.venv\Scripts\python.exe -u scripts/scrape_youtube_chart_titles.py --annual-metrics --workers 2
.venv\Scripts\python.exe scripts/build_annual_top80.py --apply
```

Capturas com views ficam em `data/raw/annual_top80/20261021`. O segundo comando
grava somente a seleção com cobertura completa na tabela `article_annual_top80`,
com posição limitada a 1–80, e em `data/derived/annual_top80/20261021/song_names.csv`.
`selection_manifest.json` informa cobertura incompleta. Nenhuma seleção anual
definitiva é emitida enquanto faltarem semanas ou métricas. O cálculo processa
um país/ano por vez. `watch_web_chart_export.py --annual-top80 --pid PID` atualiza
a seleção no banco a cada cinco minutos e ao término desse coletor.

As capturas antigas e a exportação abaixo são arquivo de apoio, não a seleção
limitada do artigo. Não foram apagadas. O coletor de letras do catálogo amplo e
seus importadores foram pausados; não retomar esses comandos para a nova seleção.

O piloto verificou 100 contagens exatas de views no YouTube BR em 15/10/2026.
YouTube mantém a convenção de ano do fim da semana; isso pode incluir dias da
virada do ano e mede apenas consumo observado nas paradas. Spotify Charts
redirecionou a consulta histórica para login; Kworb expôs totais históricos e
parada atual, sem divisão anual nas páginas inspecionadas. Essa indisponibilidade
está em `source_availability.json`; a preferência Spotify não implica cobertura
Spotify já obtida. Não foram usados endpoints de API nem contornadas autenticações.

O coletor pausa após a captura em andamento quando o disco fica abaixo de 5 GB.
O guardião temporário aceita `-MinFreeGB 8`, removendo apenas arquivos numéricos
antigos e fechados de `.git/lfs/tmp`, antes de atingir esse limite.

Executar na raiz do projeto, com o PostgreSQL configurado disponível:

```powershell
.venv\Scripts\python.exe -u scripts/scrape_youtube_chart_titles.py --workers 2 --retries 1 --apply
```

O coletor descobre os países e as semanas disponíveis de 2025 e 2026 na interface,
prioriza 2026, bloqueia imagens, fontes, vídeos e rastreadores, preserva o cache do
navegador e limita a concorrência. Playwright e Chrome devem estar instalados.
Não executar duas instâncias no mesmo diretório de saída.

Para solicitar pausa sem interromper uma gravação em andamento:

```powershell
.venv\Scripts\python.exe scripts/scrape_youtube_chart_titles.py --pause
```

O comando apenas cria um sinal local. O coletor conclui os acessos em andamento,
salva as capturas, descarrega os lotes pendentes no banco e registra PAUSED.
A pausa só está concluída quando esse estado aparece em `collection_manifest.json`.
Para retomar, execute o comando de coleta original: ele remove o sinal de pausa
e reutiliza as capturas verificadas. Em uma falha interna, o relatório registra
FAILED e preserva a quantidade de importações pendentes para diagnóstico.

Os arquivos verificados são reutilizados na próxima execução. Falhas recebem no
máximo uma tentativa adicional por padrão. A gravação no PostgreSQL usa lotes de
100 capturas e identificadores determinísticos para evitar duplicação ao retomar.
Arquivos capturados antes de uma falha no banco permanecem disponíveis para a
próxima execução. Nenhum processamento de letras ou classificação é iniciado.

Para verificar a cobertura sem navegador, rede ou banco:

```powershell
.venv\Scripts\python.exe scripts/report_web_chart_coverage.py
```

`data/raw/web_chart_titles/20261021/coverage_manifest.json` registra as semanas
faltantes por país e ano. O inventário necessário ao cálculo é persistido na
próxima descoberta pela interface. Sem inventário, o estado permanece PARTIAL.
`collection_manifest.json` registra andamento, erros e linhas inseridas na execução.
O processo retorna código 1 quando terminam as tentativas com falhas de coleta.
Uma execução com `--max-snapshots` pode ser parcial mesmo sem erros.

O ano corresponde ao encerramento da semana nativa da fonte. Os dados representam
o ranking semanal disponível, com o período original preservado. As capturas
diárias do Kworb complementam países disponíveis, mas não representam cobertura
anual e ficam fora do cálculo de cobertura semanal. Artista é preservado apenas
para distinguir músicas homônimas; métricas de reprodução não são coletadas.

Para exportar os nomes já gravados no PostgreSQL:

```powershell
.venv\Scripts\python.exe scripts/export_web_chart_titles.py
```

O arquivo `data/derived/web_chart_titles/20261021/song_names.csv` agrupa título e
artista por país, ano e fonte, com primeiro/último período observado e número de
períodos. Não representa ranking anual nem quantidade de músicas únicas globais.

No Windows, `watch_web_chart_export.py --pid PID_DO_COLETOR` acompanha uma única
execução e atualiza cobertura e CSV a cada cinco minutos, com uma atualização
final quando o processo termina. Não reinicia o coletor nem agenda recorrência.
Consulte `export_manifest.json` para verificar a última atualização.

Estado em 21/10/2026: revisão liberada e extração retomada. A cobertura permanece
parcial até a confirmação de todas as semanas no relatório de cobertura.

## Recuperação e letras — 23/10/2026

O Windows reservou a porta 56433. O mesmo cluster PostgreSQL foi recuperado na
porta 15433, e apenas a porta na conexão local do `.env` foi alterada.

A coleta de letras usa o fluxo já existente:

```powershell
.venv\Scripts\python.exe -u -m chart_observatory.lyrics.lyrics_backfill --workers 2 --skip-gemini --output data/raw/lyrics_recovery/20261023/found.jsonl --completed-from data/derived/lyrics/gemini_annotations.jsonl
.venv\Scripts\python.exe -u scripts/import_lyrics_incremental.py --follow --input data/raw/lyrics_recovery/20261023/found.jsonl
```

Os comandos são processos separados. O segundo acompanha o arquivo JSONL em
lotes de até 500 linhas completas e grava no banco pelo importador existente.
O checkpoint só avança após a confirmação; repetições são idempotentes. Erros de
conexão são repetidos após 60 segundos, sem registrar credenciais. O arquivo
`gemini_annotations.import-checkpoint.json` contém o progresso sem textos de letras.
Um arquivo `gemini_annotations.import-pause` interrompe o acompanhamento após o
lote atual; remova esse sinal e reinicie o importador para retomar.

`--completed-from` lê o corpus histórico para deduplicação sem reescrevê-lo.
As novas capturas ficam em `data/raw`, já ignorado pelo Git, evitando que cada
letra recuperada altere novamente o grande arquivo histórico rastreado no LFS.

A política de `config/lyrics_identity_quarantine.json` suspende LETRAS por risco
de incompatibilidade entre identidade e texto. O coletor agora respeita essa
política tanto na fila de retomada quanto na escolha de fontes: resultados
suspensos ou em quarentena não impedem nova busca nas demais fontes. Originais
são preservados. A pesquisa atual de disponibilidade retornou HTTP 403 para
Letras.mus.br; não foi feita tentativa de contornar esse bloqueio.

O LRCLIB permanece uma alternativa com documentação pública em
https://lrclib.net/docs. Sua consulta passou a usar o mesmo artista principal
utilizado na validação exata, preservando a rejeição de edições divergentes.
Não se diminuiu o critério de identidade para aumentar artificialmente a cobertura.

Na recuperação operacional foram removidos 120 arquivos temporários numéricos
fechados de `.git/lfs/tmp`, liberando aproximadamente 8,8 GB após esgotamento do
disco. Não foram removidos originais da pesquisa nem objetos versionados.
Checkpoints e relatórios repetem substituições atômicas quando o Windows mantém
um bloqueio temporário; o importador também repete erros transitórios de arquivo.

Após liberação de espaço pelo responsável, a proteção temporária de limpeza LFS
foi encerrada. A retomada valida o banco antes de iniciar os coletores. O coletor
de rankings descarrega lotes pequenos após 60 segundos de progresso, além do
limite de 100 capturas e da descarga final. Uma última linha JSONL interrompida
recebe apenas o delimitador de linha na retomada; o fragmento original é mantido,
e as novas letras não são concatenadas a ele. O importador continua rejeitando
fragmentos malformados e preservando os registros completos seguintes.
