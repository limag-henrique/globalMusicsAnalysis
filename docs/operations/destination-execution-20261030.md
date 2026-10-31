# Preparação efetivamente executada no destino — 30/10/2026

Projeto: `D:\Repositórios\PromiscuidadeMusical`. Seguido o plano
[execucao-outro-computador-20261030.md](execucao-outro-computador-20261030.md).
Este registro separa a preparação concluída da pesquisa ainda pendente de validação.

## Ambiente

- uv 0.13.6 e Python 3.12.16 operacionais. A instalação automática do Python gerou
  um erro no link da versão menor, embora o executável tenha sido extraído corretamente.
  A `.venv` nova foi criada apontando explicitamente para esse interpretador funcional.
- Ambiente original preservado em `.venv-origin-preserved`, excluído localmente do Git.
- Dependências de desenvolvimento e pesquisa instaladas pelo lockfile. Playwright
  declarado em `pyproject.toml` e `uv.lock`; sincronização posterior confirmada.
- Chromium do Playwright instalado e lançamento headless verificado com página local.
  O coletor aceita `--browser-channel chromium`; o padrão anterior Chrome foi preservado.
- Google Cloud SDK 591.0.0 instalado e `gcloud --version` conferido. ADC ainda ausente.
- Docker Desktop instalado, mas sem mecanismo ativo. WSL exige instalação administrativa;
  a tentativa via WinGet retornou `0x80073d28`. Nenhum reinício foi realizado.
- Chrome: tentativa WinGet rejeitada por hash divergente; instalação pelo Playwright
  falhou por privilégios. A revisão automática bloqueou a tentativa por instalador
  alternativo. Chromium é a alternativa já instalada e testada.

