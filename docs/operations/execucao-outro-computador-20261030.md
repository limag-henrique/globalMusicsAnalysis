# Execução em outro computador: transferência, importação e Gemini

Atualizado em 30/10/2026. Destino previsto: Windows com Codex instalado, sem ambiente Python/PostgreSQL preparado. Este guia rege a nova fase de cotas variáveis e teto de **US$150**. Documentos de campanhas anteriores com Top 80, US$180, US$300 ou US$600 são históricos e não definem a nova execução.

## Resumo para começar

1. Na origem, pausar os escritores, preparar um snapshot do projeto e um dump lógico do banco. Levar código atual, dados ignorados pelo Git, cotas, fontes, caches úteis e checkpoints por pendrive. Conferir SHA-256 no destino.
2. No destino, instalar Git, uv/Python 3.12, Docker Desktop/WSL2, Google Chrome e Google Cloud CLI. Criar uma `.venv` nova e autenticar ADC novamente.
3. Restaurar o dump em **banco novo** e reconciliar o snapshot do banco com os arquivos e registros de custos. Código no GitHub, CSVs, bancos SQLite auxiliares e dump PostgreSQL têm papéis diferentes; nenhum substitui automaticamente os demais.
4. Adaptar e testar os importadores para consumir as cotas por país/ano. Recoletar apenas lacunas de fontes gratuitas verificadas, recomputar o ranking anual e importar a seleção de forma idempotente.
5. Recuperar letras dos selecionados, confirmar gravação/versão e integridade textual, preparar o piloto e a validação. Manter pendências sem inventar letras ou substituir sucessos silenciosamente.
6. Conectar a fila validada ao executor Gemini com assinatura completa, retomada e limite financeiro cumulativo. Começar por teste mínimo e piloto; ampliar com custo real conhecido. A meta principal é até 30 mil identidades candidatas, não gastar US$150.

**Estado real do software:** a transferência e o ambiente podem ser preparados agora. A seleção variável e o despacho pago do protocolo novo ainda exigem implementação. `revision_pipeline.py` prepara/audita, mas não realiza a classificação paga; a etapa tem bloqueio explícito no código. Alterar apenas um campo de configuração não integra o novo fluxo. Não usar o classificador legado do catálogo inteiro como atalho.

## 1. O que transferir por pendrive

Para cópia manual, a origem é `D:\PromiscuidadeMusical`. Levar `src`, `scripts`, `config`, `tests`, `docs`, `research`, `outputs` e `data`, junto com os arquivos de configuração da raiz. Em `data/backups`, levar separadamente os dumps escolhidos e seus registros, sem copiar VHDX/volumes Docker. Em `data/recovery`, as ferramentas instaladas podem ser recriadas; preservar eventuais dados/evidências de recuperação. As exclusões e o comando de pacote abaixo evitam carregar histórico Git e instalações desnecessárias.

Transferir uma cópia do diretório de trabalho atual, incluindo alterações ainda não presentes no GitHub. O `.gitignore` não transporta arquivos ignorados e não reduz o histórico remoto já existente. Esta transferência não requer commits, pushes, troca de branch ou reescrita do Git.

| Conteúdo | Motivo |
| --- | --- |
| `src/`, `scripts/`, `config/`, `tests/`, `docs/`, `README.md`, `pyproject.toml`, `uv.lock`, `.python-version`, `compose.yaml`, `alembic.ini` | Código e configuração efetivamente usados, inclusive arquivos novos ainda não enviados ao GitHub |
| `research/`, especialmente os cálculos e fontes de 30/10 | Metodologia, população, diversidade e reprodução das cotas |
| `data/raw/`, `data/normalized/` | Capturas com proveniência e histórico de rankings; não são recriados por um clone |
| `data/derived/research_quality/import-quotas-20261030/` | Cotas, 680 células país/ano, rankings intermediários e listas nominais |
| `outputs/annual-import-quotas-20261030/` | Planilha e CSVs de entrega das cotas |
| `data/derived/annual_revision/`, inclusive registries SQLite, runtime e ledgers | Identidades, validações, reservas, estados e prevenção de repetição paga |
| `data/derived/lyrics/` e caches de aquisição usados pela revisão | Letras e respostas já recuperadas, erros, evidências e checkpoints |
| Dump PostgreSQL em formato custom (`.dump`) e informações de origem/data | Banco histórico, vínculos, documentos e classificações persistidas |

