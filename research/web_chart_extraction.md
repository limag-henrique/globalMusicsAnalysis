# Extração de títulos pela interface web

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
