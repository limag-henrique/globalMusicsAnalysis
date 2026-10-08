# Gemini Batch Lyrics Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify every remaining authorized lyric through cost-controlled Gemini 3.8 Flash batch jobs while preserving scientific reproducibility, item-level failure evidence, and private temporary storage.

**Architecture:** A deep `BatchClassificationService` coordinates a PostgreSQL run/item ledger, canonical JSONL exporter, private Cloud Storage adapter, Vertex batch adapter, streaming importer, and pilot quality report. The online and batch paths share one prompt and one sanitized JSON Schema, while immutable `lyric_classification_snapshots` remain the scientific system of record.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy 2, PostgreSQL 18, Alembic, Typer, `google-genai`, `google-cloud-storage`, Vertex AI ADC, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-26-gemini-batch-lyrics-classification-design.md`

## Global Constraints

- Work only on the current branch; never switch branches.
- Never create a Git commit automatically. Every task ends at a human review checkpoint; only a human may choose and run a commit.
- Preserve all pre-existing working-tree changes and the active run log.
- Use Vertex AI and ADC only; reject `GEMINI_API_KEY` and `GOOGLE_API_KEY`.
- Pin `gemini-3.8-flash`, location `global`, and `GEMINI_THINKING_LEVEL=LOW` for batch submission.
- Never send title, artist, country, genre, chart, rank, streams, platform, or research hypothesis to Gemini.
- Send only control instructions/schema plus lyric text and optional language; the opaque key stays outside the model request.
- Never use `--force`; error revalidation is an explicit `retry-errors` workflow linked through `forced_from_snapshot_id`.
- Never automatically resubmit a failed, cancelled, or expired provider job.
- Never log lyric text, prompts, model payloads, credentials, tokens, or signed URLs.
- Keep snapshots immutable; operational batch run/item rows are mutable.
- Default safety limits are 190,000 requests and 900 MiB per JSONL file.
- Cloud Storage artifacts use Standard storage, public-access prevention, uniform bucket-level access, no versioning, no soft delete, and deletion after seven days.
- Stop the pre-existing online runner at a completed five-song boundary before applying the migration or preparing a batch.

## Review Focus

- **Provider accepts a JSONL line but does not round-trip `key`:** the one-item canary must block pilot/main submission and persist a safe error without moving the key into the prompt (Task 7).
- **Upload succeeds but the create-job response is lost:** submit must discover the unique display name and attach the existing job instead of creating a duplicate billable job (Task 6).
- **Output repeats a known key with a different echoed request:** append a fingerprint-mismatch error for that item, stop further import, and retain already committed rows (Task 7).
- **Lifecycle is correct but soft delete remains enabled through inherited/default configuration:** preflight must fail closed because deleted lyrics would remain retained and billable (Task 5).
- **Pilot statistics are absent or insufficient for a positive estimate:** main preparation must refuse to submit rather than convert missing evidence into a zero estimate (Tasks 4 and 8).

---

## File structure

- `src/chart_observatory/lyrics/classification.py`: existing scientific taxonomy and common rate-card types.
- `src/chart_observatory/lyrics/gemini_pipeline.py`: shared prompt, supported JSON Schema, generation policy, and online adapter.
- `src/chart_observatory/lyrics/classification_queue.py`: shared remaining-candidate selection, local terminal statuses, and PostgreSQL advisory lock.
- `src/chart_observatory/lyrics/batch_contract.py`: batch enums, immutable request/result dataclasses, limits, and state-transition rules.
- `src/chart_observatory/db/models/lyrics_batch.py`: mutable batch run/item ORM models.
- `src/chart_observatory/lyrics/batch_repository.py`: run/item reservation and state persistence.
- `src/chart_observatory/lyrics/batch_jsonl.py`: canonical request serialization, validation, splitting, hashing, and cost estimation.
- `src/chart_observatory/lyrics/batch_storage.py`: Cloud Storage security preflight, upload/download, and exact-prefix cleanup.
- `src/chart_observatory/lyrics/batch_vertex.py`: Vertex batch submission, ambiguity recovery, and status normalization.
- `src/chart_observatory/lyrics/batch_importer.py`: streaming reconciliation, Pydantic validation, snapshots, finalization, and explicit error retry selection.
- `src/chart_observatory/lyrics/batch_quality.py`: pilot distributions and optional human-agreement calculations.
- `src/chart_observatory/lyrics/batch_service.py`: the small public orchestration interface used by CLI commands.
- `migrations/versions/0015_gemini_batch_classification.py`: ledger tables, active-reservation index, and snapshot traceability columns.
- `tests/unit/lyrics/test_batch_*.py`: focused contract, repository, JSONL, storage, Vertex, importer, quality, service, and CLI tests.
- `tests/integration/lyrics/test_batch_postgresql.py`: advisory-lock, partial-index, migration, and transactional reservation checks.
- `tests/live/test_vertex_lyrics_batch_canary.py`: explicitly opted-in one-item Vertex/GCS contract test.

### Task 1: Shared prompt, JSON Schema, generation policy, and batch settings

**Files:**
- Modify: `src/chart_observatory/lyrics/gemini_pipeline.py:123-320`
- Modify: `src/chart_observatory/config.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `tests/unit/lyrics/test_gemini_pipeline.py`
- Modify: `tests/unit/test_config.py`
- Create: `tests/unit/lyrics/test_batch_contract.py`