Levar os diretórios de dados restantes que sejam insumos de manifestos ou relatórios referenciados. Preservar caminhos relativos. Levar o `.gitignore` como configuração, mas não esperar que dados ignorados apareçam no clone.

Recriar no destino: `.venv`, programas instalados, caches descartáveis, instalação de navegadores e autenticação. O pacote não precisa de `.git`, objetos LFS, `node_modules`, ferramentas PostgreSQL antigas, VHDX Docker ou outro ambiente virtual. Não transportar `.env`, tokens ADC, chaves privadas ou o perfil de autenticação do Google; recriar configurações locais e login. Manter o pendrive e os dados privados de letras e banco sob controle do responsável.

### Preparar o snapshot de arquivos

Antes do pacote, concluir o lote em andamento e pausar escritores de banco, JSONL e SQLite. Um PID copiado para outro computador não identifica o mesmo processo. Manter a máquina antiga sem escritores durante a migração e usar apenas um computador como proprietário da nova execução.

O scraper anual aceita uma pausa entre capturas:

```powershell
Set-Location 'D:\PromiscuidadeMusical'
uv run --no-sync python scripts/scrape_youtube_chart_titles.py --annual-metrics --pause
```

Conferir o estado e os logs do coletor; `PAUSE_REQUESTED` sozinho não comprova encerramento. Outros escritores precisam de encerramento no limite de lote correspondente. Para SQLite, copiar após fechar os escritores; se isso não for possível, produzir snapshot pela API de backup SQLite, em vez de copiar só o `.sqlite` e perder o WAL.

Exemplo de pacote `.tar`, sem compressão adicional dos Parquet/gzip já compactados. O diretório `data/backups` é excluído para não incluir o próprio pacote nem VHDX antigos:

```powershell
$projectRoot = (Resolve-Path '.').Path
$transferDir = Join-Path $projectRoot 'data\backups\transfer-20261030'
New-Item -ItemType Directory -Path $transferDir -Force | Out-Null
$projectArchive = Join-Path $transferDir 'projeto-dados.tar'
if (Test-Path -LiteralPath $projectArchive) { throw 'O pacote já existe; escolha outro diretório de transferência.' }
tar -cf $projectArchive -C $projectRoot --exclude='./.git' --exclude='./.venv' --exclude='./.env' --exclude='./.env.*' --exclude='./.codex' --exclude='./.agents' --exclude='./.firecrawl' --exclude='./graphify-out' --exclude='./data/backups' --exclude='./data/recovery/tools' --exclude='./data/derived/research_quality/test-*' --exclude='*/node_modules' --exclude='*/__pycache__' --exclude='./.pytest_cache' --exclude='./.mypy_cache' --exclude='./.ruff_cache' .
if ($LASTEXITCODE -ne 0) { throw 'Falha no pacote; não transferir como se estivesse completo.' }
(Get-FileHash -LiteralPath $projectArchive -Algorithm SHA256).Hash | Set-Content -LiteralPath "$projectArchive.sha256" -Encoding ascii
```

Revisar os arquivos selecionados para excluir credenciais que porventura tenham sido guardadas fora dos locais convencionais. Registrar junto ao pacote: data/hora, máquina de origem, branch/commit se disponíveis, alterações locais, versão do PostgreSQL, banco de origem e se os escritores estavam parados. A ausência de `.git` no snapshot é deliberada; não copiar o histórico grande só para executar a pesquisa.

### Preparar o banco

Os dumps encontrados em `data/backups/docker-recovery-20261007/` são de **07/10/2026**. `chart-observatory-current.dump` não significa “atual em 30/10”. Preferir um novo dump do banco realmente utilizado; se ele não estiver acessível, levar os dumps existentes como recuperação datada e manter a reconciliação pendente. Não inicializar um banco vazio e declarar que o histórico foi restaurado.

