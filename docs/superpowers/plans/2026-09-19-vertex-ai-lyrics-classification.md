# Vertex AI Lyrics Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist reproducible, automatic Gemini Vertex AI lyric-classification snapshots without changing the existing manual classification UI.

**Architecture:** `lyrics.classification` owns the immutable Pydantic taxonomy and model-family generation policy. `GeminiLyricsClassifier` in the existing Gemini pipeline file is the injected Vertex/ADC adapter; `lyrics.repository` owns SQLAlchemy snapshot queries/inserts; `classification_service` coordinates preflight, idempotency, cost protection, and bounded concurrent execution for the new Typer command.

**Tech Stack:** Python 3.12, Pydantic v2, `google-genai`, Vertex AI ADC, SQLAlchemy 2, Alembic, Typer, Tenacity, pytest.

**Spec:** `docs/superpowers/specs/2026-09-19-vertex-ai-lyrics-classification-design.md`

## Global Constraints

- Use only `google-genai` with Vertex AI and ADC; never use a Gemini API key, manual REST authorization header, or credential file.
- `GEMINI_MODEL` is required and its exact configured ID is recorded in every snapshot.
- Prompt input is lyric text plus optional language only; it excludes all title, artist, market, chart, performance, platform, TikTok, externally assigned genre, and hypothesis data.
- Gemini 3 uses `thinking_level` and omits custom sampling; only known compatible legacy models receive `temperature=0`; unknown models omit both.
- Automatic snapshot rows are immutable; `--force` creates a linked new row.
- Missing/insufficient/instrumental/error output must not become zero scores.
- Cost is null unless supplied SDK usage and a complete configured rate card allow a reliable calculation.
- Preserve `SemanticAnnotation` and `ui.classifications.JsonClassificationRepository`; do not change the Streamlit taxonomy.
- No commit, branch change, reset, restore, checkout, or classification mass run is authorized.

## Review Focus

- A Gemini 3 model must receive no `temperature`, `top_p`, or `top_k`, but must receive the configured thinking level.
- A safety-blocked, malformed, or transiently failing response must persist a safe non-zero-inventing status/error without leaking lyric text in logs.
- A matching previous `error` snapshot must remain idempotently skipped unless `--force` is supplied.
- `--max-cost-usd` must fail closed when the requested batch has an unreliable estimate, rather than allow an unbounded provider run.
- Input token counts must be stored even when output/thought metadata is absent; the missing values and total cost must remain null.

---

### Task 1: Classification contract, Settings, and dependency

**Files:**
- Create: `src/chart_observatory/lyrics/classification.py`
- Create: `tests/unit/lyrics/test_classification.py`
- Modify: `src/chart_observatory/config.py`
- Modify: `tests/unit/test_config.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Produces `LyricsClassification`, `ClassificationStatus`, `Stance`, `Consent`, `TargetGender`, `RepresentationRole`, `GenerationPolicy`, `UsageTelemetry`, and `CostRateCard`.
- Produces `Settings.gemini_model`, `gemini_thinking_level`, output allowance, and optional Decimal rate-card fields for later adapter/service tasks.

- [ ] **Step 1: Write failing taxonomy and policy tests**

```python
def test_gemini_3_policy_uses_thinking_without_sampling() -> None:
    policy = GenerationPolicy.for_model("gemini-3.5-flash", "MINIMAL")
    assert policy.temperature is None
    assert policy.thinking_level == "MINIMAL"

def test_classification_rejects_invalid_intensity_and_stance() -> None:
    with pytest.raises(ValidationError):
        AntisocialDimension(intensity=4, stance="glorified")
    with pytest.raises(ValidationError):
        AntisocialDimension(intensity=1, stance="celebrated")
```

- [ ] **Step 2: Run the focused tests and observe failure**

Run: `uv run pytest tests/unit/lyrics/test_classification.py tests/unit/test_config.py -v`  
Expected: FAIL because the classification contract and new Settings fields do not exist.

- [ ] **Step 3: Implement the smallest complete Pydantic contract and settings**

```python
class AntisocialDimension(BaseModel):
    intensity: int = Field(ge=0, le=3)
    stance: Stance