**Interfaces:**
- Produces `build_lyrics_prompt(lyrics: str, language: str | None) -> str`.
- Produces `lyrics_response_json_schema() -> dict[str, object]`.
- Produces `build_lyrics_generation_config(model_id: str, thinking_level: ThinkingLevel | str, max_output_tokens: int | None) -> types.GenerateContentConfig`.
- Produces Settings fields `gemini_batch_bucket`, `gemini_batch_input_usd_per_million_tokens`, and `gemini_batch_output_usd_per_million_tokens`.
- Adds runtime dependency `google-cloud-storage>=3,<4`.

- [x] **Step 1: Write failing shared-contract and configuration tests**

```python
def test_online_and_batch_schema_is_json_serializable_and_identical() -> None:
    schema = lyrics_response_json_schema()
    assert json.loads(json.dumps(schema)) == schema
    assert schema["required"] == list(LyricsClassification.model_fields)
    assert "default" not in json.dumps(schema)

def test_gemini_38_low_omits_sampling_parameters() -> None:
    config = build_lyrics_generation_config("gemini-3.8-flash", "LOW", 1024)
    payload = config.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert payload["thinkingConfig"] == {"thinkingLevel": "LOW"}
    assert payload["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in payload
    assert not {"temperature", "topP", "topK", "candidateCount"} & payload.keys()

def test_batch_settings_use_unprefixed_environment_aliases(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_BATCH_BUCKET", "private-lyrics-batch")
    monkeypatch.setenv("GEMINI_BATCH_INPUT_USD_PER_MILLION_TOKENS", "0.375")
    monkeypatch.setenv("GEMINI_BATCH_OUTPUT_USD_PER_MILLION_TOKENS", "1.875")
    settings = Settings.load(PROJECT_ROOT)
    assert settings.gemini_batch_bucket == "private-lyrics-batch"
    assert settings.gemini_batch_input_usd_per_million_tokens == Decimal("0.375")
    assert settings.gemini_batch_output_usd_per_million_tokens == Decimal("1.875")
```

- [x] **Step 2: Run the focused tests and verify RED**

Run: `uv run pytest tests/unit/lyrics/test_gemini_pipeline.py tests/unit/lyrics/test_batch_contract.py tests/unit/test_config.py -v`  
Expected: FAIL because the public builders and batch settings do not exist.

- [x] **Step 3: Implement the shared wire contract**

Rename the private prompt helper to `build_lyrics_prompt`. Generate JSON Schema from
`LyricsClassification.model_json_schema()`, recursively retain only provider-supported
keywords (`$defs`, `$ref`, `type`, `title`, `description`, `enum`, `items`, `minimum`,
`maximum`, `anyOf`, `properties`, `additionalProperties`, `required`), and cache a deep
copy-safe result. Make the online classifier use `response_json_schema` through
`build_lyrics_generation_config`; do not keep a second schema path using the class object.

- [x] **Step 4: Add batch settings and storage dependency**

Add nullable batch-rate settings with exact aliases and a nullable bucket name. Add
`google-cloud-storage>=3,<4`, regenerate `uv.lock`, and leave prices out of source defaults.

- [x] **Step 5: Run tests, lint, and typing; stop for human review**

Run: `uv run pytest tests/unit/lyrics/test_gemini_pipeline.py tests/unit/lyrics/test_batch_contract.py tests/unit/test_config.py -v`  
Run: `uv run ruff check src/chart_observatory/lyrics/gemini_pipeline.py src/chart_observatory/config.py tests/unit/lyrics/test_batch_contract.py`  
Run: `uv run mypy src/chart_observatory/lyrics/gemini_pipeline.py src/chart_observatory/config.py`  
Expected: all PASS. Do not commit; present the diff to the human.

### Task 2: Batch ledger models, migration, and snapshot traceability

**Files:**
- Create: `src/chart_observatory/db/models/lyrics_batch.py`
- Modify: `src/chart_observatory/db/models/corpus.py:220-262`
- Modify: `src/chart_observatory/db/models/__init__.py`
- Create: `migrations/versions/0015_gemini_batch_classification.py`
- Create: `tests/unit/lyrics/test_batch_migration.py`
- Modify: `tests/unit/lyrics/test_classification_repository.py`

**Interfaces:**
- Produces ORM models `LyricClassificationBatchRun` and `LyricClassificationBatchItem`.
- `LyricClassificationBatchRun` includes nullable `pilot_accepted_at` and
  `pilot_accepted_by`; only a successfully imported pilot run may populate them.
- Extends `LyricClassificationSnapshot` with `provider_model_version`, `execution_mode`, `batch_run_id`, and `batch_item_key`.
- Extends `ClassificationSnapshotInput` and `append_classification_snapshot` with the same nullable traceability fields.

- [x] **Step 1: Write failing metadata and migration tests**

```python
def test_batch_metadata_has_active_signature_index() -> None:
    index = next(i for i in LyricClassificationBatchItem.__table__.indexes
                 if i.name == "uq_lyric_batch_items_active_signature")
    assert index.dialect_options["postgresql"]["where"] is not None

def test_batch_snapshot_traceability_is_persisted(session, lyric_document) -> None:
    run = make_batch_run(session)
    item = make_batch_item(session, run, lyric_document)
    row = append_classification_snapshot(
        session,
        snapshot_input(lyric_document, batch_run_id=run.id,
                       batch_item_key=item.opaque_key,
                       provider_model_version="gemini-3.8-flash@001",
                       execution_mode="batch"),
    )
    assert row.batch_item_key == item.opaque_key
    assert row.execution_mode == "batch"
```