Somente se o banco de origem conferido for o serviço `postgres` de `compose.yaml`, com banco/usuário `chart_observatory`, usar:

```powershell
docker compose exec -T postgres pg_dump -U chart_observatory -d chart_observatory -Fc --file=/tmp/transferencia.dump
if ($LASTEXITCODE -ne 0) { throw 'Falha no dump.' }
$dumpFile = Join-Path $transferDir 'banco.dump'
docker compose cp postgres:/tmp/transferencia.dump $dumpFile
if ($LASTEXITCODE -ne 0) { throw 'Falha ao copiar dump.' }
(Get-FileHash -LiteralPath $dumpFile -Algorithm SHA256).Hash | Set-Content -LiteralPath "$dumpFile.sha256" -Encoding ascii
```

Se a origem for a instância nativa antiga em outra porta, usar `pg_dump` contra **essa instância**, com seus parâmetros conferidos. Não trocar de banco por conveniência. Não usar `>` no PowerShell para transportar o dump binário. Um dump lógico é portátil; copiar um volume ou diretório físico de PostgreSQL em execução não é substituto equivalente.

Copiar para o pendrive a pasta contendo o `.tar`, o `.dump`, seus hashes e o registro da transferência. No destino, copiar tudo para o disco local antes de extrair e executar. Não rodar o banco, SQLite ou ledgers diretamente no pendrive. Se algum arquivo exceder 4 GiB, usar um dispositivo já preparado com exFAT/NTFS; FAT32 não comporta esse arquivo. Não formatar um dispositivo com arquivos sem preservar seu conteúdo.

## 2. Preparar o computador de destino

Instalar a partir das fontes oficiais verificadas em [windows-setup-sources-20261030.md](windows-setup-sources-20261030.md):

- Git for Windows.
- uv; ele instala o Python, dispensando Python prévio.
- WSL2 e Docker Desktop, com virtualização habilitada. Reiniciar quando solicitado e abrir Docker Desktop até o mecanismo Linux estar pronto.
- Google Chrome: o coletor atual usa `channel="chrome"`; Chromium isolado não atende a esse código.
- Google Cloud CLI para autenticar Vertex AI.

O destino preferencial é `D:\PromiscuidadeMusical`, no disco local do computador novo. **O workflow atual rejeita outra unidade no Windows**, além de haver caminhos absolutos em configurações/checkpoints. Se o computador não tiver D:, o Codex deverá portar essa regra para o disco local escolhido e revisar referências antes de executar o workflow. Não basta alterar o diretório do terminal ou trocar todas as strings indiscriminadamente.

Conferir hash antes de extrair. Usar um diretório novo/vazio, sem sobrepor silenciosamente outro checkout ou dados diferentes:

```powershell
$receivedArchive = 'D:\Transferencia\projeto-dados.tar'
$expectedHash = (Get-Content -LiteralPath "$receivedArchive.sha256").Trim()
if ((Get-FileHash -LiteralPath $receivedArchive -Algorithm SHA256).Hash -ne $expectedHash) { throw 'Hash diferente; baixar novamente.' }
$destinationRoot = 'D:\PromiscuidadeMusical'
if (Test-Path -LiteralPath $destinationRoot) { throw 'Destino existente; escolher uma pasta vazia ou reconciliar a cópia antes de extrair.' }
New-Item -ItemType Directory -Path $destinationRoot | Out-Null
tar -xf $receivedArchive -C $destinationRoot
if ($LASTEXITCODE -ne 0) { throw 'Falha na extração.' }
Set-Location $destinationRoot
```

Se o projeto já foi clonado no destino, conservar esse checkout e extrair o snapshot em outra pasta para comparar/conciliar. Trabalhar na branch existente, sem criar commits ou mudar de branch automaticamente. O snapshot sem `.git` também pode ser aberto diretamente no Codex para execução, preservando o checkout original.

No PowerShell novo, após instalar uv:

