# Pipeline de Letras e Classificação com Vertex AI Gemini

Este documento descreve a infraestrutura de classificação semântica de letras musicais utilizando o SDK oficial `google-genai` com Vertex AI e autenticação via Application Default Credentials (ADC).

---

## 1. Comandos de Execução

O sistema oferece dois fluxos de execução:

### 1.1 Comando Oficial e Reprodutível (`corpus classify-lyrics`)

O comando preferencial e auditável opera diretamente sobre os documentos de letras autorizados já ingeridos no banco de dados (`LyricDocument`), persistindo snapshots imutáveis em `LyricClassificationSnapshot`.

```powershell
# 1. Aplicar migrações do banco de dados (garante a tabela e índices imutáveis)
chart-observatory db upgrade

# 2. Estimativa de custo prévia (apenas conta tokens, não invoca geração)
chart-observatory corpus classify-lyrics --limit 5 --estimate-cost

# 3. Execução limitada e segura com teto de custo máximo em dólares
chart-observatory corpus classify-lyrics --limit 5 --max-cost-usd 0.05

# 4. Execução padrão limitada (concorrência máxima de workers = 2 por padrão)
chart-observatory corpus classify-lyrics --limit 5
```

**Principais opções de `classify-lyrics`**:
- `--limit N`: Restringe a execução a no máximo `N` letras elegíveis.
- `--estimate-cost`: Executa apenas contagem de tokens via `count_tokens` e cálculo de limite superior monetário; **não** chama `generate_content`.
- `--max-cost-usd X.XX`: Proteção orçamentária fail-closed; se a estimativa exceder o valor ou for desconhecida, a execução aborta antes de qualquer chamada ao modelo.
- `--workers W`: Limita os workers paralelos (mínimo 1, máximo 8; padrão 2).
- `--only-unclassified`: Ignora faixas que já possuam qualquer classificação bem-sucedida (`classified` ou `ambiguous`).
- `--force`: Em caso de reprocessamento explícito, mantém a imutabilidade do histórico e anexa um novo snapshot encadeado ao anterior via `forced_from_snapshot_id`.
- `--database-url URL`: URL de conexão opcional (padrão via `.env` / `Settings`).

### 1.2 Comando Legado (`corpus gemini-analyze`)

Mantido para compatibilidade com o fluxo de extração e anotação direta em arquivo JSONL (`data/derived/lyrics/gemini_annotations.jsonl`):

```powershell
chart-observatory corpus gemini-analyze --limit 10 --output data/derived/lyrics/gemini_smoke.jsonl
```

---

## 2. Configuração do Vertex AI e Autenticação ADC

O pipeline utiliza **exclusivamente** o SDK `google-genai` conectado à Vertex AI via ADC. **Nenhuma chave de API (API key) ou cabeçalho manual de autorização é aceito.**

> [!CAUTION]
> **Nunca armazene credenciais, chaves de serviço ou tokens no repositório ou em arquivos versionados pelo Git.** O ADC gerencia as credenciais no perfil do sistema operacional do usuário.

### Configuração Passo a Passo no Windows PowerShell:

```powershell
# 1. Definir o projeto ativo no Google Cloud CLI
gcloud config set project SEU_PROJECT_ID

# 2. Habilitar a API do Vertex AI no projeto
gcloud services enable aiplatform.googleapis.com

# 3. Autenticação interativa do usuário no navegador para gerar o ADC
gcloud auth application-default login

# 4. Definir o projeto de quota para faturamento de chamadas Vertex AI
gcloud auth application-default set-quota-project SEU_PROJECT_ID
```

### Variáveis de Ambiente (`.env` ou sessão PowerShell)

Configure as seguintes variáveis no arquivo `.env` na raiz do projeto ou na sessão do PowerShell:

```powershell
$env:GOOGLE_CLOUD_PROJECT = "SEU_PROJECT_ID"
$env:GOOGLE_CLOUD_LOCATION = "global"
$env:GEMINI_MODEL = "MODEL_ID_COMPATIVEL_E_FIXO"
```

> [!IMPORTANT]
> - `GEMINI_MODEL`: Deve ser um identificador de modelo fixo e suportado (por exemplo, `gemini-2.5-flash` ou `gemini-3.8-flash`). Não utilize aliases voláteis ou inexistentes.
> - `GOOGLE_CLOUD_LOCATION`: Localização suportada pela Vertex AI para o modelo selecionado (ex.: `global` ou `us-central1`).

---

## 3. Política de Geração por Família de Modelos

A camada de integração (`GenerationPolicy`) adapta a chamada do SDK conforme a família do modelo configurado:

- **Modelos Gemini 3** (ex.: `gemini-3.8-flash`):
  - Utilizam `thinking_level` configurável (padrão `MINIMAL` via `GEMINI_THINKING_LEVEL`).
  - Não utilizam parâmetros de amostragem customizada (`temperature`, `top_p`, `top_k`), prevenindo erros de validação da API.
- **Modelos Gemini 2** (ex.: `gemini-2.5-flash`):
  - Utilizam amostragem determinística (`temperature=0.0`).
- **Modelos Desconhecidos**:
  - Omitirão amostragem e configurações de thinking para máxima compatibilidade futura.

---

## 4. Tabela de Preços (Rate Card) e Telemetria

Para que o pipeline calcule os custos monetários exatos em dólares (`estimated_cost_usd`), configure as taxas por milhão de tokens no `.env`:

```dotenv
GEMINI_INPUT_USD_PER_MILLION_TOKENS=0.15
GEMINI_OUTPUT_USD_PER_MILLION_TOKENS=0.60
GEMINI_THOUGHT_USD_PER_MILLION_TOKENS=0.60
GEMINI_OUTPUT_TOKEN_ALLOWANCE=8192
```

Se qualquer taxa da tabela de preços estiver ausente, o custo será mantido estritamente como `null` no banco de dados para evitar projeções financeiras errôneas. As contagens de tokens brutas (`input_tokens`, `output_tokens`, `thought_tokens`, `total_tokens`) são sempre registradas a partir do `usage_metadata` retornado pela API.

---

## 5. Testes de Fumaça (Live Smoke Test)

Para validar a autenticação ADC e a comunicação real com a Vertex AI sem tocar na base de dados de produção nem incorrer em custos relevantes, execute o teste de fumaça unitário opt-in:

```powershell
$env:CHART_OBSERVATORY_LIVE_SMOKE = "1"
uv run pytest tests/live/test_vertex_lyrics_classification_smoke.py -v
```

O teste classifica uma única letra estática de teste e verifica o status retornado (`classified` ou `ambiguous`). Sem a variável `CHART_OBSERVATORY_LIVE_SMOKE=1`, o teste é automaticamente pulado (`SKIPPED`).