Migration tests must also assert `down_revision == "0014_lyric_classification_queue"`,
revision length at most 32, upgrade/downgrade table order, nullable additions for existing
snapshots, and the PostgreSQL partial predicate over active states.

- [x] **Step 2: Run the focused tests and verify RED**

Run: `uv run pytest tests/unit/lyrics/test_batch_migration.py tests/unit/lyrics/test_classification_repository.py -v`  
Expected: FAIL because ledger models and migration 0015 do not exist.

- [x] **Step 3: Implement the ORM and Alembic migration**

Use string states constrained by application enums rather than PostgreSQL enum types.
Create indexed foreign keys for run/item/document/track relationships, unique `(run_id,
line_number)` and `(run_id, opaque_key)` constraints, and the partial active-signature
index over `reserved`, `submitted`, and `running`. Keep item `snapshot_id` nullable and
validate it in the repository to avoid mutation of snapshot rows.

- [x] **Step 4: Extend snapshot append persistence**

Add nullable parameters to `ClassificationSnapshotInput`; validate that a supplied batch
item matches document, track, hash, model, taxonomy, prompt, and run before appending.
Existing online callers continue to default to `execution_mode="online"`.

- [x] **Step 5: Verify migration/model behavior; stop for human review**

Run: `uv run pytest tests/unit/lyrics/test_batch_migration.py tests/unit/lyrics/test_classification_repository.py tests/unit/lyrics/test_classification_snapshot_migration.py -v`  
Run: `uv run chart-observatory db upgrade` against a disposable PostgreSQL test database, then inspect `alembic_version` for `0015_gemini_batch_classification`.  
Expected: all PASS. Do not run the migration against the imported production database yet. Do not commit.

### Task 3: Shared candidate queue, advisory lock, and atomic reservation

**Files:**
- Create: `src/chart_observatory/lyrics/classification_queue.py`
- Create: `src/chart_observatory/lyrics/batch_contract.py`
- Create: `src/chart_observatory/lyrics/batch_repository.py`
- Modify: `src/chart_observatory/lyrics/classification_service.py`
- Create: `tests/unit/lyrics/test_classification_queue.py`
- Create: `tests/unit/lyrics/test_batch_repository.py`
- Create: `tests/integration/lyrics/test_batch_postgresql.py`

**Interfaces:**
- Produces frozen `ClassificationSignature` and `ClassificationCandidate` dataclasses.
- Produces `local_classification_status(candidate: ClassificationCandidate) -> str | None`.
- Produces `select_remaining_candidates(session: Session, signature: ClassificationSignature, limit: int | None, exclude_active_batch: bool = True) -> list[ClassificationCandidate]`.
- Produces `classification_queue_lock(session: Session) -> AbstractContextManager[None]` using a fixed session-level PostgreSQL advisory-lock key and a SQLite no-op.
- Produces `BatchRunKind`, `BatchRunState`, `BatchItemState`, `BatchPreparationRequest`,
  `BatchPreparation`, and `BatchRetryCandidate`, plus explicit transition validation.
- Produces `BatchRepository.prepare_run(request: BatchPreparationRequest) -> LyricClassificationBatchRun` and read/update methods consumed by later tasks.

- [x] **Step 1: Write failing selection, locking, and reservation tests**

```python
def test_selection_excludes_handled_and_active_batch_signatures(session) -> None:
    candidates = select_remaining_candidates(session, SIGNATURE, limit=None)
    assert [item.lyric_document_id for item in candidates] == [remaining_document.id]

def test_prepare_run_reserves_candidates_with_random_opaque_keys(session) -> None:
    run = BatchRepository(session).prepare_run(PILOT_REQUEST)
    items = BatchRepository(session).items(run.id)
    assert len(items) == 99
    assert len({item.opaque_key for item in items}) == 99
    assert all(item.opaque_key not in {item.lyric_document_id, item.canonical_track_id}
               for item in items)

def test_second_postgresql_queue_lock_fails_fast(postgresql_sessions) -> None:
    with classification_queue_lock(postgresql_sessions.first):
        with pytest.raises(ClassificationQueueBusy):
            with classification_queue_lock(postgresql_sessions.second):
                pass
```

Also pin deterministic ordering, one document per reproducibility signature, instrumentals
and short text excluded from provider candidates, invalid state transitions, and rollback
of all reservations when preparation fails.