```powershell
uv python install 3.12
uv sync --frozen --extra dev
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar dependências.' }
uv pip install playwright
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar Playwright.' }
uv run --no-sync python -c "import sys, polars, psycopg; from playwright.sync_api import sync_playwright; print(sys.version)"
```

Playwright não está declarado no `pyproject.toml` atual. Essa instalação extra é transitória; registrar sua versão. Na adaptação, declarar/travar a dependência para reprodução pelo lockfile. Até lá, `--no-sync` evita que a sincronização remova o pacote extra. Não são necessários Node.js, Excel, modelos locais ou GPU para o núcleo Python e chamadas remotas Gemini.

Criar os diretórios locais de estado/temporários e começar com concorrência baixa:

```powershell
New-Item -ItemType Directory -Path 'data\runtime\tmp' -Force | Out-Null
$env:TEMP = Join-Path (Get-Location).Path 'data\runtime\tmp'
$env:TMP = $env:TEMP
$env:PYTHONIOENCODING = 'utf-8'
$env:POLARS_MAX_THREADS = '2'
```

Em transferência completa por pendrive, os CSVs/JSONLs já vêm atuais: não restaurar automaticamente snapshots `.csv.gz` antigos sobre eles. Em clone sem esses dados, `scripts/sync_git_data.py restore` restaura apenas o que consta do manifesto Git e recusa conflitos; não recria o dump nem todos os dados brutos privados.

## 3. Restaurar PostgreSQL sem sobrescrever a origem

O Compose usa PostgreSQL 16 e porta local 5432. Conferir o hash de `banco.dump` com o mesmo procedimento do arquivo `.tar`. Depois:

```powershell
docker compose up -d postgres
if ($LASTEXITCODE -ne 0) { throw 'Docker indisponível.' }
docker compose exec -T postgres pg_isready -U chart_observatory
if ($LASTEXITCODE -ne 0) { throw 'Aguardar PostgreSQL ficar pronto.' }
docker compose cp 'D:\Transferencia\banco.dump' postgres:/tmp/transferencia.dump
if ($LASTEXITCODE -ne 0) { throw 'Falha ao copiar dump.' }
docker compose exec -T postgres pg_restore --list /tmp/transferencia.dump
if ($LASTEXITCODE -ne 0) { throw 'Dump inválido ou incompatível.' }
$restoredDb = 'chart_observatory_transfer_20261030'
docker compose exec -T postgres createdb -U chart_observatory -T template0 $restoredDb
if ($LASTEXITCODE -ne 0) { throw 'Banco já existente ou falha na criação; não apagar nem sobrescrever.' }
docker compose exec -T postgres pg_restore -U chart_observatory -d $restoredDb --no-owner --no-acl --exit-on-error --single-transaction /tmp/transferencia.dump
if ($LASTEXITCODE -ne 0) { throw 'Restauração falhou; investigar antes de prosseguir.' }
$env:CHART_OBSERVATORY_DATABASE_URL = "postgresql+psycopg://chart_observatory:local_development_only@127.0.0.1:5432/$restoredDb"
docker compose exec -T postgres psql -U chart_observatory -d $restoredDb -c 'SELECT current_database(), version();'
```

O usuário/senha local acima vem do Compose existente. Se o Compose for configurado de outra forma, ajustar também a URL. Recriar a configuração persistente no destino para que sessões seguintes apontem ao banco restaurado, e não ao banco padrão vazio.

Restaurar primeiro; depois conferir a revisão Alembic e revisar migrações pendentes. `uv run --no-sync chart-observatory db upgrade` é o comando existente que respeita a URL configurada; aplicar apenas depois dessa conferência. Não criar previamente as tabelas do aplicativo em um banco que receberá dump completo. Não usar `--clean` nem `docker compose down -v`.

Critério para prosseguir: conexão no banco esperado, contagens de capturas/entradas/letras/classificações comparadas ao snapshot de origem, schemas presentes, hashes dos SQLite e arquivos conferidos. Diferenças entre dump antigo e ledgers novos são pendências de reconciliação, não classificações novas automaticamente autorizadas.