class GenerationPolicy(BaseModel, frozen=True):
    temperature: float | None = None
    thinking_level: ThinkingLevel | None = None

    @classmethod
    def for_model(cls, model_id: str, thinking_level: ThinkingLevel) -> "GenerationPolicy":
        return cls(thinking_level=thinking_level) if model_id.startswith("gemini-3") else cls(
            temperature=0.0 if model_id.startswith("gemini-2") else None
        )
```

Define every taxonomy section from the approved spec, constrained enums, nullable usage fields,
and Decimal rate-card calculation that returns `None` for incomplete rates/usage. Add environment
aliases for `GEMINI_MODEL`, `GEMINI_THINKING_LEVEL`, and the three USD-per-million-token rates.
Add `google-genai` to project dependencies with a bounded major version, regenerate `uv.lock`, and
do not retain `google-auth` solely for the replaced manual client.

- [ ] **Step 4: Run contract, configuration, formatting, and typing checks**

Run: `uv run pytest tests/unit/lyrics/test_classification.py tests/unit/test_config.py -v; uv run ruff check src/chart_observatory/config.py src/chart_observatory/lyrics/classification.py tests/unit/lyrics/test_classification.py tests/unit/test_config.py; uv run mypy src/chart_observatory/config.py src/chart_observatory/lyrics/classification.py`  
Expected: PASS.

### Task 2: Immutable snapshot persistence

**Files:**
- Modify: `src/chart_observatory/db/models/corpus.py`
- Modify: `src/chart_observatory/db/models/__init__.py`
- Modify: `src/chart_observatory/lyrics/repository.py`
- Create: `migrations/versions/0013_lyric_classification_snapshots.py`
- Create: `tests/unit/lyrics/test_classification_repository.py`

**Interfaces:**
- Consumes `LyricsClassification`, `UsageTelemetry`, and `CostRateCard` from Task 1.
- Produces `LyricClassificationSnapshot`, `ClassificationSnapshotInput`, `find_matching_snapshot`, and `append_classification_snapshot`.

- [ ] **Step 1: Write failing repository tests**

```python
def test_matching_signature_skips_and_force_appends_immutable_history(session, lyric_document) -> None:
    first = append_classification_snapshot(session, snapshot_input(lyric_document))
    assert find_matching_snapshot(session, signature(lyric_document)) == first
    forced = append_classification_snapshot(session, snapshot_input(lyric_document, forced_from=first.id))
    assert forced.id != first.id
    assert forced.forced_from_snapshot_id == first.id