- [x] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/unit/lyrics/test_classification_queue.py tests/unit/lyrics/test_batch_repository.py -v`  
Expected: FAIL because queue and repository modules do not exist.

- [x] **Step 3: Extract and reuse the queue logic**

Move candidate dataclasses, authorized selection, handled-status filtering, and local-status
logic out of `LyricsClassificationService`. Wrap each online `run` call in the shared lock
and retain current observable behavior and tests.

- [x] **Step 4: Implement atomic batch reservation and transition checks**

`prepare_run` acquires the same lock, persists local terminal snapshots, creates a run,
creates items for provider candidates, flushes, and commits once. A failed write rolls back
the run and every reservation. All mutable state changes pass through a transition table;
direct arbitrary state assignment is not part of the repository interface.

- [x] **Step 5: Verify unit and PostgreSQL concurrency tests; stop for human review**

Run: `uv run pytest tests/unit/lyrics/test_classification_queue.py tests/unit/lyrics/test_batch_repository.py tests/unit/lyrics/test_classification_service.py -v`  
Run: `uv run pytest tests/integration/lyrics/test_batch_postgresql.py -v -m integration`  
Expected: all PASS with PostgreSQL available. Do not commit.

### Task 4: Canonical JSONL exporter, limits, integrity, and cost estimates

**Files:**
- Create: `src/chart_observatory/lyrics/batch_jsonl.py`
- Create: `tests/unit/lyrics/test_batch_jsonl.py`
- Modify: `tests/unit/lyrics/test_batch_repository.py`

**Interfaces:**
- Produces `BatchJsonlArtifact(path: Path, sha256: str, byte_count: int, request_count: int, first_key: UUID, last_key: UUID)`.
- Produces `BatchExportItem`, `PilotUsage`, and `BatchCostEstimate` frozen dataclasses used
  by the exporter, estimator, and orchestrator.
- Produces `build_batch_request(item: LyricClassificationBatchItem, candidate: ClassificationCandidate, config: types.GenerateContentConfig) -> dict[str, object]`.
- Produces `write_batch_jsonl(run_id: UUID, items: Iterable[BatchExportItem], directory: Path, *, max_requests: int = 190_000, max_bytes: int = 900 * 1024 * 1024) -> list[BatchJsonlArtifact]`.
- Produces `validate_batch_jsonl(path: Path, expected: Mapping[UUID, str]) -> BatchJsonlArtifact`.
- Produces `estimate_batch_cost(artifacts: Sequence[BatchJsonlArtifact], exact_input_tokens: Sequence[int] | None, pilot_usage: Sequence[PilotUsage], rate_card: CostRateCard, max_output_tokens: int) -> BatchCostEstimate`.

- [x] **Step 1: Write failing serialization, privacy, splitting, and estimate tests**

```python
def test_request_contains_only_key_and_lyric_request(batch_export_item) -> None:
    payload = build_batch_request(batch_export_item.item, batch_export_item.candidate, CONFIG)
    encoded = json.dumps(payload)
    assert set(payload) == {"key", "request"}
    assert payload["key"] == str(batch_export_item.item.opaque_key)
    assert "Artist Name" not in encoded
    assert "chart_rank" not in encoded
    assert "responseJsonSchema" in encoded

def test_writer_splits_before_request_or_byte_safety_limit(tmp_path) -> None:
    artifacts = write_batch_jsonl(RUN_ID, THREE_ITEMS, tmp_path,
                                  max_requests=2, max_bytes=10_000)
    assert [artifact.request_count for artifact in artifacts] == [2, 1]

def test_estimate_refuses_missing_pilot_usage() -> None:
    with pytest.raises(CostEstimateUnavailable):
        estimate_batch_cost(ARTIFACTS, None, [], RATE_CARD, 1024)
```

Tests must parse every produced line, assert canonical compact UTF-8 serialization, verify
request SHA-256 against the ledger, reject duplicate/unknown keys and structural forbidden
metadata, and prove expected/conservative estimates are positive. The conservative formula
uses at most one input token per UTF-8 request byte plus `request_count * max_output_tokens`
at the configured batch output/reasoning rate.

- [x] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/unit/lyrics/test_batch_jsonl.py -v`  
Expected: FAIL because the JSONL module does not exist.

- [x] **Step 3: Implement streaming canonical export and validation**

Write to a temporary file with `ensure_ascii=False`, compact separators, sorted envelope
keys, newline termination, incremental SHA-256, and size checks before appending each line.
Never load all lyrics or serialized lines into memory. Persist each request hash and line
number through `BatchRepository` only after the artifact validates.

- [x] **Step 4: Implement exact pilot and inferred-main cost estimates**

Canary/pilot uses exact `count_tokens` results for at most 100 items. Main expected input
uses the pilot median input-token/request-byte ratio and median output+thought tokens; the
conservative maximum uses the byte/output ceiling formula. Return null nowhere: unavailable
or non-positive values raise `CostEstimateUnavailable`.

- [x] **Step 5: Verify focused tests, lint, and typing; stop for human review**

Run: `uv run pytest tests/unit/lyrics/test_batch_jsonl.py tests/unit/lyrics/test_batch_repository.py -v`  
Run: `uv run ruff check src/chart_observatory/lyrics/batch_jsonl.py tests/unit/lyrics/test_batch_jsonl.py`  
Run: `uv run mypy src/chart_observatory/lyrics/batch_jsonl.py`  
Expected: all PASS. Do not commit.

### Task 5: Private Cloud Storage adapter and lifecycle preflight

**Files:**
- Create: `src/chart_observatory/lyrics/batch_storage.py`
- Create: `tests/unit/lyrics/test_batch_storage.py`

**Interfaces:**
- Produces `BucketSecurityReport` with project, location, storage class, public-access prevention, uniform access, versioning, soft-delete retention seconds, lifecycle delete age, and service-agent access.
- Produces `UploadedBatchObject(uri: str, generation: int, sha256: str, byte_count: int)`.
- Produces `BatchStorage.preflight(bucket_name: str, project_id: str, service_agent: str) -> BucketSecurityReport`.
- Produces `BatchStorage.upload(artifact: BatchJsonlArtifact, object_name: str) -> UploadedBatchObject` with generation-match zero.
- Produces `BatchStorage.iter_output_lines(prefix: str) -> Iterator[bytes]`.
- Produces `BatchStorage.delete_exact_prefix(prefix: str, expected_objects: Collection[str]) -> int`.

