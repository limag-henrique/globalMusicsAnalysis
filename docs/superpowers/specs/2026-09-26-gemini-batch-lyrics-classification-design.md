# Gemini Batch Lyrics Classification Design

**Status:** Approved  
**Date:** 2026-09-26

## Intent and success criteria

Add an asynchronous, cost-controlled classification path for the remaining authorized
lyrics. The path exports only model-eligible lyric text and optional language to JSONL,
uploads that file to a private Cloud Storage bucket, submits Gemini 3.8 Flash batch jobs,
validates every returned classification with the existing Pydantic taxonomy, and appends
results and item-level errors to `lyric_classification_snapshots`.

Success means that:

- every exported item has one random opaque reconciliation key with no embedded database or
  track identity;
- no title, artist, country, genre, chart, rank, stream count, platform, or research
  hypothesis reaches Gemini;
- a technical canary proves the provider round-trips the opaque key before any large job;
- a 100-item scientific pilot is reviewed before the main corpus job is authorized;
- already handled or actively reserved lyrics cannot be submitted twice;
- valid responses, ambiguous classifications, provider blocks, unsupported languages,
  insufficient text, instrumentals, and errors are represented without inventing zero
  scores;
- an item-level error never causes the importer to stop processing the remaining output;
- a job-level failure never triggers automatic resubmission;
- the database, not Cloud Storage, is the durable system of record; and
- input and output artifacts are deleted explicitly after verified import and by a seven-day
  lifecycle rule as a safety net.

## Non-goals

- Do not replace the existing online `classify-lyrics` or `classify-lyrics-run` paths.
- Do not change the substantive classification taxonomy in this increment.
- Do not use a tuned model, API key, service-account key file, BigQuery input, a VM, or
  Provisioned Throughput.
- Do not automatically retry failed songs or automatically advance from the scientific
  pilot to the main run.
- Do not project automatic classifications into the manual Streamlit annotation store.

## Fixed constraints

- Authentication uses Vertex AI and Application Default Credentials (ADC) only.
- The exact model is `gemini-3.8-flash` and the endpoint location is `global`.
- `GEMINI_THINKING_LEVEL=LOW` is mandatory.
- Gemini 3.8 Flash receives no `temperature`, `top_p`, `top_k`, `candidate_count`,
  `frequency_penalty`, or `presence_penalty`.
- Structured output uses both `application/json` and a response schema derived from the
  existing `LyricsClassification` Pydantic model. The batch JSONL contains a fully inline
  schema with no `$ref` or `$defs` keys because the provider's GCS ingestion layer rejects
  those field names.
- `TAXONOMY_VERSION`, `PROMPT_VERSION`, model ID, requested thinking level, and returned
  provider model version are preserved for reproducibility.
- No branch change or automatic Git commit is part of this work.

The global endpoint maximizes availability and minimizes regional price overhead, but it
does not provide a data-residency guarantee. That tradeoff is accepted for this workflow.

## Existing architecture and selected seam

`LyricDocument` remains the authoritative rights-gated source. An idempotent bootstrap adapter
imports legacy API-download JSONL records with `FOUND` text, ignores provider `song_id`, and
derives deterministic local artist/track identities from normalized artist and title. This
adapter does not require a platform catalog or send those identities to Gemini. The explicit
operator authorization is stored as `RESEARCH_AUTHORIZED`. `LyricsClassification`,
`TAXONOMY_VERSION`, `PROMPT_VERSION`, `GenerationPolicy`, and the current prompt builder
remain the classification contract. `LyricClassificationSnapshot` remains the immutable
scientific record.

Add `lyrics.batch_classification` as the orchestration module at the batch seam. Its public
interface accepts an operation such as prepare, submit, inspect, import, clean up, or
explicitly retry prior errors. Its implementation hides candidate reservation, JSONL
serialization, Cloud Storage integrity checks, Vertex batch calls, output reconciliation,
Pydantic validation, and snapshot persistence.

The batch module has four internal adapters:

1. a PostgreSQL ledger adapter for runs and items;
2. a JSONL request/output adapter;
3. a Cloud Storage adapter authenticated by ADC; and
4. a Gemini batch adapter using the existing `google-genai` dependency.

These are internal seams, not separate public workflows. CLI commands call one batch
orchestrator rather than coordinating these details themselves.

## Considered approaches