```

Also assert document/track mismatch is rejected, status-only rows have null result JSON, full Pydantic
output is stored as JSON, and partial usage leaves nullable fields/cost intact.

- [ ] **Step 2: Run the focused test and observe failure**

Run: `uv run pytest tests/unit/lyrics/test_classification_repository.py -v`  
Expected: FAIL because the snapshot ORM model and repository functions do not exist.

- [ ] **Step 3: Add model, repository functions, and Alembic migration**

```python
class LyricClassificationSnapshot(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "lyric_classification_snapshots"
    lyric_document_id: Mapped[UUID] = mapped_column(ForeignKey("lyric_documents.id"), index=True)
    canonical_track_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_tracks.id"), index=True)
    lyrics_hash: Mapped[str] = mapped_column(String(64), index=True)
    model_id: Mapped[str] = mapped_column(String(160), index=True)
    taxonomy_version: Mapped[str] = mapped_column(String(80), index=True)
    prompt_version: Mapped[str] = mapped_column(String(80), index=True)
    result_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
```

Add the statuses, confidence, error, classified timestamp, four token fields, nullable Numeric cost,
and `forced_from_snapshot_id`. Query the five-field signature before insertion without an SQL unique
constraint, because forced executions must retain duplicate signatures. Make the migration descend
from `0012_track_metadata`, create indexes for signature lookup, and remove only this table/indexes
in downgrade.

- [ ] **Step 4: Run repository tests and migration metadata check**

Run: `uv run pytest tests/unit/lyrics/test_classification_repository.py tests/unit/lyrics/test_repository.py -v; uv run python -c "from chart_observatory.db.base import Base; from chart_observatory.db import models; assert 'lyric_classification_snapshots' in Base.metadata.tables"`  
Expected: PASS.

### Task 3: Vertex SDK adapter and telemetry

**Files:**
- Modify: `src/chart_observatory/lyrics/gemini_pipeline.py`
- Modify: `tests/unit/lyrics/test_gemini_pipeline.py`

**Interfaces:**
- Consumes `LyricsClassification`, `GenerationPolicy`, and `UsageTelemetry` from Task 1.
- Produces `GeminiLyricsClassifier.classify(lyrics: str, language: str | None) -> GeminiClassificationResponse` and `estimate_input_tokens(lyrics: str, language: str | None) -> int | None`.

- [ ] **Step 1: Write mocked SDK tests**

```python
def test_vertex_client_uses_adc_and_structured_schema_without_biasing_metadata(monkeypatch) -> None:
    classifier = GeminiLyricsClassifier(project_id="project", location="global", model_id="gemini-3.5-flash")
    response = classifier.classify("lyric only", language="pt")
    assert fake_client.calls[0].config.response_schema is LyricsClassification
    assert "title" not in fake_client.calls[0].contents.casefold()
    assert fake_client.calls[0].config.temperature is None

def test_usage_metadata_is_extracted_without_inventing_missing_tokens() -> None:
    assert extract_usage(fake_usage(prompt_token_count=10)) == UsageTelemetry(input_tokens=10)
```

Include tests for Pydantic validation, rate-limit retry, terminal auth failure, blocked output, a
Gemini-2 temperature policy, Gemini-3 `ThinkingConfig`, count-tokens invocation, and no manual HTTP
URL/header/client construction.

- [ ] **Step 2: Run adapter tests and observe failure**

Run: `uv run pytest tests/unit/lyrics/test_gemini_pipeline.py -v`  
Expected: FAIL against the existing REST `GeminiAnnotationClient` behavior.

- [ ] **Step 3: Refactor the existing Gemini implementation to the SDK adapter**

```python
client = genai.Client(
    vertexai=True,
    project=project_id,
    location=location,
    http_options=types.HttpOptions(api_version="v1"),
)
response = client.models.generate_content(
    model=model_id,
    contents=build_lyrics_only_prompt(lyrics, language),
    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=LyricsClassification, **policy.sdk_kwargs()),
)
```

Delete manual bearer token refresh, URL construction, HTTP headers, and API-key compatibility from
the classification path. Keep `LrclibClient` and `LyricsOvhClient` unchanged. Build a thread-local
SDK client only where the batch worker needs it, apply Tenacity retry predicates solely to retryable
provider conditions, and parse SDK `usage_metadata` field-by-field.

- [ ] **Step 4: Run adapter regression checks**

Run: `uv run pytest tests/unit/lyrics/test_gemini_pipeline.py tests/unit/lyrics/test_backfill_recovery.py -v; uv run ruff check src/chart_observatory/lyrics/gemini_pipeline.py tests/unit/lyrics/test_gemini_pipeline.py; uv run mypy src/chart_observatory/lyrics/gemini_pipeline.py`  
Expected: PASS.

### Task 4: Service, bounded batch execution, and Typer CLI

**Files:**
- Create: `src/chart_observatory/lyrics/classification_service.py`
- Create: `tests/unit/lyrics/test_classification_service.py`
- Modify: `src/chart_observatory/cli.py`
- Create: `tests/unit/lyrics/test_classification_cli.py`

**Interfaces:**
- Consumes snapshot repository functions from Task 2 and `GeminiLyricsClassifier` from Task 3.
- Produces `LyricsClassificationService.run(request) -> ClassificationRunSummary` and the `corpus classify-lyrics` command.

- [ ] **Step 1: Write failing service and CLI tests**

```python
def test_same_signature_does_not_call_classifier_twice(session, document, fake_classifier) -> None:
    service = LyricsClassificationService(session, fake_classifier, settings())
    service.run(one_document_request(document))
    service.run(one_document_request(document))
    assert fake_classifier.call_count == 1

def test_max_cost_rejects_unknown_or_excessive_estimate() -> None:
    with pytest.raises(CostLimitExceeded):
        service.run(ClassificationRequest(estimate_cost=True, max_cost_usd=Decimal("0.01")))
