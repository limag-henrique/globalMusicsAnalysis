# Vertex AI Lyrics Classification Design

**Status:** Approved for implementation planning  
**Date:** 2026-09-19

## Intent and success criteria

Add a reproducible automatic lyric-classification pipeline to the chart observatory.
It must classify one authorized lyric document per Gemini request using the official
`google-genai` SDK with Vertex AI and Application Default Credentials (ADC), while
keeping the current manual Streamlit/JSON classification flow and `SemanticAnnotation`
model intact.

Success means that a bounded CLI run can select eligible stored lyric documents, skip an
already-created classification with the same reproducibility signature, call Gemini
Flash once per newly eligible lyric, validate the structured result, and append an
immutable auditable snapshot. A forced run creates a new snapshot instead of updating an
old one. The model receives only the lyric text and, when available, its language.

## Constraints

- Use `google-genai`, Vertex AI, and ADC only. Do not use the Gemini Developer API,
  manual REST requests, API keys, checked-in service-account JSON, or copied ADC files.
- Read `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and `GEMINI_MODEL` through
  `Settings`. `GEMINI_MODEL` is required for classification; it has no silent mutable
  alias default. `GOOGLE_CLOUD_LOCATION` defaults to `global`, but the deployment owner
  must choose a location compatible with the configured model.
- Use JSON structured output and a Pydantic `response_schema`. Generation parameters are
  selected by an explicit model-family policy: Gemini 3 requests use a compatible
  `thinking_level` and omit `temperature`, `top_p`, and `top_k`; only a known compatible
  non-Gemini-3 family receives `temperature=0`. Unknown models receive no custom sampling
  parameter rather than an incompatible one.
- The prompt carries no title, artist, country, chart, rank, streams, platform, TikTok
  data, externally assigned genre, or research hypothesis. It carries lyric text and
  optional detected language only.
- Do not turn unavailable text, errors, or unclassifiable output into zero scores.
- Do not change the manual Streamlit taxonomy or its JSON repository in this increment.

## Existing architecture and selected seam

`LyricDocument` is the existing authoritative, rights-gated persistent representation
of stored lyric text and its content SHA-256. The current `SemanticAnnotation` table is
deliberately not reused: it stores one float per category/model and its uniqueness rule
cannot preserve an entire taxonomy response, prompt version, classification status, or
forced history.

Add the `lyrics.classification` module as a deep module at the automatic-classification
seam. Its small interface accepts an eligible lyric document plus an execution policy and
returns a persisted snapshot outcome. Internally it hides preflight status handling,
idempotency lookup, Gemini invocation, retry/backoff, Pydantic validation, and SQLAlchemy
persistence. A Gemini adapter is injected at that seam, enabling deterministic unit tests
without a real Google call.

The existing manual `ui.classifications.JsonClassificationRepository` and
`ui.taxonomy.CONTENT_TAXONOMY` remain separate adapters. No automatic output is projected
into manual records in this increment.

## Classification contract

Define Pydantic v2 models in `chart_observatory.lyrics.classification` for the complete
taxonomy. Integer intensity fields are constrained to `0..3`; confidence is constrained
to `0..1`; and all controlled vocabulary fields use `StrEnum` values.

The top-level structured result contains:

- `classification_status`: `classified`, `ambiguous`, `blocked`, or
  `language_unsupported` when Gemini can make that determination;
- `confidence`;
- `sexuality`: `sexual_explicitness`, `sexual_desire`, `sexual_innuendo`,
  `explicit_sexual_act`, and `explicit_sexual_anatomy`;
- `relationships`: `romantic_affection`, `heartbreak`, `infidelity`,
  `transactional_sex`, `casual_sex`, `jealousy_possession`, `reciprocity`, and consent
  (`not_applicable`, `explicit_mutual`, `implicit_mutual`, `ambiguous`, `coercive`, or
  `nonconsensual`);
- `gender_representation`: objectification, misogyny, sexual agency, status
  symbolization, commodification, target gender, and zero-or-more representation roles;
- `material_status`: money reference, materialism, conspicuous consumption, and wealth as
  status;
- four `antisocial` dimensions (`drugs_alcohol`, `crime`, `violence`, `weapons`), each
  holding independent `intensity` and `stance`;
- `territorial_identity`; and
- `romantic_summary`.

Every numeric intensity uses the shared meaning `0=absent`, `1=implicit/isolated`,
`2=explicit/relevant`, and `3=central/recurring/dominant`, unless the relevant taxonomy
definition states otherwise. The system prompt explicitly separates presence from stance:
mention, depiction, participation, territorial pride, money, sexual content, or
infidelity do not by themselves imply endorsement, normalization, glorification,
objectification, misogyny, or coercion.

The service derives `insufficient_text` locally for absent/blank/too-short text and
`instrumental` locally when trusted lyric metadata identifies it as instrumental. Provider
or validation failures create an `error` snapshot. These cases store no invented score
payload. The prompt need not and must not receive unrelated track metadata.

`TAXONOMY_VERSION` and `PROMPT_VERSION` are explicit immutable constants associated with
the contract. A changed prompt or taxonomy is a new reproducibility signature.

## Gemini adapter

Replace the partially migrated manual `httpx`/Bearer-token Vertex REST client with a
`GeminiLyricsClassifier` adapter using:

```python
genai.Client(
    vertexai=True,
    project=settings.google_cloud_project,
    location=settings.google_cloud_location,
    http_options=types.HttpOptions(api_version="v1"),
)
```

The SDK obtains ADC; the application does not read credential files, print tokens, or
construct authorization headers. `generate_content` receives the configured exact
`GEMINI_MODEL`, lyric-only contents, and `GenerateContentConfig` with `temperature=0`,
`response_mime_type="application/json"`, and the Pydantic `response_schema`. Returned
data is validated again with `model_validate` before it crosses the adapter seam.

The adapter uses an explicit `GenerationPolicy.for_model(model_id)`. Gemini 3 receives a
`ThinkingConfig` with a conservative `thinking_level` (configurable as `MINIMAL`, `LOW`,
`MEDIUM`, or `HIGH`); it receives no `temperature`, `top_p`, or `top_k`. Known compatible
legacy families receive `temperature=0`. Unknown models receive Structured Output with no
custom sampling or thinking parameter. The selected policy is unit-tested from the actual
SDK config arguments, so a model-family rule cannot silently reintroduce unsupported
parameters.

The adapter applies a finite timeout and bounded exponential backoff only to transient
network, service-unavailable, and rate-limit errors. Authentication errors, malformed
responses, safety blocks, and validation errors become recoverable persisted outcomes
without logging lyric text or credentials. Logging contains only snapshot/document IDs,
status, attempt count, token counts, and safe error type/message.

When the SDK provides `usage_metadata`, the adapter returns `prompt_token_count`,
`candidates_token_count`, `thoughts_token_count`, and `total_token_count`. It never
guesses unavailable usage values. A cost is calculated only when the configured immutable
rate card covers every billed token class returned by the SDK; otherwise it remains null.

## Persistence and idempotency

Create an immutable `lyric_classification_snapshots` table and SQLAlchemy model. It has:

- UUID `id` and `created_at` through the project mixins;
- non-null `lyric_document_id` foreign key;
- non-null `canonical_track_id` foreign key, validated against the lyric document by the
  repository before insert;
- indexed `lyrics_hash`, `model_id`, `taxonomy_version`, `prompt_version`, and
  `classification_status`;
- nullable `confidence`;
- nullable JSON `result_json` containing the entire validated Pydantic result;
- nullable `error` text;
- nullable `input_tokens`, `output_tokens`, `thought_tokens`, and `total_tokens` integers;
- nullable decimal `estimated_cost_usd`, calculated only from a configured compatible rate
  card and the returned SDK usage metadata;
- non-null `classified_at`; and
- nullable `forced_from_snapshot_id` self-reference for an auditable forced rerun.

The repository queries by the reproducibility signature:

`canonical_track_id + lyrics_hash + model_id + taxonomy_version + prompt_version`.

Normal execution skips if any matching snapshot exists, including a recorded recoverable
failure, so that re-running does not silently alter the evidence trail. `--force` always
inserts a new row and links it to the most recent matching snapshot; it never updates the
old row. The UUID snapshot identity, rather than a uniqueness constraint that would block
force, distinguishes executions. The CLI creates each candidate once per run, and the
repository performs the existence lookup immediately before calling Gemini to prevent
duplicates within the bounded worker pool.

Alembic receives one forward migration from `0012_track_metadata`, plus the matching
downgrade. The new model is imported in `db.models` so migration metadata remains complete.

## CLI and execution flow

Add `chart-observatory corpus classify-lyrics`. It opens the configured SQLAlchemy session
through the established `ResearchApplication`/`Settings` pattern and selects authorized
`LyricDocument` rows with text. It provides:

- `--limit` for a bounded run;
- `--force` for a new immutable snapshot despite a matching signature;
- `--only-unclassified` to restrict selection to tracks with no successful automatic
  classification snapshot;
- `--workers` with a conservative, validated default; and
- bounded request timeout/retry options where configuration is appropriate;
- `--estimate-cost`, which performs no content generation and reports candidate count,
  estimated input tokens, configured output-token allowance, and a nullable cost estimate;
  and
- `--max-cost-usd`, which calculates that preflight estimate and refuses to start content
  generation when the estimate exceeds the bound or a reliable estimate cannot be made.

The batch coordinator keeps at most `workers` futures in flight, following the existing
lyrics-backfill pattern. Cost estimation uses the SDK token-count operation where
available; output is a clearly labelled configured upper allowance, not an asserted
provider quote. It returns compact JSON counts (selected, skipped-idempotent, classified,
status outcomes, aggregate known token usage, aggregate known cost, and errors) and never
prints full lyric text. It does not perform a mass run automatically.

The older retrieval-oriented `corpus gemini-analyze` and `lyrics_backfill` flow is
refactored only as needed to remove the incompatible REST client and API-key-era behavior.
Automatic content classification is the new dedicated database-backed CLI flow, not an
append to the legacy analysis JSONL.

## Settings and documentation

`Settings` adds `gemini_model` with aliases for `GEMINI_MODEL` and its project-prefixed
equivalent. The existing Google project and location settings stay compatible, with
validated non-empty values before invoking the client. `pyproject.toml` and `uv.lock` add
the official `google-genai` dependency; the manual `google-auth` use introduced by the
working-tree migration is removed if it is no longer needed by other code.

`Settings` also provides a Gemini 3 thinking level and an optional immutable rate card:
input, output, and thought USD-per-million-token values plus an output-token allowance for
preflight estimation. Missing or incomplete rate-card values disable cost calculation;
they never produce a fictitious dollar value. `GOOGLE_CLOUD_LOCATION=global` remains a
default only for a model confirmed by its operator as globally available; documentation
requires a compatible regional location otherwise.

Create the missing root `README.md` with Windows/PowerShell instructions:

```powershell
gcloud config set project PROJECT_ID
gcloud services enable aiplatform.googleapis.com
gcloud auth application-default login
gcloud auth application-default set-quota-project PROJECT_ID
$env:GOOGLE_CLOUD_PROJECT = "PROJECT_ID"
$env:GOOGLE_CLOUD_LOCATION = "global"
$env:GEMINI_MODEL = "MODEL_ID_COMPATIVEL_E_FIXO"
chart-observatory db upgrade
chart-observatory corpus classify-lyrics --limit 5
```

The README explains that ADC login is interactive and must be completed by the user in a
browser, and that `application_default_credentials.json` must never be copied into the
repository. It also says that `global` is suitable only when the selected model supports
it and that the exact configured model is recorded in each snapshot.

## Verification

Unit tests use a mocked Gemini adapter/client and SQLite SQLAlchemy metadata. They cover:

1. all taxonomy bounds and enum rejections;
2. `google-genai` client construction for Vertex AI with project/location and no API key;
3. structured-output configuration, a lyric-only prompt, Pydantic response validation,
   Gemini 3 thinking-level policy without sampling parameters, compatible legacy
   `temperature=0` policy, and safe unknown-model policy;
4. blank/instrumental text receiving statuses rather than zero scores;
5. persisted snapshot audit fields and full JSON result;
6. same-signature idempotency avoiding a second provider call;
7. `--force` producing a second immutable snapshot and provider call;
8. telemetry extraction, nullable cost when rates/usage are incomplete, reliable actual
   cost calculation, `--estimate-cost`, and `--max-cost-usd` refusal;
9. retryable versus terminal failures, rate-limit handling, timeout, and bounded workers;
10. configuration loading and safe error logging; and
11. an optional `live`-marked smoke test that classifies one lyric only when ADC and the
    three required environment values are available.

Run `pytest`, `ruff check src tests`, and `mypy src/chart_observatory`. The optional smoke
test is never part of the default suite and never triggers a mass classification.
