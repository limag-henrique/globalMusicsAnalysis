# Gemini batch lyric classification runbook

This runbook operates the human-gated Vertex AI batch path. It never uses a static API
key, never exports track metadata, and never advances automatically from canary to pilot or
from pilot to the main corpus. The application enforces a cumulative ceiling of US$600
across known spend and conservative reservations.

## 1. Stop the online classifier and configure ADC

Stop `classify-lyrics-run` only at a completed five-song boundary. Start the repository's
PostgreSQL service with `docker compose up -d postgres`; the local `.env` points to that
database on `127.0.0.1:5432`. To use a different imported database, set its URL explicitly
in the current PowerShell session:

```powershell
$env:CHART_OBSERVATORY_DATABASE_URL =
  'postgresql+psycopg://postgres@127.0.0.1:55432/chart_observatory'

Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:GOOGLE_API_KEY -ErrorAction SilentlyContinue
gcloud auth application-default login
gcloud auth application-default print-access-token | Out-Null
```

Configure these values in `.env`; obtain the current batch rates from the official Vertex AI
rate card rather than copying historical prices:

```dotenv
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
GEMINI_MODEL=gemini-3.8-flash
GEMINI_THINKING_LEVEL=LOW
GEMINI_BATCH_BUCKET=your-private-lyrics-batch-bucket
GEMINI_BATCH_INPUT_USD_PER_MILLION_TOKENS=replace-with-current-batch-input-rate
GEMINI_BATCH_OUTPUT_USD_PER_MILLION_TOKENS=replace-with-current-batch-output-rate
```

Each request caps generated output at 1,024 tokens. For 159,113 lyrics, maximum output
reserves US$305.50 at the configured introductory batch rate. After the pilot, conservative
input tokens use the worst observed token/byte ratio plus 20% headroom; the reservation is
checked before upload. The pilot confirmed the output cap was sufficient for valid responses.
Truncated or invalid responses are recorded as per-song errors for explicit review and
revalidation.

## 2. Import the API-downloaded lyric corpus

The legacy `gemini_annotations.jsonl` artifact contains API retrieval outcomes. Import only
records with `lyrics_status=FOUND` and non-empty `original_lyrics`; the importer streams the
file, ignores its `song_id` field, and derives stable local track identities from normalized
artist/title text. Artist/title remain local and are never sent to Gemini. Exact repeated
documents are deduplicated by local track, API source, and lyric hash. This produces an
independent lyric-analysis corpus and does not require a Spotify catalog or chart crosswalk.
The user-authorized `RESEARCH_AUTHORIZED` rights status is explicit at import.

```powershell
uv run chart-observatory corpus ingest-api-lyrics --dry-run
uv run chart-observatory db upgrade
uv run chart-observatory corpus ingest-api-lyrics --rights-status RESEARCH_AUTHORIZED
```

The importer is idempotent and commits bounded chunks, so an interrupted import can be
re-run. Its output contains aggregate counts only, never lyric content. The current source
has one malformed JSONL record; it is counted and skipped rather than guessed or repaired.

## 3. Provision the dedicated private bucket once

Choose a globally unique bucket name. The example uses the `US` multi-region; change it
only after accepting the corresponding data-location and price implications.

```powershell
$project = 'your-project-id'
$bucket = 'your-private-lyrics-batch-bucket'

gcloud storage buckets create "gs://$bucket" `
  --project $project `
  --location US `
  --default-storage-class STANDARD `
  --uniform-bucket-level-access `
  --public-access-prevention

gcloud storage buckets update "gs://$bucket" `
  --no-versioning `
  --clear-soft-delete `
  --clear-retention-period

$lifecyclePath = Join-Path $env:TEMP 'gemini-lyrics-lifecycle.json'
@'
{"rule":[{"action":{"type":"Delete"},"condition":{"age":7}}]}
'@ | Set-Content -LiteralPath $lifecyclePath -Encoding utf8NoBOM
gcloud storage buckets update "gs://$bucket" --lifecycle-file $lifecyclePath
Remove-Item -LiteralPath $lifecyclePath

$projectNumber = gcloud projects describe $project --format='value(projectNumber)'
$vertexAgent = "service-$projectNumber@gcp-sa-aiplatform.iam.gserviceaccount.com"
$operator = gcloud config get-value account
gcloud storage buckets add-iam-policy-binding "gs://$bucket" `
  --member "serviceAccount:$vertexAgent" `
  --role roles/storage.objectAdmin
gcloud storage buckets add-iam-policy-binding "gs://$bucket" `
  --member "user:$operator" `
  --role roles/storage.objectAdmin
```

The application validates these controls but never changes bucket security or IAM itself.

## 4. Preflight

```powershell
uv run chart-observatory corpus classify-lyrics-batch preflight
```

Use `preflight` as the authoritative check for the configured imported database. Running
`uv run alembic current` directly reads `alembic.ini` and can inspect a different local
PostgreSQL instance than the URL loaded from `.env`.

Stop on any model, LOW-thinking, ADC, bucket, database, lock, rate, or cost error. Do not
repeat a mutating command until its run ledger has been inspected.

## 5. One-item contract canary