Revisar checkpoints com caminho absoluto, inode, PID e hostname: `import_lyrics_incremental.py`, por exemplo, confere caminho/inode. Não apagar registros de custos ou reservas para fazer a execução continuar. Preservar o checkpoint original e ajustar/gerar a retomada somente após comprovar identidade do arquivo e reconciliação. Copiar a `.venv` antiga ou reutilizar PIDs da outra máquina não resolve isso.

## 4. Política da nova importação

Fonte de verdade de cotas: [country_quotas.csv](../../data/derived/research_quality/import-quotas-20261030/country_quotas.csv), com [country_year_import_plan.csv](../../data/derived/research_quality/import-quotas-20261030/country_year_import_plan.csv) e [allocation_summary.json](../../data/derived/research_quality/import-quotas-20261030/allocation_summary.json). A cópia amigável está em `outputs/annual-import-quotas-20261030/`. Memória do cálculo: [annual_import_quotas_20261030.md](../../research/annual_import_quotas_20261030.md).

- Cotas são por **país e ano**, uma seleção principal por célula: Brasil 230; República Dominicana 130; Estados Unidos/Indonésia 270; Índia 440. Seguir os 68 valores do CSV, sem substituir por um Top N uniforme.
- A janela candidata é 2017–2026. Fonte gratuita/API/web precisa ter disponibilidade histórica verificada para o mercado/período. Não contratar fornecedor pago para preencher lacunas por padrão.
- Em 2023–2024 não há arquivos locais usados no cálculo; 2017 e 2022 têm lacunas. Em 2026, o corte atual é 15/10/2026. Não inventar parâmetros `--years` inexistentes nem afirmar que o coletor atual já cobre dez anos.
- Importar capturas e proveniência de forma idempotente; agregar cada item/período uma vez. Preferir um único provedor Spotify por célula e nunca somar MGD e Kaggle espelhados. Não somar streams Spotify e views YouTube, nem períodos diários e semanais sobrepostos.
- Ordenar por totais comparáveis no período anual; pico diário, all-time, posição semanal isolada e ano de lançamento não substituem ranking anual. Quando só há união de paradas diárias, explicitar que o total é observado na parada.
- A lista `import_calendar_eligible.csv` contém 40.520 participações e 16.410 identidades candidatas em 270 células, incluindo 48 janelas parciais de 2026. Completude do calendário não certifica a extração ou a identidade; revisar as capturas e os vínculos antes de promover resultados.
- Ao completar lacunas, recalcular a ordem anual inteira. Não anexar entradas novas ao fim de um ranking antigo. Conservar captura bruta, URL, data de coleta, país observado, período, unidade, ID nativo e hashes.

**Adaptação necessária antes de importar a nova seleção:** remover limites fixos relevantes de `annual_cohort.py`, `annual_selection.py`, preparação/elegibilidade e persistência anual, substituindo-os pela consulta à política de cotas. Algumas funções aceitam no máximo 200 e a tabela antiga `article_annual_top80` impõe 80. Preservar tabelas/artefatos históricos; usar uma versão de seleção/migração própria, sem sobrescrever os resultados antigos. Testar países com cotas distintas, duplicações, conflitos, lacunas, empates e 2026 parcial.

O script `research/calculate_import_quotas_20261030.py` calcula o snapshot datado, mas usa cache e caminhos de 2026-10-30; não é um importador geral de dados novos. Reutilizar as cotas congeladas ou adaptar explicitamente a geração/invalidação de cache para novos insumos.

O coletor existente pode ser verificado sem coleta:

```powershell
uv run --no-sync python scripts/scrape_youtube_chart_titles.py --help
uv run --no-sync python scripts/revision_pipeline.py --help
uv run --no-sync python scripts/recover_reviewed_lyrics.py --help
```

Após conferir fonte, corte e adaptação, um piloto existente de **capturas**, sem importação no banco, é `uv run --no-sync python scripts/scrape_youtube_chart_titles.py --annual-metrics --countries BR,DO --workers 1 --max-snapshots 2`. Ele se limita ao inventário/corte implementado; não é um backfill 2017–2026. A saída deve ser inspecionada antes de ampliar.