```

Add CLI tests for `--limit 5`, `--force`, `--only-unclassified`, `--estimate-cost`, compact JSON
summary, an insufficient-text row, controlled worker maximum, and no real SDK invocation.

- [ ] **Step 2: Run the focused tests and observe failure**

Run: `uv run pytest tests/unit/lyrics/test_classification_service.py tests/unit/lyrics/test_classification_cli.py -v`  
Expected: FAIL because the service and command do not exist.

- [ ] **Step 3: Implement preflight, cost guard, and CLI**

```python
@corpus_app.command("classify-lyrics")
def corpus_classify_lyrics(
    database_url: str | None = typer.Option(None, envvar="CHART_OBSERVATORY_DATABASE_URL"),
    limit: int | None = typer.Option(None, min=1),
    force: bool = typer.Option(False),
    only_unclassified: bool = typer.Option(False),
    estimate_cost: bool = typer.Option(False),
    max_cost_usd: Decimal | None = typer.Option(None, min=0),
    workers: int = typer.Option(2, min=1, max=8),
) -> None:
    settings = Settings.load(Path.cwd())
    application = ResearchApplication(Path("data/runtime"), database_url=database_url or settings.database_url)
    service = LyricsClassificationService(
        application.session, GeminiLyricsClassifier.from_settings(settings), settings
    )
    summary = service.run(
        ClassificationRequest(limit, force, only_unclassified, estimate_cost, max_cost_usd, workers)
    )
    typer.echo(json.dumps(summary.to_json()))
```

Select only authorized stored lyric documents. Return `insufficient_text` and `instrumental` snapshot
outcomes without calling Gemini; call the repository's signature lookup immediately before provider
work; submit no more than `workers` pending futures; and call `session.commit()` after each durable outcome. In
estimate-only mode do no `generate_content` call. Before a normal run with a max cost, compute the
same preflight estimate and raise a Typer parameter error if it is unknown or above the cap. Include
aggregate known token/cost totals but no lyric text in output/logging.

- [ ] **Step 4: Run service and CLI checks**

Run: `uv run pytest tests/unit/lyrics/test_classification_service.py tests/unit/lyrics/test_classification_cli.py -v; uv run ruff check src/chart_observatory/lyrics/classification_service.py src/chart_observatory/cli.py tests/unit/lyrics; uv run mypy src/chart_observatory/lyrics/classification_service.py src/chart_observatory/cli.py`  
Expected: PASS.

### Task 5: Documentation, optional smoke test, and full verification

**Files:**
- Create: `README.md`
- Create: `tests/live/test_vertex_lyrics_classification_smoke.py`
- Modify: `research/gemini_lyrics_pipeline_usage_2026-09-10.md`

**Interfaces:**
- Documents the configured CLI from Task 4 and leaves existing manual/UI flows unchanged.

- [ ] **Step 1: Write a collection-safe live smoke test**

```python
@pytest.mark.live
def test_classifies_one_lyric_with_adc() -> None:
    pytest.skipif(not adc_smoke_is_configured(), reason="ADC smoke configuration is absent")
    assert run_one_fixture_lyric().classification_status in {"classified", "ambiguous"}
```

The test must require an explicit opt-in environment flag plus project, location, and model; it must
never select from the production database or execute more than its one fixture lyric.

- [ ] **Step 2: Run the default suite and prove the smoke test is not collected as a live call**

Run: `uv run pytest tests/live/test_vertex_lyrics_classification_smoke.py -v; uv run pytest -m 'not live' -q`  
Expected: smoke test SKIPPED without opt-in; default suite makes no Vertex request.

- [ ] **Step 3: Write user documentation**

Add exact PowerShell setup commands for project selection, API enablement, interactive browser ADC
login, quota-project setting, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and a pinned compatible
`GEMINI_MODEL`. State that credentials must not be copied into the repository. Document location/model
compatibility, rate-card requirements for dollar estimates, and these bounded commands:

```powershell
chart-observatory db upgrade
chart-observatory corpus classify-lyrics --limit 5
chart-observatory corpus classify-lyrics --limit 5 --estimate-cost
```

- [ ] **Step 4: Run full non-live verification and inspect the diff**

Run: `uv run pytest -m 'not live'; uv run ruff check src tests; uv run mypy src/chart_observatory; git diff --check; git status --short`  
Expected: all non-live checks pass, no whitespace errors, no classification provider request, and only intended source/test/migration/documentation changes are present.