- [x] **Step 1: Write failing bucket and object-safety tests**

```python
@pytest.mark.parametrize("defect", [
    "public_access_not_enforced", "uniform_access_disabled", "versioning_enabled",
    "soft_delete_enabled", "missing_seven_day_delete", "service_agent_cannot_read_write",
])
def test_preflight_fails_closed_for_insecure_bucket(defect, storage_fixture) -> None:
    with pytest.raises(BucketSecurityError, match=defect):
        storage_fixture(defect).preflight(BUCKET, PROJECT, SERVICE_AGENT)

def test_upload_uses_no_overwrite_precondition(fake_storage, artifact) -> None:
    uploaded = fake_storage.upload(artifact, "runs/run-id/input.jsonl")
    assert fake_storage.upload_kwargs["if_generation_match"] == 0
    assert uploaded.sha256 == artifact.sha256
```

Also test that `delete_exact_prefix` rejects bucket roots, parent prefixes, unexpected
objects, and generation changes; output iteration must be deterministic across multiple
JSONL shards and must not log bytes.

- [x] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/unit/lyrics/test_batch_storage.py -v`  
Expected: FAIL because the storage adapter does not exist.

- [x] **Step 3: Implement read-only bucket preflight and guarded object operations**

Use `google.cloud.storage.Client(project=project_id)` with ADC. Runtime code validates but
does not alter bucket IAM/lifecycle/security. Upload sets SHA-256 metadata, verifies object
size/generation/hash after reload, and deletes the local temporary file only after success.
Cleanup enumerates the exact recorded run prefix and requires an exact expected-object set.

- [x] **Step 4: Verify tests, lint, and typing; stop for human review**

Run: `uv run pytest tests/unit/lyrics/test_batch_storage.py -v`  
Run: `uv run ruff check src/chart_observatory/lyrics/batch_storage.py tests/unit/lyrics/test_batch_storage.py`  
Run: `uv run mypy src/chart_observatory/lyrics/batch_storage.py`  
Expected: all PASS. Do not create or modify a real bucket in this task. Do not commit.

### Task 6: Vertex batch adapter and duplicate-submission recovery

**Files:**
- Create: `src/chart_observatory/lyrics/batch_vertex.py`
- Create: `tests/unit/lyrics/test_batch_vertex.py`

**Interfaces:**
- Produces normalized `VertexBatchJob(name: str, display_name: str, state: BatchRunState, source_uri: str, output_prefix: str, successful_count: int | None, failed_count: int | None, provider_error: str | None)`.
- Produces `VertexBatchAdapter.submit(run: LyricClassificationBatchRun) -> VertexBatchJob`.
- Produces `VertexBatchAdapter.get(job_name: str) -> VertexBatchJob`.
- Produces `VertexBatchAdapter.find_unique(display_name: str) -> VertexBatchJob | None`.

- [x] **Step 1: Write failing ADC, submission, state, and ambiguity tests**

```python
def test_submit_uses_vertex_adc_exact_model_and_private_uris(fake_genai, run) -> None:
    job = VertexBatchAdapter(PROJECT, "global", fake_genai.client).submit(run)
    assert fake_genai.client_kwargs == {"vertexai": True, "project": PROJECT,
                                        "location": "global", "http_options": ANY}
    assert fake_genai.create_kwargs["model"] == "gemini-3.8-flash"
    assert fake_genai.create_kwargs["src"] == run.source_uri
    assert fake_genai.create_kwargs["config"].dest == run.output_uri_prefix
    assert job.name.startswith("projects/")

def test_lost_create_response_recovers_unique_existing_job(fake_genai, run) -> None:
    fake_genai.create_raises_after_creation = True
    job = VertexBatchAdapter(PROJECT, "global", fake_genai.client).submit(run)
    assert job.display_name == f"lyrics-batch-{run.id}"
    assert fake_genai.create_calls == 1
```

Also assert static API-key environment variables fail preflight, multiple jobs with the
same display name are fatal, read-only `get` never submits, and failed/cancelled/expired
states are terminal without resubmission.

- [x] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/unit/lyrics/test_batch_vertex.py -v`  
Expected: FAIL because the Vertex adapter does not exist.

- [x] **Step 3: Implement the finite Vertex adapter**

Use `genai.Client(vertexai=True, project=..., location=..., http_options=v1)` and
`client.batches.create/get/list`. Do not retry create blindly. On an ambiguous transport
exception, list and match the exact opaque display name once; zero or multiple matches are
safe fatal outcomes. Sanitize provider errors to HTTP code/type/message without payloads.

- [x] **Step 4: Verify tests, lint, and typing; stop for human review**

Run: `uv run pytest tests/unit/lyrics/test_batch_vertex.py -v`  
Run: `uv run ruff check src/chart_observatory/lyrics/batch_vertex.py tests/unit/lyrics/test_batch_vertex.py`  
Run: `uv run mypy src/chart_observatory/lyrics/batch_vertex.py`  
Expected: all PASS. Do not call Vertex live. Do not commit.

### Task 7: Streaming importer, error snapshots, canary contract, and finalization

