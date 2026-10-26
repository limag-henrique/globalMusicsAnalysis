# Dados compactados no Git

O Git recebe os snapshots `.csv.gz`; os CSVs e o JSONL de trabalho ficam locais.
Os coletores, importadores, checkpoints e relatórios continuam usando os mesmos
caminhos. Nenhum dado local é apagado pela migração.

Após clonar, ou após receber novos snapshots, execute antes dos pipelines:

```powershell
python scripts/sync_git_data.py restore
```

Antes de adicionar alterações de dados ao Git:

```powershell
python scripts/sync_git_data.py pack
python scripts/sync_git_data.py verify
```

`pack` exporta os CSVs listados no manifesto e os CSVs ainda versionados, mais
`gemini_annotations.jsonl`. Novos CSVs de trabalho precisam ser incluídos
explicitamente com `pack --include caminho/arquivo.csv`.
Pastas de dados brutos já ignoradas continuam privadas e não são descobertas
automaticamente. O manifesto `data/git-data-manifest.json` registra caminhos,
formatos, tamanhos e SHA-256. A compactação gzip é determinística.

CSV existente é compactado byte a byte. O JSONL vira CSV de uma coluna,
`record_json`, que contém o registro original completo, inclusive sua quebra de
linha. Isso preserva campos aninhados, tipos, textos e a representação original;
não é uma tabela analítica achatada. A restauração recupera os bytes originais.

`restore` recusa sobrescrever arquivos locais diferentes do snapshot. Nesse caso,
exporte ou guarde suas alterações antes de receber dados de outra máquina.
Pare escritores ativos durante `pack`; ele recusa fontes modificadas durante a
exportação. `verify` testa a descompactação e os hashes de todos os snapshots sem
modificar dados de trabalho. Arquivos compactados a partir de 95 MiB são recusados.

Os snapshots usam Git comum, com `-filter` explícito em `.gitattributes`.
Esta migração não reescreve histórico nem remove objetos LFS antigos do servidor.
Liberar a cota remota exige uma operação administrativa separada.