### Selected: canary, scientific pilot, then one main job

Submit one single-item contract canary, then the remaining 99 items of a 100-item
scientific pilot, and finally one main job containing all then-remaining lyrics. Every
pilot item is a real corpus item and is persisted, so the pilot spend is not discarded.

The main exporter splits only when either of these safety margins would be exceeded:

- 190,000 requests per file; or
- 900 MiB of UTF-8 JSONL per file.

Generated output is capped at 1,024 tokens per item. After at least 20 canary/pilot usage
observations, conservative input tokens for the remaining corpus use the maximum observed
pilot input-token/request-byte ratio with 20% headroom. Before the pilot is available, the
importer retains the byte-per-token upper bound. This estimate and all prior reservations
must fit the operator ceiling before any GCS upload. A fresh ledger uses an operational cap
of US$595, retaining US$5 for previously recorded activity that may not be present in that
database; the hard application ceiling remains US$600.

The provider limit is 200,000 requests and 1 GB per Cloud Storage input file. Google also
recommends combining small jobs into one large job for throughput. See
[Batch inference with Gemini](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/batch-inference).

### Rejected: many fixed-size shards

Sharding into many 5,000- or 20,000-item jobs reduces the blast radius of a job-level
failure, but increases queueing, reconciliation state, IAM-visible objects, and operator
work. Provider-supported resume and durable item reconciliation already address partial
completion. Sharding remains a limit-driven fallback, not the default.

### Rejected: online workers on a VM

A VM improves host uptime but does not remove online per-request latency, retry, and quota
coordination. Batch inference already supplies managed parallelism, retries, and discounted
pricing, so a VM adds cost without improving this workload's scientific contract.

## Operational persistence

Add mutable operational tables. They coordinate work but do not replace immutable
snapshots.

### `lyric_classification_batch_runs`

The run record contains:

- UUID `id`, creation/update timestamps, and a run kind (`canary`, `pilot`, `main`, or
  `error_retry`);
- state (`prepared`, `uploaded`, `submitted`, `running`, `succeeded`, `failed`,
  `cancelled`, `expired`, `imported`, or `cleaned`);
- requested model ID, returned model version when known, taxonomy version, prompt version,
  and thinking level;
- Cloud project and location, but no credential material;
- source object URI, object generation, file SHA-256, byte count, and request count;
- output URI prefix and Vertex batch job resource name;
- expected and conservative-maximum cost estimates;
- provider completion statistics and local imported/error counts;
- safe job-level error code/message and terminal timestamps.

### `lyric_classification_batch_items`

The item record contains:

- random UUIDv4 `opaque_key` as its primary reconciliation identity;
- `batch_run_id`, line number, lyric document ID, canonical track ID, and lyrics hash;
- the full reproducibility signature: requested model, taxonomy version, and prompt version;
- SHA-256 of the canonical serialized provider request;
- state (`reserved`, `submitted`, `succeeded`, `error`, `missing`, or `imported`);
- nullable linked snapshot ID;
- nullable safe provider status and error code; and
- processed/imported timestamps.

The opaque key is random, never derived from a track/document ID, and never reused. A
partial unique PostgreSQL index prevents the same reproducibility signature from appearing
in more than one active batch item. Application-level checks provide equivalent behavior
in SQLite tests.

### Snapshot extensions

Add nullable fields to `lyric_classification_snapshots`:

- `provider_model_version`;
- `execution_mode`, with existing rows treated as `online` and new batch rows as `batch`;
- `batch_run_id`; and
- `batch_item_key`.

These additions let a scientific result be traced to the exact provider output and batch
run without putting operational payloads in `result_json`. Existing rows remain valid.

## Candidate selection and reservation

Preparation runs under a PostgreSQL advisory lock shared with both online classification
commands. A pre-existing online process must be stopped before deploying the migration;
after deployment, the shared lock prevents simultaneous selection.

Candidate selection:

1. selects only `LyricDocument` rows with an authorized rights status;
2. deduplicates by the current reproducibility signature;
3. excludes signatures with handled snapshots;
4. excludes signatures held by active batch items;
5. applies the existing local instrumental and minimum-text rules; and
6. orders deterministically by creation time and document ID.

Instrumental and insufficient-text outcomes are appended directly as snapshots and never
exported. Remaining candidates and their batch item reservations are committed before the
JSONL file is made externally visible. If local file creation fails, the run is marked
failed and its reservations become inactive; no provider call occurs.