**Files:**
- Create: `src/chart_observatory/lyrics/batch_importer.py`
- Create: `tests/unit/lyrics/test_batch_importer.py`
- Modify: `src/chart_observatory/lyrics/repository.py`
- Modify: `tests/unit/lyrics/test_classification_repository.py`

**Interfaces:**
- Produces `BatchImportSummary(processed: int, classified: int, ambiguous: int, blocked: int, language_unsupported: int, errors: int, duplicates: int, input_tokens: int, output_tokens: int, thought_tokens: int, total_tokens: int, known_cost_usd: Decimal | None)`.
- Produces `BatchImporter.import_available(run_id: UUID, lines: Iterable[bytes]) -> BatchImportSummary`.
- Produces `BatchImporter.finalize_missing(run_id: UUID) -> BatchImportSummary`.
- Produces `BatchImporter.assert_canary_contract(run_id: UUID) -> None`.
- Produces `BatchRepository.error_retry_candidates(prior_run_id: UUID) -> list[BatchRetryCandidate]` for the orchestrator; the importer itself never submits or prepares work.

- [x] **Step 1: Write failing successful/error/continuation tests**

```python
def test_import_validates_pydantic_and_appends_batch_snapshot(importer, valid_line) -> None:
    summary = importer.import_available(RUN_ID, [valid_line])
    row = snapshot_for(KEY)
    assert LyricsClassification.model_validate(row.result_json)
    assert row.batch_run_id == RUN_ID
    assert row.batch_item_key == KEY
    assert row.provider_model_version == "gemini-3.8-flash@001"
    assert summary.classified == 1

def test_item_error_is_persisted_and_next_line_continues(importer) -> None:
    summary = importer.import_available(RUN_ID, [provider_error_line(KEY1), valid_line(KEY2)])
    assert snapshot_for(KEY1).classification_status == "error"
    assert snapshot_for(KEY1).result_json is None
    assert snapshot_for(KEY2).classification_status == "classified"
    assert summary.errors == 1

def test_fingerprint_mismatch_persists_error_then_stops(importer) -> None:
    with pytest.raises(BatchIntegrityError):
        importer.import_available(RUN_ID, [mismatched_line(KEY1), valid_line(KEY2)])
    assert snapshot_for(KEY1).error == "batch_request_fingerprint_mismatch"
    assert snapshot_for(KEY2) is None
```

Add tests for key round-trip failure, unknown/duplicate keys, already imported idempotency,
safety block, malformed candidate JSON, Pydantic rejection, missing usage, model-version
capture, missing-output finalization only for terminal jobs, and retry-errors selecting only
error snapshots while linking each new result through `forced_from_snapshot_id`.

- [x] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/unit/lyrics/test_batch_importer.py tests/unit/lyrics/test_classification_repository.py -v`  
Expected: FAIL because importer interfaces do not exist.

- [x] **Step 3: Implement streaming row reconciliation and snapshot append**

Resolve the top-level key first, compare the canonical echoed-request SHA-256, inspect
provider `status`, finish reason, safety data, model version, candidate text, and
`usageMetadata`, then validate with `LyricsClassification.model_validate_json`. Commit in
bounded batches of at most 100 rows; rollback only the current bounded transaction.

- [x] **Step 4: Implement canary and terminal finalization gates**

Canary succeeds only for exactly one known returned key, exact request fingerprint, valid
schema result, and matching model. `finalize_missing` requires a terminal provider state and
appends `batch_missing_output` for each unresolved item. It never resubmits a job.

- [x] **Step 5: Implement explicit error-only retry preparation**

Select prior item snapshots with `classification_status="error"`; create new random keys
and batch items with the prior snapshot ID retained for the next append. Reject success,
ambiguous, instrumental, insufficient-text, blocked, and unsupported-language rows.

- [x] **Step 6: Verify importer and repository tests; stop for human review**

Run: `uv run pytest tests/unit/lyrics/test_batch_importer.py tests/unit/lyrics/test_classification_repository.py -v`  
Run: `uv run ruff check src/chart_observatory/lyrics/batch_importer.py tests/unit/lyrics/test_batch_importer.py`  
Run: `uv run mypy src/chart_observatory/lyrics/batch_importer.py`  
Expected: all PASS. Do not commit.

### Task 8: Scientific pilot report and main-run quality gate

**Files:**
- Create: `src/chart_observatory/lyrics/batch_quality.py`
- Create: `tests/unit/lyrics/test_batch_quality.py`

**Interfaces:**
- Produces `HumanPilotReview` and `PilotQualityReport` models with
  status/confidence/intensity distributions, validation rate, token/cost strata, and
  optional agreement metrics.
- Produces `build_pilot_quality_report(session: Session, run_ids: Sequence[UUID], reviews: Iterable[HumanPilotReview] = ()) -> PilotQualityReport`.
- Produces `weighted_cohens_kappa(left: Sequence[int], right: Sequence[int]) -> float | None`.
- Produces `write_blinded_review_manifest(report: PilotQualityReport, path: Path) -> Path` containing opaque keys and locally assigned strata only, never lyrics or track metadata.

- [x] **Step 1: Write failing distribution, privacy, and agreement tests**

```python
def test_pilot_report_contains_no_lyric_or_track_metadata(pilot_session) -> None:
    report = build_pilot_quality_report(pilot_session, PILOT_RUN_IDS)
    encoded = report.model_dump_json()
    assert "lyric text" not in encoded
    assert "artist" not in encoded.casefold()
    assert report.total_items == 100
    assert report.validation_error_rate == Decimal("0.01")

