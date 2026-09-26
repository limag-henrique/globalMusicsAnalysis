# Chart Observatory — Global Musics Analysis

Research observatory and analytical platform for global music charts, popularity dynamics, and automated lyrical classification.

---

## 1. Visão Geral e Arquitetura

O **Chart Observatory** coleta, normaliza e reconcilia metadados de faixas musicais e observações de paradas (Spotify, YouTube, MGD, Kaggle) e integra um pipeline de classificação semântica e taxonômica de letras musicais com inteligência artificial via **Google Cloud Vertex AI** (`google-genai` SDK).

### Componentes Principais

- **Ingestão e Normalização (`chart_observatory.ingestion`, `sources`)**: Processamento de datasets históricos, streaming em lotes e reconciliação canônica de títulos e artistas.
- **Catálogo Canônico (`chart_observatory.corpus`)**: Estruturação de faixas canônicas (`track_master`), observações temporais e verificação de direitos autorais de letras (`LyricDocument`).
- **Classificação Automática de Letras (`chart_observatory.lyrics`)**:
  - Taxonomia Pydantic v2 imutável com 6 dimensões temáticas (sexualidade, relacionamentos, representação de gênero, status material, elementos antissociais, identidade territorial).
  - Políticas de geração por família de modelos (suporte nativo a Gemini 3 com `thinking_level` e Gemini 2 com `temperature=0`).
  - Persistência append-only imutável em banco de dados (`LyricClassificationSnapshot`) com garantia de integridade tanto em PostgreSQL quanto em SQLite.
  - Estimativa prévia de custos (`--estimate-cost`) e proteção orçamentária rígida (*fail-closed* via `--max-cost-usd`).
- **Interface e Exportação (`chart_observatory.ui`, `exports`)**: Painel de visualização analítica em Streamlit e pipelines analíticos.

---

## 2. Requisitos e Instalação

- **Python**: 3.12+
- **Gerenciador de dependências**: [`uv`](https://docs.astral.sh/uv/)

```powershell
# Sincronizar o ambiente virtual e instalar dependências
uv sync
```

---

## 3. Configuração do Vertex AI com Application Default Credentials (ADC)

A classificação automática de letras utiliza a API oficial da Vertex AI via autenticação **ADC**. **Não** é permitida a utilização de chaves de API estáticas (`API_KEY`) ou credenciais versionadas no repositório.

> [!CAUTION]
> **Nunca copie credenciais, arquivos de chave de serviço (service account keys) ou tokens para o repositório.** O Google Cloud CLI armazena o token ADC de forma segura no perfil local do sistema operacional.

### Configuração Passo a Passo no Windows PowerShell:

```powershell
# 1. Definir o projeto padrão no Google Cloud CLI
gcloud config set project SEU_PROJECT_ID

# 2. Habilitar a API do Vertex AI no projeto
gcloud services enable aiplatform.googleapis.com

# 3. Realizar o login interativo via navegador para gerar o ADC
gcloud auth application-default login

# 4. Definir o projeto de quota para cobrança das operações Vertex AI
gcloud auth application-default set-quota-project SEU_PROJECT_ID
```

### Configuração de Variáveis de Ambiente

Crie ou edite o arquivo `.env` na raiz do projeto (ou configure as variáveis na sessão do PowerShell):

```powershell
$env:GOOGLE_CLOUD_PROJECT = "SEU_PROJECT_ID"
$env:GOOGLE_CLOUD_LOCATION = "global"
$env:GEMINI_MODEL = "MODEL_ID_COMPATIVEL_E_FIXO"
```

#### Parâmetros de Configuração:
- `GOOGLE_CLOUD_PROJECT`: ID do projeto Google Cloud com faturamento ativo e a API Vertex AI habilitada.
- `GOOGLE_CLOUD_LOCATION`: Região suportada pelo modelo na Vertex AI (por exemplo, `global` ou `us-central1`).
- `GEMINI_MODEL`: Identificador de versão fixo e homologado da família Gemini (ex.: `gemini-2.5-flash` ou `gemini-3.8-flash`). Não utilize aliases mutáveis ou experimentais.
- `GEMINI_THINKING_LEVEL`: Nível de raciocínio para modelos Gemini 3 (opções: `MINIMAL`, `LOW`, `MEDIUM`, `HIGH`; padrão: `MINIMAL`).

#### Tabela de Preços (Rate Card) para Estimativas Monetárias:
Para que o sistema estime custos financeiros em dólares (`--estimate-cost` / `--max-cost-usd`), defina as taxas correspondentes no `.env`:

```dotenv
GEMINI_INPUT_USD_PER_MILLION_TOKENS=0.15
GEMINI_OUTPUT_USD_PER_MILLION_TOKENS=0.60
GEMINI_THOUGHT_USD_PER_MILLION_TOKENS=0.60
GEMINI_OUTPUT_TOKEN_ALLOWANCE=8192
```

Se qualquer taxa da tabela estiver ausente, o custo financeiro é mantido estritamente como `null` para prevenir cálculos enganosos.

---

## 4. Comandos da Linha de Comando (CLI)

O executável `chart-observatory` disponibiliza as operações do sistema.

### 4.1 Preparar o Banco de Dados

Aplique as migrações mais recentes do Alembic para garantir a criação das tabelas e dos gatilhos de imutabilidade:

```powershell
chart-observatory db upgrade
```

### 4.2 Estimativa Prévia de Custos (Segura / Não Invocativa)

Conta os tokens de entrada de até 5 letras elegíveis e calcula o limite superior de custo sem invocar a geração do Gemini:

```powershell
chart-observatory corpus classify-lyrics --limit 5 --estimate-cost
```

### 4.3 Execução Limitada de Classificação

Executa a classificação de forma estritamente controlada e idempotente:

```powershell
# Execução básica limitada
chart-observatory corpus classify-lyrics --limit 5

# Execução com proteção orçamentária máxima (aborta antes da geração se a estimativa exceder o limite)
chart-observatory corpus classify-lyrics --limit 5 --max-cost-usd 0.05

# Processar apenas letras que ainda não foram classificadas com sucesso
chart-observatory corpus classify-lyrics --limit 10 --only-unclassified

# Forçar reclassificação (gera um novo registro encadeado no histórico sem sobrescrever o anterior)
chart-observatory corpus classify-lyrics --limit 5 --force
```

---

## 5. Testes e Validação de Código

### 5.1 Suíte de Testes Automáticos (Sem Chamadas Externas)

Todos os testes unitários, contratuais e de integração operam com fakes e mocks e podem ser executados sem credenciais de nuvem:

```powershell
# Executa todos os testes não-live
uv run pytest -m 'not live'
```

### 5.2 Teste de Fumaça em Produção (Live Smoke Test Opcional)

Para verificar pontualmente a conectividade com o Vertex AI e o ADC sem comprometer a base de dados de produção:

```powershell
$env:CHART_OBSERVATORY_LIVE_SMOKE = "1"
uv run pytest tests/live/test_vertex_lyrics_classification_smoke.py -v
```

### 5.3 Análise Estática e Tipagem

```powershell
# Linter e regras de formatação
uv run ruff check src tests

# Verificação estrita de tipos
uv run mypy src/chart_observatory
```