The scientific pilot is selected locally to cover languages and text-length bands without
including those strata in provider input. The main run selects everything remaining after
the pilot has been accepted.

## JSONL request contract

Each line is canonical compact UTF-8 JSON with this logical shape:

```json
{
  "key": "random-opaque-uuid",
  "request": {
    "contents": [
      {
        "role": "user",
        "parts": [{"text": "classification instructions, optional language, and lyrics"}]
      }
    ],
    "generationConfig": {
      "responseMimeType": "application/json",
      "responseSchema": {},
      "thinkingConfig": {"thinkingLevel": "LOW"},
      "maxOutputTokens": 1024
    }
  }
}
```

The actual response schema is generated from `LyricsClassification`; the schema is not
duplicated in the prose prompt. The prompt builder is shared with the online adapter so
both modes use identical instructions and language formatting. The only song-derived
provider content is lyric text and optional language.

Before upload, a streaming validator rejects a file if it finds:

- a duplicate/malformed opaque key;
- a request not represented in the item ledger;
- a request hash mismatch;
- a missing required generation setting;
- a forbidden metadata field outside the lyric text;
- a blank lyric; or
- an exceeded row/file limit.

The single-item canary proves that Vertex accepts and returns the top-level key while the
model sees only `request`. If the key is absent, changed, or model-visible, the run stops
and no pilot/main job may be submitted. The opaque ID is never moved into the prompt as a
fallback.

## Cloud Storage security and lifecycle

Use one dedicated bucket with:

- Standard storage;
- uniform bucket-level access;
- public access prevention set to `enforced`;
- object versioning disabled;
- soft delete disabled;
- no retention policy or signed URLs;
- Google-managed encryption at rest; and
- a lifecycle `Delete` action at age seven days for all batch prefixes.