def test_weighted_kappa_is_one_for_identical_ordinal_codes() -> None:
    assert weighted_cohens_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == 1.0
```

Tests must cover absent human reviews, one-rater-only input, constant vectors, language/text
length strata, confidence outliers, and model-versus-human-consensus metrics without
changing snapshots.

- [x] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/unit/lyrics/test_batch_quality.py -v`  
Expected: FAIL because quality-report interfaces do not exist.

- [x] **Step 3: Implement deterministic aggregate-only reporting**

Read only item/snapshot data and precomputed local strata. Implement quadratic weighted
kappa without adding a new statistics dependency. Reports and blinded manifests use opaque
keys; reviewers access lyrics through the authorized local database/UI, not exported files.

- [x] **Step 4: Verify quality tests, lint, and typing; stop for human review**

Run: `uv run pytest tests/unit/lyrics/test_batch_quality.py -v`  
Run: `uv run ruff check src/chart_observatory/lyrics/batch_quality.py tests/unit/lyrics/test_batch_quality.py`  
Run: `uv run mypy src/chart_observatory/lyrics/batch_quality.py`  
Expected: all PASS. Do not commit.

### Task 9: Deep orchestration module and pilot-to-main gate

**Files:**
- Create: `src/chart_observatory/lyrics/batch_service.py`
- Create: `tests/unit/lyrics/test_batch_service.py`

**Interfaces:**
- Produces `BatchClassificationService.preflight() -> BatchPreflightReport`.
- Produces `BatchPreflightReport` and `BatchCleanupSummary` result models.
- Produces `prepare_canary(max_cost_usd: Decimal) -> list[BatchPreparation]`.
- Produces `prepare_pilot(max_cost_usd: Decimal, total_size: int = 100) -> list[BatchPreparation]`.
- Produces `accept_pilot(run_id: UUID, reviewer: str) -> PilotQualityReport`, which records
  a durable acceptance timestamp/reviewer only after the quality report passes.
- Produces `prepare_main(max_cost_usd: Decimal) -> list[BatchPreparation]`, which reads the
  persisted canary/pilot acceptance instead of trusting a boolean flag.
- Produces `submit(run_id: UUID, max_cost_usd: Decimal) -> VertexBatchJob`.
- Produces `status(run_id: UUID) -> VertexBatchJob`.
- Produces `import_results(run_id: UUID) -> BatchImportSummary`.
- Produces `finalize(run_id: UUID) -> BatchImportSummary`.
- Produces `cleanup(run_id: UUID) -> BatchCleanupSummary`.
- Produces `prepare_retry_errors(prior_run_id: UUID, max_cost_usd: Decimal) -> list[BatchPreparation]`.

- [x] **Step 1: Write failing end-to-end orchestration tests with fakes**

```python
def test_main_is_blocked_until_canary_and_100_item_pilot_are_accepted(service) -> None:
    with pytest.raises(PilotNotAccepted):
        service.prepare_main(Decimal("100"))
    service.accept_pilot(PILOT_RUN_ID, reviewer="human-reviewer")
    assert service.prepare_main(Decimal("100"))

def test_terminal_job_failure_imports_available_output_without_resubmit(service) -> None:
    service.vertex.job.state = BatchRunState.FAILED
    summary = service.import_results(RUN_ID)
    assert summary.processed == 9
    assert service.vertex.submit_calls == 0
```

Also test preflight rejects wrong model/location/thinking, static keys, absent ADC, zero rates,
insecure bucket, unapplied migration, online lock contention, source object generation/hash
changes, exceeded cost cap, cleanup before reconciliation, and retry-errors without explicit
run ID.

- [x] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/unit/lyrics/test_batch_service.py -v`  
Expected: FAIL because the orchestration module does not exist.

- [x] **Step 3: Implement the small orchestration interface**

Compose adapters through constructor injection. Keep all provider/storage/database details
behind the methods above. `prepare_*` performs lock, reservation, export, validation, cost
gate, upload, and ledger transition; `submit` revalidates immutable source metadata;
`import_results` streams outputs; `accept_pilot` records acceptance only after one successful
canary plus exactly 100 terminal pilot snapshots and a valid quality report; `cleanup`
verifies terminal/reconciled counts and the exact object set.

- [x] **Step 4: Verify service tests, lint, and typing; stop for human review**

Run: `uv run pytest tests/unit/lyrics/test_batch_service.py -v`  
Run: `uv run ruff check src/chart_observatory/lyrics/batch_service.py tests/unit/lyrics/test_batch_service.py`  
Run: `uv run mypy src/chart_observatory/lyrics/batch_service.py`  
Expected: all PASS. Do not commit.

### Task 10: CLI group, compact logs, and operator documentation

**Files:**
- Modify: `src/chart_observatory/cli.py`
- Create: `tests/unit/lyrics/test_batch_cli.py`
- Modify: `README.md`
- Create: `docs/operations/gemini-batch-lyrics.md`

**Interfaces:**
- Adds `corpus classify-lyrics-batch preflight`.
- Adds `prepare-canary`, `prepare-pilot`, `prepare-main`, `submit`, `status`, `import-results`, `quality-report`, `accept-pilot`, `finalize`, `cleanup`, and `retry-errors` subcommands.
- Every mutating command requires explicit run/bucket/cost arguments where applicable and emits one compact JSON object plus a safe NDJSON event.

- [x] **Step 1: Write failing CLI routing, privacy, and guard tests**

```python
def test_prepare_main_requires_positive_cost_cap_and_pilot_acceptance(monkeypatch) -> None:
    result = runner.invoke(app, ["corpus", "classify-lyrics-batch", "prepare-main",
                                 "--max-cost-usd", "0"])
    assert result.exit_code == 2
    assert "positive" in result.stderr