```powershell
uv run chart-observatory corpus classify-lyrics-batch prepare-canary --max-cost-usd 595
# Copy run_id from the compact JSON output.
$canaryRun = '00000000-0000-0000-0000-000000000000'
uv run chart-observatory corpus classify-lyrics-batch submit --run-id $canaryRun --max-cost-usd 595
uv run chart-observatory corpus classify-lyrics-batch status --run-id $canaryRun
uv run chart-observatory corpus classify-lyrics-batch import-results --run-id $canaryRun
uv run chart-observatory corpus classify-lyrics-batch finalize --run-id $canaryRun
```

Do not submit the pilot unless the canary imports one valid, matching opaque key and model
version.

## 6. Scientific pilot and durable acceptance

The pilot command adds the remaining 99 items so canary plus pilot total 100.

```powershell
uv run chart-observatory corpus classify-lyrics-batch prepare-pilot --max-cost-usd 595
$pilotRun = '00000000-0000-0000-0000-000000000000'
uv run chart-observatory corpus classify-lyrics-batch submit --run-id $pilotRun --max-cost-usd 595
uv run chart-observatory corpus classify-lyrics-batch status --run-id $pilotRun
uv run chart-observatory corpus classify-lyrics-batch import-results --run-id $pilotRun
uv run chart-observatory corpus classify-lyrics-batch finalize --run-id $pilotRun
uv run chart-observatory corpus classify-lyrics-batch quality-report --run-id $pilotRun
uv run chart-observatory corpus classify-lyrics-batch accept-pilot `
  --run-id $pilotRun `
  --reviewer 'your-reviewer-id'
```

Acceptance is persisted only after exactly 100 canary-plus-pilot snapshots and a validation
error rate no greater than 5%. Review confidence outliers, every error, text-length strata,
and ordinal agreement before invoking `accept-pilot`. If the source has no language code, the
report correctly labels that stratum `unknown`; do not infer or invent it.

## 7. Main remaining corpus

`prepare-main` returns a JSON array. If the corpus exceeds the per-file safety limits,
each entry is an independent run with its own opaque ID and input object. Keep every ID;
submit and reconcile each entry separately. All entries reserve against the same cumulative
US$595 operational ceiling. The remaining US$5 is reserved for historical activity not
represented in a fresh batch ledger; reconcile billing exports before changing this margin.
After at least 20 pilot observations, conservative input tokens use the worst observed
pilot input-token/request-byte ratio plus 20% headroom. Output remains capped at 1,024 tokens
per song.

Active or not-yet-reconciled runs keep their full conservative reservation. After a terminal
run is fully reconciled, the ledger uses recorded per-snapshot costs and releases unused
reservation only when every response has a known cost or Vertex confirmed that an item had no
output. Any unpriced response keeps that run's conservative reservation in place.

```powershell
$mainRuns = @(
  uv run chart-observatory corpus classify-lyrics-batch prepare-main --max-cost-usd 595 |
    ConvertFrom-Json
)
$mainRuns | Format-Table run_id, request_count, conservative_cost_usd
foreach ($run in $mainRuns) {
  uv run chart-observatory corpus classify-lyrics-batch submit `
    --run-id $run.run_id `
    --max-cost-usd 595
}
```

Check each run with the read-only `status` command. Its JSON includes completed/total,
percentage, successful and failed counts, and state. Vertex can queue jobs for hours. Once a
run is terminal, import its available output, finalize only missing items, then clean up:

```powershell
foreach ($run in $mainRuns) {
  uv run chart-observatory corpus classify-lyrics-batch status --run-id $run.run_id
  # Continue only after this run reports a terminal state.
  uv run chart-observatory corpus classify-lyrics-batch import-results --run-id $run.run_id
  uv run chart-observatory corpus classify-lyrics-batch finalize --run-id $run.run_id
  uv run chart-observatory corpus classify-lyrics-batch cleanup --run-id $run.run_id
}
```

Cleanup is refused until every reserved item links to an immutable snapshot and the durable
summary exists. The seven-day lifecycle is a safety net, not the normal cleanup path.

## 8. Explicit later revalidation of errors

No error is retried automatically. After reviewing the run summary, prepare only its error
snapshots under a new run and new opaque keys:

```powershell
uv run chart-observatory corpus classify-lyrics-batch retry-errors `
  --prior-run-id $mainRun `
  --max-cost-usd 595
```

For a reviewed technical subset, narrow the retry by safe error code, missing usage
telemetry, and an item limit. Repeated preparations exclude snapshots already referenced
by a provider-attempted retry, while failed preflight/preparation reservations remain
eligible because they were never submitted:

```powershell
uv run chart-observatory corpus classify-lyrics-batch retry-errors `
  --prior-run-id $mainRun `
  --max-cost-usd 595 `
  --error-code batch_malformed_response `
  --missing-usage-only `
  --limit 6000
```

`--missing-usage-only` separates absent provider responses from malformed responses that
still carry usage telemetry. The command checks the full conservative cost reservation
against all known costs and active reservations before uploading the request artifact.
Importing a partially committed result stream recomputes the run's known cost from its
immutable snapshots, so resumption cannot omit costs already imported.

The command returns one or more runs. Submit/import/finalize each returned run with the same
explicit commands. Their spend also uses the remaining portion of the cumulative US$595
operational ceiling; US$5 is held for historical activity.

Operational events are appended to
`data/derived/lyrics/gemini_batch_events.jsonl`. They contain IDs, states, counts, tokens,
costs and safe error codes only—never lyrics, prompts, requests, responses or credentials.
