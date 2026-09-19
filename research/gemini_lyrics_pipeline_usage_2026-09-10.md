# Pipeline de letras e análise Gemini

O comando `corpus gemini-analyze` percorre `data/derived/track_master.parquet`, busca a
letra original primeiro no LRCLIB e depois no Lyrics.ovh, e envia cada letra encontrada
ao Gemini para detectar o idioma, produzir uma tradução inglesa e classificar as
dimensões da pesquisa em escala 0–3. A resposta é gravada em
`data/derived/lyrics/gemini_annotations.jsonl` uma faixa por linha.

## Autenticação

O pipeline usa Vertex AI com Application Default Credentials (ADC), sem chave de
API. Em Bash/Linux ou macOS, configure o ADC com o script:

```bash
bash <(curl -sSL \
  https://storage.googleapis.com/cloud-samples-data/adc/setup_adc.sh)
```

Esse script instala ou localiza o `gcloud`, solicita o projeto, configura o ADC,
define o projeto de quota, habilita `aiplatform.googleapis.com` e faz uma chamada
de verificação. Como ele baixa e executa código remoto, revise o script antes de
rodá-lo. Em produção, prefira ADC baseado em conta de serviço para não depender de
login pessoal.

Se o projeto não for detectado automaticamente pelo ADC, defina no `.env`:

```dotenv
GOOGLE_CLOUD_PROJECT=seu-project-id
GOOGLE_CLOUD_LOCATION=global
```

## Execução

Depois execute:

```powershell
.venv\Scripts\python.exe -m chart_observatory.cli corpus gemini-analyze
```

Para validar uma amostra antes do corpus inteiro:

```powershell
.venv\Scripts\python.exe -m chart_observatory.cli corpus gemini-analyze --limit 10 --output data/derived/lyrics/gemini_smoke.jsonl
```

O arquivo é append-only. IDs com `lyrics_status` `FOUND` ou `MISSING` são pulados em
execuções posteriores; erros de provedor ou do Gemini ficam registrados e podem ser
tentados novamente. O processo usa chamadas sequenciais e uma espera padrão de 350 ms,
adequada ao uso responsável do LRCLIB. Nenhuma letra ou chave é escrita no log do
terminal, mas as letras são armazenadas no JSONL local para permitir auditoria e
traduções posteriores.

## Estrutura de cada registro

Registros encontrados contêm `song_id`, título, artista, fonte da letra, a letra original,
modelo usado e `analysis`. Dentro de `analysis`, `translation_en` é a tradução inglesa e
`dimensions`, `relational_scripts`, `representation_roles`, `evidence` e
`quality_flags` formam a saída comparável entre modelos. Registros sem letra preservam o
ID com `lyrics_status: MISSING`; falhas transitórias usam `PROVIDER_ERROR` ou
`GEMINI_ERROR`.

O resultado é uma camada de pesquisa e não substitui revisão humana: correspondências
ambíguas do LRCLIB são descartadas para evitar atribuir a letra errada, e menção,
descrição, crítica, endosso e glorificação são solicitados separadamente ao modelo.