def test_import_prints_counts_without_payloads(monkeypatch) -> None:
    result = runner.invoke(app, ["corpus", "classify-lyrics-batch", "import-results",
                                 "--run-id", str(RUN_ID)])
    payload = json.loads(result.stdout)
    assert payload["classified"] == 98
    assert "lyrics" not in result.stdout.casefold()
```

Cover all command-to-service argument mappings, UUID/Decimal validation, no `--force`
option, wrong model/thinking preflight, status read-only behavior, durable `accept-pilot`
reviewer/timestamp forwarding, and fatal-safe logging.

- [x] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/unit/lyrics/test_batch_cli.py -v`  
Expected: FAIL because the command group does not exist.

- [x] **Step 3: Implement the Typer group and event writer**

Keep CLI functions thin: load Settings/application, construct adapters/service, invoke one
method, and print `model_dump(mode="json")`. Reuse one safe event writer that rejects
fields named `lyrics`, `prompt`, `request`, `response`, `credential`, or `access_token`.

- [x] **Step 4: Document provisioning and the human-gated runbook**

Document PowerShell commands to stop the online runner, confirm ADC, apply migrations,
provision/inspect the private bucket with public-access prevention/uniform access/no soft
delete/seven-day lifecycle, discover the Vertex service agent, run preflight, canary, pilot,
human quality review, durable pilot acceptance, main submission, status checks, import,
finalization, cleanup, and
later error retry. Never include a static key or raw lyric in examples.

- [x] **Step 5: Verify CLI tests and help output; stop for human review**

Run: `uv run pytest tests/unit/lyrics/test_batch_cli.py -v`  
Run: `uv run chart-observatory corpus classify-lyrics-batch --help`  
Expected: all commands appear, `--force` does not appear, and tests PASS. Do not commit.

### Task 11: Live canary harness and complete verification

**Files:**
- Create: `tests/live/test_vertex_lyrics_batch_canary.py`
- Modify: `README.md`
- Modify only as needed for defects found by verification: files from Tasks 1-10

**Interfaces:**
- Produces an explicitly gated live test that handles exactly one authorized remaining lyric and never launches pilot/main work.
- Produces the final verification record and operational handoff; it does not run the production corpus.

- [x] **Step 1: Write the collection-safe live test**

```python
@pytest.mark.live
def test_vertex_batch_canary_round_trips_opaque_key() -> None:
    if os.getenv("RUN_VERTEX_BATCH_CANARY") != "1":
        pytest.skip("explicit live authorization required")
    result = run_one_item_canary_from_environment()
    assert result.request_count == 1
    assert result.returned_key == result.opaque_key
    assert result.snapshot_status in {"classified", "ambiguous", "blocked",
                                      "language_unsupported"}
```

Collection must not initialize ADC, Cloud Storage, Vertex, or PostgreSQL. Execution requires
an explicit environment flag, exact test bucket, database URL, project, location, model,
LOW thinking, and positive cost cap.

- [x] **Step 2: Run the complete non-live verification suite**

Run: `uv run pytest -m "not live"`  
Run: `uv run ruff check src tests migrations`  
Run: `uv run mypy src/chart_observatory`  
Expected: all PASS; only already-known third-party deprecation warnings are acceptable.

- [x] **Step 3: Exercise migrations on disposable PostgreSQL**

Run upgrade from 0014 to head, inspect tables/indexes/FKs, run downgrade to 0014, then
upgrade again. Verify the immutable snapshot trigger still blocks updates/deletes and the
active batch signature index blocks concurrent reservations.

- [x] **Step 4: Run the live canary only after separate human authorization**

Do not infer authorization from plan approval. When authorized, use one remaining lyric,
one private run prefix, and the configured cost cap. Confirm snapshot persistence and exact
prefix cleanup. Stop immediately on auth, IAM, schema, key, bucket, quota, database, memory,
or cost-estimate error; do not resubmit automatically.

Verified on 2026-09-26 with run `d23d0596-e5e2-41f0-9375-a5f7d6e19b64`: one
opaque-key response imported as `classified`, provider model version persisted, 3,185 total
tokens recorded, known cost US$0.001884375, and the exact two-object run prefix cleaned.

- [x] **Step 5: Update Graphify and prepare the final handoff**

Run: `graphify update .`  
Report changed files, test/migration results, canary outcome if separately authorized,
remaining classified/error counts, and exact operator commands. Do not commit, change
branch, launch the pilot, or launch the main production job.

## Human execution checkpoints

Implementation completion does not authorize production execution. The human must make
separate decisions for:

1. applying migration 0015 to the imported PostgreSQL database;
2. provisioning or changing bucket IAM/lifecycle/security;
3. running the one-item live canary;
4. accepting the 100-item scientific pilot; and
5. submitting the main remaining-corpus job.

At every checkpoint, preserve the current branch and let the human decide whether and when
to commit the reviewed changes.