## 5. Letras, identidade e piloto

Gerar a fila a partir da nova seleção anual, reaproveitando caches e candidatos históricos. O CSV anual não tem o schema de `recovery-targets.jsonl`: criar o adaptador com IDs e bindings corretos, não passar um arquivo no lugar do outro. Preservar posição original e perdas. Consultar [identity-rubric-pilot-20261025.md](identity-rubric-pilot-20261025.md) para os contratos de identidade/edição textual.

Para cada selecionado: confirmar gravação e versão, associar uma edição textual completa, manter texto original e normalizado com hashes, fontes/evidências, idioma e decisão de validação. Título/artista semelhantes e concordância entre sites ajudam na triagem, mas não certificam identidade/integridade. Instrumentais, ambiguidades e letras ausentes precisam de estado próprio. Não marcar validações humanas fictícias nem usar o texto mais longo como critério de verdade.

Classificar uma edição compatível uma vez e conservar seus vínculos a todos os países/anos. A assinatura de reutilização inclui hash textual, versão de normalização, rubrica, prompt, modelo e configuração efetiva. Texto diferente, versão limpa/explícita e tradução diferente não são automaticamente equivalentes. Snapshots antigos sem assinatura completa permanecem históricos até reconciliação.

Separar desenvolvimento do prompt e avaliação independente. Fazer teste mínimo de contrato, piloto pequeno com idiomas/temas variados e revisão humana; a amostra precisa ter suporte para os temas e idiomas que serão comparados. Conservar as avaliações e a adjudicação. Os oito casos problemáticos existentes e, separadamente, o exemplo BTS discutido nesta fase são regressões a verificar, não evidência de acurácia geral. Uma classificação válida no schema ainda pode estar semanticamente errada.

## 6. Google Cloud e orçamento

Autenticar no destino, sem copiar tokens da origem:

```powershell
gcloud config set project SEU_PROJECT_ID
gcloud services enable aiplatform.googleapis.com
gcloud auth application-default login
gcloud auth application-default set-quota-project SEU_PROJECT_ID
$env:GOOGLE_CLOUD_PROJECT = 'SEU_PROJECT_ID'
$env:GOOGLE_CLOUD_LOCATION = 'global'
```

Configurar `GEMINI_MODEL` com modelo e região efetivamente disponíveis/homologados na Vertex AI; registrar a configuração resolvida. Não copiar como atuais os modelos ou preços exemplificativos do README antigo. Consultar [preços oficiais Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/pricing) para o modo online/batch escolhido, configurar as taxas correspondentes e medir uso no piloto. ADC deve apontar ao projeto correto de cobrança. Autenticação e habilitação de API não enviam letras.

Política desta fase:

| Controle | Regra |
| --- | --- |
| Teto total informado | US$150 para a nova fase, com gastos e compromissos reconciliados |
| Meta principal | Até 30.000 candidatos globais; 23.984 observados no cálculo, incluindo anos incompletos só para planejamento |
| Reserva de volume | 6.000 candidatos para novas coletas, sujeita a recontagem |
| Expansão opcional | Até 45.000, somente após recontar identidades, letras e custo |
| Estimativa anterior | US$0,001/música fornecido pelo pesquisador: hipótese, não tarifa garantida |
| Gasto acumulado | Livro único com despesas conhecidas, reservas abertas, retentativas e serviços auxiliares; estado desconhecido impede novo envio |

`config/revision_campaign_budget.json` ainda declara US$180 e execuções legadas têm outros tetos. Na adaptação, versionar a política de US$150, conferir a soma das alocações e conectar o despachante ao mesmo controle cumulativo. Preservar o histórico e reconciliar despesas/compromissos; não reiniciar o contador a cada máquina, lote ou retomada. Ter um alerta de faturamento não substitui um bloqueio de gasto no aplicativo.

Levar os livros de requisições e de custo e consultar jobs pendentes no provedor antes de reenviar. Estado `submitted`, `reserved` ou `uncertain` exige reconciliação, não repetição automática. Não tratar SQLite vazio, restauração antiga ou erro de conexão como gasto zero.

