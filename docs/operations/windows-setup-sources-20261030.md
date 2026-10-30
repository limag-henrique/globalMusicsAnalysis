# Fontes verificadas para preparar outro computador Windows

Verificação documental em 30/10/2026. Esta nota apoia o guia de transferência; não instala programas, não restaura bancos e não autoriza chamadas pagas.

## Instalação em máquina sem ambiente de desenvolvimento

| Componente | Procedimento confirmado | Fonte primária |
| --- | --- | --- |
| Git | Instalador oficial ou `winget install --id Git.Git -e --source winget`; reabrir o terminal e conferir `git --version`. | [Git for Windows](https://git-scm.com/install/windows) |
| uv | O instalador standalone funciona sem Python previamente instalado: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"`. O escape da barra nesta tabela é somente Markdown; usar a versão abaixo no terminal. | [Astral: instalação](https://docs.astral.sh/uv/getting-started/installation/) |
| Python | `uv python install 3.12`; o uv gerencia o interpretador e dispensa instalação manual separada. | [Astral: Python](https://docs.astral.sh/uv/guides/install-python/) |
| WSL | Em PowerShell como administrador, `wsl --install`, reiniciar quando solicitado; conferir `wsl --list --verbose`. | [Microsoft: WSL](https://learn.microsoft.com/en-us/windows/wsl/install) |
| Docker Desktop | Usar o instalador oficial e backend Linux/WSL2. Abrir o aplicativo e esperar o mecanismo iniciar antes de `docker compose`. Conferir os requisitos do Windows e virtualização na página oficial. | [Docker: Windows](https://docs.docker.com/desktop/setup/install/windows-install/) |
| Google Cloud CLI | Instalador Windows oficial, com o Python próprio incluído. Reabrir o terminal e conferir `gcloud --version`. | [Google: instalar CLI](https://docs.cloud.google.com/sdk/docs/install-sdk) |
| Navegador do scraper | O scraper atual lança `channel="chrome"`, exigindo Google Chrome instalado. Chromium isolado não atende a esse código. | [Código local](../../scripts/scrape_youtube_chart_titles.py), [Playwright: navegadores](https://playwright.dev/python/docs/browsers) |

Comando PowerShell oficial do uv, sem escape de tabela:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Não é necessário instalar Node.js para usar a biblioteca Playwright Python pelo fluxo documentado. Seus componentes são distribuídos pela própria biblioteca.

## Atenção à dependência Playwright neste projeto

O `pyproject.toml` inspecionado não declara Playwright. Logo, `uv sync` sozinho não instala o coletor web completo. A solução durável é declarar e travar essa dependência quando a implementação for adaptada. Para uma instalação operacional transitória, pode-se instalar na `.venv` com `uv pip install playwright`, conservando um registro da versão, e usar `uv run --no-sync ...` nas chamadas seguintes para que uma nova sincronização não remova o pacote extra. Não chamar isso de reprodução integral pelo lockfile.

A documentação Playwright confirma que o pacote e os binários de navegador são etapas distintas, e suporta `playwright install chromium` para o navegador livre e `playwright install chrome` para o Chrome de marca. Esse último instala Chrome no local global padrão e pode substituir uma instalação existente. Em máquina nova, o instalador oficial do Chrome é a opção direta. Se o código for alterado para usar Chromium sem `channel="chrome"`, instalar esse binário na versão correspondente do Playwright. [Fonte](https://playwright.dev/python/docs/browsers).

## Vertex AI: autenticação nova no computador de destino

```powershell
gcloud config set project SEU_PROJECT_ID
gcloud auth application-default login
gcloud auth application-default set-quota-project SEU_PROJECT_ID
```

`gcloud auth application-default login` abre a autenticação interativa e grava ADC no perfil local. `gcloud config set project` sozinho não cria ADC. O comando `set-quota-project` deve vir depois do login e exige a permissão `serviceusage.services.use` no projeto de quota. Não transferir o arquivo ADC nem a pasta de tokens via Drive. Configurar novamente no destino. [Google: ADC local](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment), [Google: projeto de quota](https://docs.cloud.google.com/sdk/gcloud/reference/auth/application-default/set-quota-project).

Habilitar `aiplatform.googleapis.com` e permissões de uso de Vertex no projeto quando necessário. Configuração de autenticação não executa a classificação. Taxas e modelo precisam de verificação própria antes de qualquer chamada paga; não copiar uma tabela histórica como se fosse preço atual.

## PostgreSQL: transferência lógica para um banco novo

O `compose.yaml` do projeto fixa `postgres:16-alpine`. Usar os utilitários desse container mantém o cliente do dump compatível com o servidor local. `pg_dump -Fc` gera arquivo custom; `pg_restore` lê esse formato. O dump de um banco não inclui todos os objetos globais de um cluster. [PostgreSQL: pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html), [PostgreSQL: pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html).

Exemplo para o guia adaptar aos caminhos escolhidos, sem executar nesta pesquisa:

```powershell
# Origem: arquivo binário escrito dentro do container, sem redirecionamento PowerShell.
docker compose exec -T postgres pg_dump -U chart_observatory -d chart_observatory -Fc --file=/tmp/chart_observatory_transfer.dump
if ($LASTEXITCODE -ne 0) { throw 'Falha ao exportar banco.' }
$transferContainerId = docker compose ps -q postgres
docker cp "${transferContainerId}:/tmp/chart_observatory_transfer.dump" .\chart_observatory_transfer.dump
if ($LASTEXITCODE -ne 0) { throw 'Falha ao copiar dump.' }

# Destino: banco novo. Se já existir, parar e escolher outro nome; não apagar.
$transferContainerId = docker compose ps -q postgres
docker cp .\chart_observatory_transfer.dump "${transferContainerId}:/tmp/chart_observatory_transfer.dump"
if ($LASTEXITCODE -ne 0) { throw 'Falha ao copiar dump para container.' }
docker compose exec -T postgres createdb -U chart_observatory -T template0 chart_observatory_transfer_20261030
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível criar um banco novo.' }
docker compose exec -T postgres pg_restore -U chart_observatory -d chart_observatory_transfer_20261030 --no-owner --no-acl --exit-on-error --single-transaction /tmp/chart_observatory_transfer.dump
if ($LASTEXITCODE -ne 0) { throw 'Falha ao restaurar dump.' }
```

Não aplicar migrações que criem tabelas antes de restaurar um dump completo no banco novo. Após a restauração, configurar a URL para esse banco, conferir contagens e revisar migrações pendentes. Não usar `--clean`, não restaurar por cima de um banco existente e não copiar o diretório físico de um PostgreSQL em execução como substituto de um dump lógico.

## Validação desta nota

Foram consultadas as fontes oficiais acima e confrontadas com `compose.yaml`, `pyproject.toml` e a chamada de lançamento do navegador em `scripts/scrape_youtube_chart_titles.py`. Os exemplos são instruções verificadas documentalmente, não um teste de instalação ou de restauração em outra máquina. Nenhum programa foi instalado e nenhum banco foi alterado.