Fontes oficiais usadas: [uv](https://docs.astral.sh/uv/getting-started/installation/),
[Playwright](https://playwright.dev/python/docs/intro),
[binários PostgreSQL](https://www.enterprisedb.com/download-postgresql-binaries).

## Banco recuperado

O diretório fornecido `D:\Repositórios\PromiscuidadeMusicalPostgres` contém um
cluster físico PostgreSQL **18**, não um dump lógico. Seu log registra desligamento
em 27/09/2026; a data de cópia dos arquivos não prova atualização do conteúdo.
Foi preservado, sem inicialização por PostgreSQL 16 e sem sobrescrita.
Inspeção com `pg_controldata` 18.6 confirmou estado `shut down`, controle e último
checkpoint em **27/09/2026 às 19:44:15**. Evidência local em
`data/runtime/postgres18-source-control.txt`. Portanto esse cluster não é um
snapshot posterior ao dump de 07/10, embora possa conter registros exclusivos.

O dump `data/backups/docker-recovery-20261007/chart-observatory-current.dump` declara
criação em 07/10/2026 às 22:18:32 e servidor 16.15. Foi restaurado com sucesso,
em transação única, num banco novo:

SHA-256 do dump:
`282798d9389d78ab1567dbae6594dcd40e171dde631e9cb41acea4ec39e1b4d2`.

- Servidor PostgreSQL nativo 16.15 em `127.0.0.1:55433`, somente loopback.
- Banco `chart_observatory_recovery_20261007`.
- Dados do servidor: `%LOCALAPPDATA%\ChartObservatory\postgres16-destination`.
- Ferramentas: `%LOCALAPPDATA%\ChartObservatory\postgresql16`.
- Autenticação TCP SCRAM. Credencial local de desenvolvimento igual à do Compose.
- `.env` aponta ao banco recuperado. Configuração anterior preservada em
  `data/runtime/env-origin-preserved.bak`; nenhum segredo foi impresso.

O caminho sem acentos foi necessário porque `initdb` dos binários transferidos
falhou com erro de codificação UTF-8 dentro de `D:\Repositórios`. Os arquivos da
pesquisa, backups e novas seleções continuam no projeto em D:.

Contagens após restauração: 159.111 documentos de letras; 167.952 snapshots de
classificação; 31 lotes Gemini; zero linhas em `chart_snapshots` e `chart_entries`.
Revisão Alembic `0015_gemini_batch`. Isto é recuperação datada, não comprovação
de que as classificações são compatíveis com o novo protocolo ou de gasto zero.

Para iniciar após reinicializar o computador e preparar a sessão PowerShell:

```powershell
. .\scripts\research_environment.ps1
uv run --frozen --extra dev --extra research python scripts/prepare_quota_import.py --help
```

Para conferir ou parar o servidor local:

```powershell
.\scripts\research_environment.ps1 -StatusOnly
.\scripts\research_environment.ps1 -Stop
```

## Nova seleção por cotas

Implementado `scripts/prepare_quota_import.py`, com política em
`ingestion/import_quotas.py` e persistência em `ingestion/quota_repository.py`.
Consome as cotas principais congeladas dos 68 países e os rankings anuais e
cobertura já calculados. Não recalcula a fórmula demográfica nem faz backfill.
Depois de nova coleta, é obrigatório agregar novamente o quadro anual inteiro
e fornecer rankings/cobertura atualizados; não anexar faixas ao recorte antigo.

Regras aplicadas: 680 células em 2017–2026; uma plataforma principal por célula;
calendário completo primeiro e Spotify em igualdade de completude; nenhuma soma
de plataformas/provedores; cotas individuais até 500; posições originais mantidas;
sem avanço da fronteira por letra ausente. Falta de calendário/itens vira déficit.
2026 permanece parcial. Completude de calendário não certifica profundidade nem
identidade musical. Metadados YouTube continuam candidatos provisórios.

Execução efetiva:

```powershell
uv run --frozen python scripts/prepare_quota_import.py --output data/derived/annual_revision/quotas-20261030-destination-v2 --prepared --apply
```

A execução inicial usou o mesmo destino sem `--prepared`, que exige pasta nova.
Repetir com `--prepared` confere hashes dos insumos e saídas, e reaplica a mesma
assinatura sem duplicação. Para outro snapshot, escolher uma pasta de saída nova.
Sem `--apply`, o comando apenas prepara arquivos e não grava no banco.

Resultado: **40.520 participações**, **16.410 candidatos**; 68 países, 680 células
auditadas. Correspondência exata com os totais de calendário elegível do plano.
Comparação independente com `import_calendar_eligible.csv` confirmou os mesmos
40.520 vínculos por país, ano, plataforma, posição, identidade e métrica, sem
faltas ou entradas extras. São 222 calendários anuais, 48 parciais de 2026 e
410 células ainda sem calendário completo.
Fila de recuperação deduplicada por candidato com todos os vínculos país/ano.
Nenhuma identidade entre plataformas é fundida por título/artista.

Tabelas próprias `quota_import_runs` e `quota_import_memberships`, separadas dos
resultados históricos. Snapshot `742c09c655edd97baac9bafabd9c075c5d3cd0132bc37395cefa0481d0a8eeae`.
Primeira aplicação: 40.520 vínculos; segunda: mesmo identificador, nenhuma inserção.
Os campos `database_writes=0` do manifesto descrevem a fase de preparação; a
persistência solicitada por `--apply` tem resultado separado no terminal.

61 testes relevantes passaram; Ruff e verificação do lockfile passaram.

## Pendências para pesquisa e classificação

1. Reconciliar o banco recuperado com o cluster 18 e os checkpoints/ledgers locais.
   Datas de transferência não substituem evidência do estado de origem.
2. Completar paradas ausentes com disponibilidade gratuita verificada. 2023–2024
   não passam a existir pela instalação do ambiente. Recomputar rankings depois.
3. Reconciliar caches/letras existentes antes de iniciar recuperação nova; confirmar
   gravação, versão, integridade, direitos e hashes. A fila gerada contém candidatos,
   não letras validadas. Nenhuma recuperação ou classificação nova foi disparada.
4. Conectar a seleção nova ao registro de edições e à assinatura completa do
   `revision_protocol.py`, ao executor e ao controle cumulativo de **US$150**.
   O manifesto informa esse teto, mas não é um bloqueio financeiro de execução.
   O executor/ledger legado de US$180 não foi usado como atalho nem reconfigurado.
5. Fazer ADC nesta máquina, verificar preços, reconciliar gastos/compromissos e
   realizar piloto e avaliação humana real antes de habilitar envio remoto.

Não houve chamadas Gemini nem gastos de classificação nesta preparação.
O ambiente e a seleção inicial estão preparados; a automação científica integral
ainda não está concluída nem validada para execução paga.