## 7. Contrato da automação a completar no destino

Um único orquestrador deverá executar, com estados persistentes: inventário → coleta de lacunas → ranking anual → seleção por cota → resolução de identidade → aquisição de letras → validação → piloto → classificação → revisão → exportação. Um bloqueio em um país/ano não cria dados fictícios nem impede o relatório dos demais; impedir apenas o avanço que depende do insumo ausente.

Para o Gemini: despachar somente a fila validada da seleção nova; enviar a letra completa e a rubrica, mantendo país/ranking/população fora do payload temático; exigir JSON e evidências; validar a resposta e preservar snapshots. Reutilizar o mesmo pedido/resultado pela assinatura completa, reservar custo antes do envio e reconciliar antes de nova tentativa. Começar com um trabalhador e lotes pequenos; aumentar concorrência apenas após medir memória, quotas e taxa de erro.

O executor legado `classify-lyrics-run` não oferece o limite global novo por simples flag e pode percorrer o catálogo. `classify-lyrics --estimate-cost` usa contagem de tokens remota e também seleciona pelo contrato legado; não chamá-lo de auditoria puramente offline nem usá-lo como prova de que a fila nova foi respeitada. As receitas batch de US$600 não estão liberadas para esta campanha. `--force` não é uma estratégia de retomada.

**Condição para declarar automação pronta:** comando real documentado com `--help`, teste sem geração remota, demonstração de que só a seleção nova entra na fila, retomada sem duplicar importação/pedido/custo, rejeição de preço desconhecido e interrupção antes de exceder a reserva. Testar cancelamento entre envio e resposta, assinatura incompatível, orçamento esgotado, letra ausente e falha transitória. Não inventar um comando final neste guia antes de implementá-lo.

Registrar por execução: versões/hashes dos insumos, cobertura país/ano, cota/quantidade efetiva, identidades/letras pendentes, concluídos/erros, tokens, gasto/reservas/saldo e último checkpoint. Logs operacionais não precisam reproduzir letras ou credenciais. Gerar exportações com denominadores e cobertura explícitos; não publicar rankings corrigidos a partir de resultados ainda pendentes.

## 8. Texto para entregar ao Codex no computador novo

> Leia `docs/operations/execucao-outro-computador-20261030.md` e siga esta edição para a nova fase. Prepare o ambiente e restaure o pacote do pendrive em disco local, conferindo hashes e usando banco novo. Preserve a branch existente, as alterações locais, o histórico, os dados e os livros de custo; não faça commits ou pushes automaticamente. Se o disco não for D:, porte a restrição de armazenamento com testes antes de executar o workflow.
>
> Complete a integração das cotas dos 68 países na seleção, persistência e filas. Use apenas fontes gratuitas/API/web com cobertura verificada para 2017–2026, tratando lacunas e 2026 parcial explicitamente. A seleção é por totais anuais observados, sem somar plataformas ou provedores espelhados. Reaproveite caches e classificações somente com assinatura completa e mantenha pendências de identidade/letra.
>
> Integre a classificação Gemini apenas da fila nova validada, com ADC do destino, piloto revisado, livro cumulativo e teto de US$150. A meta é ficar em até 30 mil candidatos; a média de US$0,001 é só planejamento. Execute primeiro instalação, diagnóstico, adaptação e testes sem geração paga. Registre os pontos que exigem login ou avaliação humana real. Só habilite a execução remota após comprovar fila, preços, piloto e orçamento; não contorne os bloqueios existentes nem use a classificação legada do catálogo inteiro.
>
> Ao concluir, documente os comandos efetivamente implementados, a pausa/retomada, os resultados de validação e as pendências. A existência deste guia não comprova que a migração ou a automação já foi executada.

## Verificação deste guia

Os três comandos `--help` acima foram executados localmente com sucesso em 30/10/2026. As opções, limites, dependências, caminhos e bloqueios foram confrontados com código e configuração. Instalação, transferência, restauração e inferência no outro computador ainda não foram executadas. As fontes oficiais de instalação/autenticação/restauração estão na [nota de verificação](windows-setup-sources-20261030.md).