Uniform bucket-level access and public access prevention reduce accidental exposure. See
[Uniform bucket-level access](https://docs.cloud.google.com/storage/docs/uniform-bucket-level-access)
and [Public access prevention](https://docs.cloud.google.com/storage/docs/public-access-prevention).

Seven days covers the documented maximum queue period of 72 hours plus the typical
24-hour processing window with operational margin. Lifecycle deletion is asynchronous,
so successful import triggers explicit prefix deletion first; lifecycle is only the
safety net. Cloud Storage recommends disabling soft delete for temporary batch artifacts
to avoid retained-object costs. See
[Cloud Storage batch input/output guidance](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/batch-inference/new-job-from-cloud-storage)
and [Object Lifecycle Management](https://docs.cloud.google.com/storage/docs/lifecycle).

Runtime IAM is least-privilege and bucket-scoped:

- the operator ADC principal can create/read/delete objects in the dedicated bucket;
- the Vertex AI service agent can read inputs and create outputs; and
- only an administrator provisioning the bucket can change lifecycle and bucket policy.

The application validates these properties and fails closed; it does not silently weaken
bucket policy or grant project-wide roles.

The local JSONL is created in a restricted temporary directory, uploaded with a
does-not-exist generation precondition, and deleted after upload integrity is confirmed.
The run record preserves URI, object generation, SHA-256, and byte count, but never lyric
text.

## Cost controls

Batch-specific immutable input and output/reasoning rates are configured separately from
online rates. Thought tokens use the provider's output/reasoning rate. Missing rates or a
zero/unavailable estimate block submission.

Preparation reports two values:

- an expected estimate derived from actual token counts for the 100-item stratified pilot
  and corpus byte/character distribution; and
- a conservative maximum based on full UTF-8 request bytes and the configured output-token
  ceiling.

The operator must supply a positive `--max-cost-usd`; submission fails closed if the
conservative estimate exceeds it. Cost is recomputed after import from returned
`usageMetadata`. Unknown usage remains null rather than being guessed.

Gemini batch processing is priced below online inference, and implicit caching can reduce
repeated prompt/schema input cost; cache and batch discounts do not stack. The rate card
remains configuration rather than hard-coded pricing because provider prices change. See
[Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing) and
[Batch inference with Gemini](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/batch-inference).

## Submission and monitoring

The Gemini adapter constructs a Vertex/ADC `google-genai` client with API version `v1` and
submits the exact model `gemini-3.8-flash`, GCS source URI, private output prefix, and a
display name containing only the opaque run ID.

Submission is idempotent locally: a run with a recorded provider job name cannot be
submitted again. Ambiguous transport failure after submission is resolved by listing jobs
for the exact display name before another create call is allowed.

Status inspection performs read-only provider calls and records state/completion counters.
Polling status is allowed, but a failed, cancelled, or expired job is never automatically
resubmitted. The provider's internal batch retries are accepted as part of the managed
service; application-level generation retries are not added.

The main job can be submitted only after:

1. the contract canary succeeds;
2. all 100 pilot items reach a persisted terminal snapshot;
3. output validation reports no contract violations;
4. a pilot quality report is generated; and
5. the human operator explicitly accepts the pilot.

## Import and validation

Output import is streaming and transactionally commits one item at a time or in small
bounded database batches. It never holds all JSONL responses or lyrics in memory.

For every output row, the importer:

1. resolves exactly one active item by opaque key;
2. rejects duplicate or unknown keys;
3. canonicalizes and hashes the echoed request, then compares it with `request_sha256`;
4. distinguishes provider `status` errors from response payloads;
5. checks finish reason and safety/block information;
6. extracts candidate text and validates JSON with
   `LyricsClassification.model_validate_json`;
7. checks status/payload invariants and usage counts;
8. records the returned provider model version;
9. appends one immutable snapshot; and
10. links the item to that snapshot.

Import idempotency is keyed by `batch_item_key`: an already linked item is reported and
skipped without creating another snapshot. A duplicate output key, request fingerprint
mismatch, or output for another run is a run-integrity failure. The importer stops before
persisting that offending row but retains prior committed rows and reports the exact safe
reason. Lyric text is never included in logs or error messages.

## Error semantics and explicit revalidation

Ordinary item-level provider and validation errors do not stop other rows. They append an
`error` snapshot with a stable, safe code such as:

- `batch_provider_error`;
- `batch_safety_block`;
- `batch_malformed_response`;
- `batch_schema_validation_error`;
- `batch_missing_output`.

Request-fingerprint mismatches, duplicate keys, and unknown keys are run-integrity errors,
not ordinary model failures. A mismatch for a known key appends a
`batch_request_fingerprint_mismatch` error snapshot and then halts further import; an
unknown key cannot be safely associated with a snapshot, so it is recorded only on the
batch run and halts import. Previously committed rows remain durable in both cases.

Provider-classified terminal outcomes use their normal statuses (`classified`,
`ambiguous`, `blocked`, or `language_unsupported`). Locally detected instrumentals and
insufficient text retain their existing statuses and are not counted as errors.

When a job reaches a terminal state, the importer first consumes every available completed
row. Items with no output are marked `missing` and receive `batch_missing_output` snapshots
only during explicit finalization. This keeps incomplete work visible and prevents silent
loss.

`retry-errors` is a separate, explicit operation that selects only item errors from a named
prior run. It creates new opaque keys and new batch items, then links new snapshots to the
previous error snapshots through `forced_from_snapshot_id`. It does not expose or use the
general `--force` option, does not retry successful rows, and never runs automatically.

## Scientific and social quality controls

The existing prompt remains evidence-focused: presence is distinct from stance, narrator
voice is distinct from endorsement, absence of consent language is not coercion, and
demographic identity or real-world behavior is not inferred from lyrics. Confidence
measures coding certainty rather than moral agreement or probability of harm.

Gemini 3.8 Flash supports structured output and `LOW`, `MEDIUM`, and `HIGH` thinking.
`LOW` is retained to control cost while strict schema and independent quality measurement
provide consistency. See
[Gemini 3.8 Flash guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-3-8-flash)
and [Structured output](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output).

The 100-item pilot produces a local report containing no lyric text and no demographic
inferences. It includes:

- status distribution;
- confidence distribution and outliers;
- category intensity distributions;
- Pydantic/error rate;
- token and cost distributions by local language/text-length stratum; and
- a blinded human-review worksheet keyed only by opaque item ID.

For manually double-coded pilot items, report weighted Cohen's kappa for ordinal intensity
fields and categorical agreement for enum fields. This measurement does not alter model
outputs or automatically tune thresholds. Any prompt/taxonomy change increments its
version and requires a new pilot before the main job.

## Operator interface

Expose a nested CLI group under `corpus classify-lyrics-batch` with commands for:

- `preflight`: validate ADC, model/location/thinking level, database migration, bucket
  controls, service-agent access, rates, and absence of static Gemini API keys;
- `prepare-canary`: reserve and upload exactly one remaining item;
- `prepare-pilot`: reserve the remaining items needed to reach a 100-item pilot;
- `prepare-main`: reserve all remaining items and split only at safety limits;
- `submit`: submit one prepared run after revalidating source generation/hash and cost cap;
- `status`: fetch one read-only job status snapshot;
- `import-results`: import all currently available outputs and print item/status/token/cost
  totals;
- `finalize`: create missing-output errors only for a terminal job;
- `cleanup`: delete only the exact recorded source/output prefix after reconciliation; and
- `retry-errors`: prepare a new run containing only errors from one named prior run.

Commands emit compact JSON and append an NDJSON operational log containing IDs, counts,
states, tokens, costs, and safe error codes only. No command prints lyrics, prompt bodies,
credentials, access tokens, or output payloads.

The CLI does not provide an unattended command that moves from pilot acceptance to the
main run. That transition is a deliberate human checkpoint.

## Cleanup rules

Cleanup is allowed only when:

- source bucket/object generation matches the run record;
- the provider job is terminal;
- every batch item is linked to a snapshot or explicitly finalized as missing/error;
- imported + error counts equal the reserved item count; and
- a local run summary has been durably written.

Deletion targets exact run prefixes, never a bucket root or wildcard. Cleanup records the
result in the run ledger. Lifecycle deletion remains active if explicit cleanup is missed.

## Verification strategy

Development follows red-green-refactor. Unit and integration tests cover:

1. authorized/unclassified selection and active-reservation exclusion;
2. local instrumental/insufficient-text persistence without JSONL export;
3. random opaque IDs and absence of database IDs/forbidden metadata in provider requests;
4. canonical JSONL serialization and 190,000-row/900-MiB splitting;
5. shared prompt/schema parity between online and batch modes;
6. Gemini 3.8 Flash `LOW` configuration without unsupported sampling parameters;
7. bucket security, lifecycle, soft-delete, IAM, and upload precondition failures;
8. idempotent submit recovery after an ambiguous transport failure;
9. output key and request-fingerprint reconciliation;
10. Pydantic success, ambiguous, blocked, unsupported-language, malformed, and provider
    error outcomes;
11. duplicate, unknown, missing, and already-imported output keys;
12. snapshot traceability fields and immutable history;
13. item-level continuation after errors and job-level no-auto-resubmit behavior;
14. explicit error-only retry linking to the previous snapshot;
15. nonzero expected/conservative estimates, cost-cap refusal, and actual usage totals;
16. exact-prefix cleanup gating; and
17. a live one-item canary guarded by an explicit live-test marker and ADC prerequisites.

Repository-wide verification runs the non-live pytest suite, Ruff, mypy, migration tests
against PostgreSQL, and Graphify update. No live provider test runs as part of the default
suite.

## Rollout sequence

1. Stop the currently running online classifier at a completed batch boundary.
2. Deploy code and database migration; do not start the online runner again concurrently.
3. Provision or validate the dedicated private bucket and least-privilege IAM.
4. Run local preflight and cost estimate.
5. Prepare, submit, and import the one-item contract canary.
6. Prepare, submit, import, and review the remainder of the 100-item pilot.
7. Approve or revise prompt/taxonomy based on the pilot; a revision requires a new version
   and pilot.
8. Prepare and submit the main remaining-corpus job.
9. Monitor with read-only status checks and import outputs when terminal.
10. Finalize missing rows, write the total summary, and explicitly clean the run prefix.
11. Use `retry-errors` later only when the human operator authorizes revalidation.

## Acceptance criteria

The feature is accepted when a test bucket and PostgreSQL database demonstrate that:

- a canary and pilot complete using Vertex AI ADC without static keys;
- provider input contains only control instructions, schema, lyric, optional language, and
  a non-model-visible opaque key;
- every pilot item has exactly one traceable immutable snapshot;
- individual failures do not stop import and are queryable for later revalidation;
- no failed/cancelled/expired job is resubmitted automatically;
- the main exporter reports a positive expected estimate and conservative cost cap;
- cleanup cannot remove unreconciled data and only targets the recorded prefix; and
- bucket artifacts disappear after explicit cleanup or the seven-day lifecycle safety net.
