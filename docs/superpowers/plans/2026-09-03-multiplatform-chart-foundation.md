# Multiplatform Historical Chart Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, rights-gated foundation that stores and analyzes recording-level chart observations by origin platform, source provider, country, and native period without depending on Spotify or analyzing lyrics.

**Architecture:** A Python modular monolith exposes FastAPI, CLI, and Streamlit entry points over application services and provider-neutral domain ports. PostgreSQL stores normalized, versioned records while an append-only filesystem stores source artifacts; every network, storage, analysis, and export operation is authorized by a source-specific rights profile.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic Settings, SQLAlchemy 2, Alembic, PostgreSQL 16, Polars, PyArrow, HTTPX, Typer, Streamlit, SciPy, structlog, tenacity, pytest, pytest-postgresql/testcontainers, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-03-multiplatform-chart-foundation-design.md`

## Global Constraints

- The unit is a recording, not a composition; versions remain distinct unless evidence proves the same recording.
- `origin_platform` and `source_provider` are separate dimensions.
- `chart_entries.canonical_track_id` is nullable; unresolved observations are preserved.
- A YouTube video remains an independently ranked platform item even after track resolution.
- No fuzzy match can confirm a link without human review.
- Raw artifacts and chart snapshots are immutable; corrections create superseding records.
- Missing values remain null and are never coerced to zero.
- Daily and weekly observations stay in native periods; weekly rows are never expanded into days.
- No unified popularity score and no comparison of streams with views as the same unit.
- Every adapter fails closed unless the required provider-specific rights grants are active.
- No scraping, login automation, private endpoints, purchases, or provider signups.
- Apple, YouTube, Spotify, YouTube Music, and Amazon network execution begins disabled.
- Lyrics, NLP, LLMs, content classification, and human content annotation are outside this plan.
- Unit tests use local fixtures and never call live APIs.
- The agent must never create a Git commit. Each task ends at a human commit checkpoint; only the human may decide and run a commit.

## Scope and execution gates

This master plan is deliberately split:

- **1A:** Tasks 1–16. End with an operational manual-import system plus a disabled, fixture-tested Apple adapter.
- **1B:** Tasks 17–18. Start only after human acceptance of 1A and approval of the YouTube rights route.
- **1C:** Commercial-provider procurement gate. A separate provider-specific plan is required after selection.
- **1D:** Later authorized sources. Each must pass the shared conformance suite and needs its own activation decision.

The implementation session must stop after Task 16 for the 1A review. Approval of this document does not authorize Tasks 17–18, a purchase, an authenticated API call, or activation of any provider.

## Evidence-driven provider and coverage baseline

The detailed comparison is in `research/historical_sources_assessment.md`. It controls the sequence as follows:

| Source | Role in this plan | Current/history status | Activation status |
|---|---|---|---|
| Apple Music Charts | First current-chart adapter contract | Current snapshot; no date parameter | Disabled pending written research rights |
| YouTube Data API `mostPopular` | Second, explicitly video-centric adapter | Current snapshot; not YouTube Music Top Songs | Disabled pending approved retention/derivatives route |
| YouTube Music Charts | Correct music-chart construct | No documented public API/export or guaranteed archive | Interface only |
| Spotify | Later licensed origin platform | No documented Charts API; analysis restrictions | Disabled |
| Amazon Music | Future origin platform | Personalized top tracks; no territorial history | Disabled |
| Luminate | First historical procurement contact | Nine target countries documented; 2021 may contain gaps, stronger from 2022 | Pending contract/sample |
| Soundcharts | Second historical procurement contact | Historical date/ranking endpoints; exact cells require authenticated evidence | Pending contract/sample |
| Chartmetric | Third historical procurement contact | Date-aware chart endpoints; completeness requires authenticated evidence | Pending contract/sample |
| Manual authorized files | First operational ingestion path | History depends on supplied dataset | Enabled only per approved file/source rights profile |

Expected 2021-present feasibility before authenticated samples:

| Source | BR | US | GB | FR | DE | ES | PT | IT | SE | Balanced 2021-present corpus |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Apple Music Charts | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | No / rights-blocked |
| YouTube `mostPopular` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | No native history |
| YouTube Music Charts | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | CURRENT | Unknown |
| Spotify | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | Unknown / rights-blocked |
| Amazon Music | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | No compatible native history |
| Soundcharts | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | Pending contract and sample |
| Chartmetric | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | Pending contract and sample |
| Luminate | DOC* | DOC* | DOC* | DOC* | DOC* | DOC* | DOC* | DOC* | DOC* | Pending 2021 gap audit; likely stronger from 2022 |

`CURRENT` means a current-state interface is documented, not that collection is licensed. `DOC*` means national history is documented but known gaps/breaks require validation. `PENDING` and `UNKNOWN` are preserved as uncertainty, never converted to coverage.

## Planned file map

```text
pyproject.toml                         dependencies, scripts, pytest configuration
compose.yaml                          PostgreSQL development service
.env.example                          non-secret settings template
config/countries.yaml                 nine initial countries
config/research.yaml                  configurable date window and alignment defaults
config/schemas/manual_generic.yaml    manual import mapping profile
src/chart_observatory/config.py       typed settings
src/chart_observatory/domain/         enums, value objects, entities, errors
src/chart_observatory/db/             engine, sessions, ORM mappings, repositories
src/chart_observatory/rights/         rights policy and fail-closed gate
src/chart_observatory/artifacts/      append-only artifact store and manifests
src/chart_observatory/charts/         ports, ingestion, coverage, chart repositories
src/chart_observatory/tracks/         canonical identity and resolution
src/chart_observatory/adapters/       provider and file adapters
src/chart_observatory/metrics/        native-period and overlap metrics
src/chart_observatory/exports/        datasets and manifests
src/chart_observatory/api/            FastAPI routes/schemas
src/chart_observatory/cli.py          Typer commands
src/chart_observatory/ui/             Streamlit pages
migrations/                           Alembic revisions
tests/unit/                            pure deterministic tests
tests/integration/                     PostgreSQL/application tests
tests/contract/                        fixture-based adapter contract tests
tests/fixtures/                        synthetic provider payloads and CSV files
research/                              methodology and source assessments
```

---

## Milestone 1A

### Task 1: Bootstrap the project and configuration

**Files:**
- Create: `pyproject.toml`, `compose.yaml`, `.env.example`, `.gitignore`
- Create: `src/chart_observatory/__init__.py`, `src/chart_observatory/config.py`
- Create: `config/countries.yaml`, `config/research.yaml`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Produces: `Settings`, `CountryConfig`, and `ResearchWindow` used by all later tasks.

- [ ] **Step 1: Write configuration tests**

```python
def test_research_window_is_configurable(settings):
    assert settings.research.start_date.isoformat() == "2021-01-01"
    assert settings.research.end_date is None


def test_initial_country_codes_are_exact(settings):
    assert {c.code for c in settings.countries} == {
        "BR", "US", "GB", "FR", "DE", "ES", "PT", "IT", "SE"
    }
```

- [ ] **Step 2: Run `pytest tests/unit/test_config.py -q` and verify failure because `Settings` does not exist.**
- [ ] **Step 3: Add the package metadata, pinned dependency ranges, executable entry points that import the CLI/API/UI modules, PostgreSQL Compose service, ignored secret/raw paths, and typed YAML-backed settings. Set `research_start_date: 2021-01-01` and `research_end_date: null`; do not encode those dates in Python.**
- [ ] **Step 4: Run the test and `python -m compileall src`; both must pass.**
- [ ] **Step 5: Human checkpoint. Review generated dependency lockfile and decide whether to commit Task 1. The agent does not commit.**

### Task 2: Define provider-neutral domain values

**Files:**
- Create: `src/chart_observatory/domain/enums.py`
- Create: `src/chart_observatory/domain/values.py`
- Create: `src/chart_observatory/domain/errors.py`
- Test: `tests/unit/domain/test_values.py`

**Interfaces:**
- Produces: `PlatformCode`, `SourceCode`, `ChartFrequency`, `MetricType`, `ItemKind`, `CoverageStatus`, `ResolutionStatus`, `RightsOperation`, `ChartPeriod`, `DateWindow`, `ChartKey`.

- [ ] **Step 1: Test ISO country validation, rank positivity, date-window ordering, and native-period preservation.**

```python
def test_weekly_period_remains_one_period():
    period = ChartPeriod.weekly(date(2026, 8, 28), date(2026, 9, 3))
    assert period.frequency is ChartFrequency.WEEKLY
    assert period.duration_days == 7
    assert len(period.as_native_periods()) == 1


@pytest.mark.parametrize("rank", [0, -1])
def test_rank_must_be_positive(rank):
    with pytest.raises(DomainValidationError):
        Rank(rank)
```

- [ ] **Step 2: Run the tests and verify they fail on missing domain types.**
- [ ] **Step 3: Implement immutable dataclasses/enums. Use `Decimal` for provider metrics and timezone-aware UTC datetimes for retrieval. Do not add lyrics or content-analysis enums.**
- [ ] **Step 4: Run `pytest tests/unit/domain -q`.**
- [ ] **Step 5: Human checkpoint; the human decides whether to commit.**

### Task 3: Create database infrastructure and reference entities

**Files:**
- Create: `src/chart_observatory/db/base.py`, `engine.py`, `session.py`
- Create: `src/chart_observatory/db/models/reference.py`
- Create: `src/chart_observatory/db/repositories/reference.py`
- Create: `migrations/env.py`, `migrations/versions/0001_reference_entities.py`
- Test: `tests/integration/db/test_reference_entities.py`

**Interfaces:**
- Produces repositories for `Platform`, `DataSource`, and `Country`.

- [ ] **Step 1: Write an integration test proving providers and platforms are distinct.**

```python
def test_soundcharts_can_supply_a_spotify_chart(reference_repo):
    spotify = reference_repo.get_platform("SPOTIFY")
    soundcharts = reference_repo.get_source("SOUNDCHARTS")
    assert spotify.id != soundcharts.id
    assert spotify.code == "SPOTIFY"
    assert soundcharts.code == "SOUNDCHARTS"
```

- [ ] **Step 2: Run the test against a temporary PostgreSQL database and verify migration/table failure.**
- [ ] **Step 3: Implement SQLAlchemy 2 declarative mappings with string codes, audit timestamps, uniqueness constraints, and seed data for the approved platforms, providers, and countries. Soundcharts, Chartmetric, and Luminate appear only in `data_sources`.**
- [ ] **Step 4: Apply migrations twice to verify repeatability, then run the integration test.**
- [ ] **Step 5: Human checkpoint; no automatic commit.**

### Task 4: Implement provider-specific rights profiles and fail-closed authorization

**Files:**
- Create: `src/chart_observatory/db/models/rights.py`
- Create: `src/chart_observatory/rights/models.py`, `gate.py`, `repository.py`
- Create: `migrations/versions/0002_rights_profiles.py`
- Test: `tests/unit/rights/test_gate.py`, `tests/integration/rights/test_rights_repository.py`

**Interfaces:**
- Produces: `RightsGate.authorize(source_id, operation, occurred_at) -> AuthorizationDecision` and `RightsGate.require(...) -> None`.
- Consumes: `RightsOperation` from Task 2 and source IDs from Task 3.

- [ ] **Step 1: Write fail-closed tests.**

```python
def test_pending_source_is_denied(gate, apple_source):
    decision = gate.authorize(apple_source.id, RightsOperation.FETCH, NOW)
    assert decision.allowed is False
    assert decision.reason == "NO_ACTIVE_APPROVED_GRANT"


def test_import_requires_all_declared_operations(gate, licensed_source):
    gate.require(licensed_source.id, RightsOperation.IMPORT, NOW)
    with pytest.raises(RightsDenied):
        gate.require(licensed_source.id, RightsOperation.REDISTRIBUTE_ROWS, NOW)
```

- [ ] **Step 2: Run tests and verify the missing-gate failure.**
- [ ] **Step 3: Implement immutable/effective-dated `rights_profiles` and normalized `rights_grants`. Reject absent, expired, denied, or ambiguous grants. Seed all network sources as `PENDING`; create no approved production grant.**
- [ ] **Step 4: Run unit and integration tests, including an expiry-boundary case.**
- [ ] **Step 5: Human checkpoint; no automatic commit.**

### Task 5: Model canonical recordings, artists, platform items, and external-ID claims

**Files:**
- Create: `src/chart_observatory/db/models/tracks.py`
- Create: `src/chart_observatory/tracks/models.py`, `repository.py`, `normalization.py`
- Create: `migrations/versions/0003_track_identity.py`
- Test: `tests/integration/tracks/test_track_identity.py`, `tests/unit/tracks/test_normalization.py`

**Interfaces:**
- Produces: `CanonicalTrack`, `Artist`, `PlatformItem`, `ExternalIdClaim`, `PlatformItemTrackLink` repositories.

- [ ] **Step 1: Test that one recording can have many IDs and one recording can link to several YouTube videos without merging the videos.**

```python
def test_multiple_videos_remain_distinct_for_one_recording(track_repo):
    track = track_repo.create_track(title="Synthetic Song")
    video_a = track_repo.create_platform_item("YOUTUBE_VIDEO", "video-a", "VIDEO")
    video_b = track_repo.create_platform_item("YOUTUBE_VIDEO", "video-b", "VIDEO")
    track_repo.link_item(track.id, video_a.id, evidence="HUMAN_REVIEW")
    track_repo.link_item(track.id, video_b.id, evidence="HUMAN_REVIEW")
    assert video_a.id != video_b.id
    assert track_repo.items_for_track(track.id) == [video_a, video_b]
```

- [ ] **Step 2: Verify failure before the migration exists.**
- [ ] **Step 3: Implement many-to-many artists, recording-level canonical tracks, native platform items, mapping links, and source-attributed external-ID claims. Normalize ISRC format but retain the raw value. Do not impose global uniqueness on ISRC claims; index conflicts for review.**
- [ ] **Step 4: Run identity and migration tests.**
- [ ] **Step 5: Human checkpoint.**

### Task 6: Implement deterministic resolution and the ambiguous-match queue

**Files:**
- Create: `src/chart_observatory/tracks/resolution.py`, `similarity.py`
- Create: `src/chart_observatory/db/models/resolution.py`
- Create: `migrations/versions/0004_resolution_records.py`
- Test: `tests/unit/tracks/test_resolution.py`, `tests/integration/tracks/test_resolution_audit.py`

**Interfaces:**
- Produces: `TrackResolutionService.resolve(item_id) -> ResolutionOutcome` and `record_review(decision) -> ResolutionDecision`.

- [ ] **Step 1: Test resolution priority and the fuzzy hard stop.**

```python
def test_exact_isrc_can_match(resolver, item_with_isrc, canonical_track):
    outcome = resolver.resolve(item_with_isrc.id)
    assert outcome.status is ResolutionStatus.MATCHED_EXACT
    assert outcome.canonical_track_id == canonical_track.id


def test_fuzzy_candidate_never_confirms(resolver, similar_title_item):
    outcome = resolver.resolve(similar_title_item.id)
    assert outcome.status is ResolutionStatus.NEEDS_REVIEW
    assert outcome.canonical_track_id is None
    assert len(outcome.candidates) >= 1
```

- [ ] **Step 2: Run tests and verify missing service failure.**
- [ ] **Step 3: Implement the ordered strategy: ISRC, existing exact namespace/value, documented equivalence, exact composite evidence, then candidate-only fuzzy scoring. Persist rule version, evidence, score, candidates, reviewer decision, and timestamps.**
- [ ] **Step 4: Run all track tests and ensure two conflicting ISRC claims produce `NEEDS_REVIEW`.**
- [ ] **Step 5: Human checkpoint.**

### Task 7: Model chart definitions, immutable snapshots, and entries

**Files:**
- Create: `src/chart_observatory/db/models/charts.py`
- Create: `src/chart_observatory/charts/models.py`, `repository.py`
- Create: `migrations/versions/0005_charts.py`
- Test: `tests/integration/charts/test_chart_repository.py`, `tests/integration/charts/test_immutability.py`

**Interfaces:**
- Produces repositories for `ChartDefinition`, `ChartSnapshot`, and `ChartEntry`.

- [ ] **Step 1: Test provider/platform separation, nullable resolution, null metrics, and immutability.**

```python
def test_unresolved_entry_and_missing_metric_are_preserved(chart_repo, snapshot, item):
    entry = chart_repo.add_entry(snapshot.id, item.id, position=1, metric_value=None)
    assert entry.canonical_track_id is None
    assert entry.metric_value is None


def test_snapshot_update_is_rejected(db, snapshot):
    with pytest.raises(DatabaseError):
        db.execute(text("UPDATE chart_snapshots SET entry_count=99 WHERE id=:id"), {"id": snapshot.id})
```

- [ ] **Step 2: Verify tests fail before tables/triggers exist.**
- [ ] **Step 3: Implement definitions and append-only snapshots/entries with PostgreSQL triggers rejecting update/delete. Include `observed_at`, nullable provider effective-period bounds, native frequency, raw fields, metric type/value, provider JSONB, checksum, versions, and `supersedes_snapshot_id`.**
- [ ] **Step 4: Test that corrections create a second snapshot and do not mutate the first.**
- [ ] **Step 5: Human checkpoint.**

### Task 8: Implement append-only artifact storage and provenance

**Files:**
- Create: `src/chart_observatory/artifacts/models.py`, `store.py`, `manifest.py`
- Create: `src/chart_observatory/db/models/provenance.py`
- Create: `src/chart_observatory/db/models/audit.py`
- Create: `migrations/versions/0006_provenance.py`
- Test: `tests/unit/artifacts/test_store.py`, `tests/integration/artifacts/test_provenance.py`

**Interfaces:**
- Produces: `ArtifactStore.put(bytes, metadata) -> StoredArtifact`; content address is SHA-256.

- [ ] **Step 1: Test content-addressed idempotency and rights enforcement.**

```python
def test_same_bytes_reuse_checksum_without_overwrite(store, permitted_context):
    first = store.put(b"synthetic", permitted_context)
    second = store.put(b"synthetic", permitted_context)
    assert first.sha256 == second.sha256
    assert first.path == second.path


def test_raw_storage_is_denied_without_grant(store, denied_context):
    with pytest.raises(RightsDenied):
        store.put(b"synthetic", denied_context)
```

- [ ] **Step 2: Run tests and verify missing store failure.**
- [ ] **Step 3: Store bytes under `data/raw/sha256/<prefix>/<digest>` using atomic create-if-absent semantics. Persist retrieval/acquisition parameters, media type, byte size, source, rights profile, collector, schema, timestamp, and checksum. Add append-only audit events for rights changes, imports, resolution decisions, exports, and administrative actions. Never overwrite an existing digest.**
- [ ] **Step 4: Verify manifests serialize deterministically, do not contain secrets, and that database triggers reject update/delete of source artifacts and audit events.**
- [ ] **Step 5: Human checkpoint.**

### Task 9: Implement collection runs and the coverage state machine

**Files:**
- Create: `src/chart_observatory/db/models/collection.py`
- Create: `src/chart_observatory/charts/coverage.py`, `collection_runs.py`
- Create: `migrations/versions/0007_collection_coverage.py`
- Test: `tests/unit/charts/test_coverage.py`, `tests/integration/charts/test_collection_runs.py`

**Interfaces:**
- Produces: `CoverageService.record(...)`, `coverage_matrix(...)`, and `common_observation_window(...)`.

- [ ] **Step 1: Test all six coverage states and a balanced-window calculation.**

```python
def test_common_window_requires_available_for_every_selected_chart(coverage):
    window = coverage.common_observation_window(CHART_IDS)
    assert window.start == date(2022, 1, 7)
    assert window.end == date(2026, 8, 28)
    assert window.excluded_cells == 3
```

- [ ] **Step 2: Verify failure before the service exists.**
- [ ] **Step 3: Implement append-audited transitions among `AVAILABLE`, `MISSING`, `NOT_SUPPORTED`, `NOT_LICENSED`, `NOT_COLLECTED`, and `SOURCE_UNAVAILABLE`. Retain each attempt in `collection_runs`; do not use an outage to erase an earlier available snapshot.**
- [ ] **Step 4: Test mixed daily/weekly definitions and ensure the common window does not convert frequencies silently.**
- [ ] **Step 5: Human checkpoint.**

### Task 10: Define adapter ports, registry, and conformance suite

**Files:**
- Create: `src/chart_observatory/charts/ports.py`, `dto.py`, `registry.py`, `ingestion.py`
- Create: `src/chart_observatory/adapters/disabled.py`
- Test: `tests/contract/chart_source_contract.py`, `tests/unit/charts/test_registry.py`, `tests/integration/charts/test_ingestion_service.py`

**Interfaces:**
- Produces exact protocols from the specification, `AdapterRegistry.get_enabled(source_code, operation)`, and `ChartIngestionService.ingest_current(request)`.

- [ ] **Step 1: Write contract tests requiring capabilities, raw preservation, deterministic ordering, metric nullability, and rights checks.**
- [ ] **Step 2: Run registry tests and verify missing adapter failure.**
- [ ] **Step 3: Implement ports, the ingestion coordinator, and disabled registrations for YouTube Music, Spotify Charts, Spotify metadata, Amazon, Soundcharts, Chartmetric, and Luminate. The coordinator checks rights, starts a collection run, stores the raw response, maps definitions/items/snapshot/entries transactionally, and writes coverage. A disabled adapter raises `SourceDisabled` before any HTTP client is invoked.**
- [ ] **Step 4: Run contract tests against a synthetic in-memory adapter.**
- [ ] **Step 5: Human checkpoint.**

### Task 11: Build the schema-configurable manual importer

**Files:**
- Create: `src/chart_observatory/adapters/files/manual.py`, `schema.py`, `validation.py`
- Create: `config/schemas/manual_generic.yaml`
- Create: `tests/fixtures/manual/valid_daily.csv`, `duplicate.csv`, `invalid_rank.csv`, `weekly_missing_metric.csv`
- Test: `tests/unit/adapters/files/test_preview.py`, `tests/integration/adapters/files/test_import.py`

**Interfaces:**
- Produces: `ManualChartImporter.preview(...) -> ImportPreview` and `import_file(...) -> ImportResult`.

- [ ] **Step 1: Test preview without mutation, row-level validation, unknown-column preservation, checksum duplicate detection, and native weekly periods.**

```python
def test_preview_does_not_write_rows(importer, valid_artifact, db):
    preview = importer.preview(valid_artifact, "manual_generic_v1")
    assert preview.valid_rows == 3
    assert db.scalar(select(func.count(ChartEntry.id))) == 0


def test_reimport_is_idempotent(importer, permitted_request):
    first = importer.import_file(permitted_request)
    second = importer.import_file(permitted_request)
    assert first.snapshot_id == second.snapshot_id
    assert second.created_entries == 0
```

- [ ] **Step 2: Run tests and verify missing importer failure.**
- [ ] **Step 3: Parse with Polars, map configurable columns, validate country/date/rank/depth/metric, persist raw bytes first, preserve provider-specific columns in JSONB, create platform items and unresolved entries, and write coverage only after a successful transaction. Require `IMPORT`, `STORE_RAW`, and `STORE_NORMALIZED` grants.**
- [ ] **Step 4: Run importer tests including truncated files, duplicate ranks, repeated positions, missing IDs, and schema drift.**
- [ ] **Step 5: Human checkpoint.**

### Task 12: Implement the disabled Apple Music chart adapter against fixtures

**Files:**
- Create: `src/chart_observatory/adapters/apple_music/auth.py`, `charts.py`, `mapper.py`
- Create: `src/chart_observatory/adapters/http.py`
- Create: `tests/fixtures/apple_music/charts_songs_br.json`, `charts_empty.json`, `rate_limited.json`
- Test: `tests/contract/apple_music/test_chart_source.py`, `tests/unit/adapters/apple_music/test_mapper.py`, `tests/unit/adapters/test_http_policy.py`

**Interfaces:**
- Produces: `AppleMusicChartSource`; consumes `ChartSource`, `RightsGate`, `ArtifactStore`, and an injected HTTP transport.

- [ ] **Step 1: Test request construction and mapping without a network.**

```python
def test_apple_request_is_current_songs_chart(source):
    request = source.build_request(storefront="br", limit=200)
    assert request.path == "/v1/catalog/br/charts"
    assert request.params == {"types": "songs", "chart": "most-played", "limit": 200}


def test_retrieval_date_is_not_invented_as_effective_period(mapped_snapshot):
    assert mapped_snapshot.observed_at is not None
    assert mapped_snapshot.effective_period is None
```

- [ ] **Step 2: Verify failures before adapter creation.**
- [ ] **Step 3: Implement JWT creation behind a secret provider, HTTPX transport injection, bounds `1..200`, mapping of Apple ID, raw ISRC, title, artists, album, release-date precision, content rating when present, genre names as platform metadata, and raw payload. Add a shared bounded HTTP policy: structured logs without credentials/payload bodies, correlation ID, explicit connect/read timeouts, `Retry-After` precedence on 429, jittered exponential backoff when retryable guidance is absent, and no retry for permanent 401/403.**
- [ ] **Step 4: Keep `network_enabled=false`; assert that a real fetch raises `RightsDenied`/`SourceDisabled` before transport invocation. Test 401, 403, ordinary 429, quota-exhausted 429, timeout, malformed JSON, retry exhaustion, and empty chart with fixtures.**
- [ ] **Step 5: Human checkpoint. Apple activation is not part of this task.**

### Task 13: Calculate native-period persistence and rank metrics

**Files:**
- Create: `src/chart_observatory/metrics/models.py`, `track_summary.py`
- Test: `tests/unit/metrics/test_track_summary.py`, `tests/integration/metrics/test_summary_query.py`

**Interfaces:**
- Produces: `summarize_track_platform_country(query) -> TrackPlatformCountrySummary`.

- [ ] **Step 1: Test appearances, distinct periods, `days_or_weeks_in_chart`, dates, peak, mean, median, Top 10/20/50/100, and unit-specific aggregates.**

```python
def test_streams_and_views_never_share_an_aggregate(metric_rows):
    summary = summarize(metric_rows)
    assert summary.stream_sum == Decimal("1500")
    assert summary.view_sum == Decimal("9000")
    assert not hasattr(summary, "popularity_score")
```

- [ ] **Step 2: Verify missing metric implementation failure.**
- [ ] **Step 3: Implement deterministic queries grouped by canonical track, origin platform, country, chart definition, and native frequency. Expose `days_or_weeks_in_chart` as the native-period count with an explicit `period_unit`; never convert weekly observations to days. Exclude unresolved entries from canonical-track rankings but report unresolved numerator/denominator alongside every result.**
- [ ] **Step 4: Test daily and weekly fixtures separately; ensure a weekly period contributes one appearance.**
- [ ] **Step 5: Human checkpoint.**

### Task 14: Implement presence, Top-N overlap, and rank correlation

**Files:**
- Create: `src/chart_observatory/metrics/presence.py`, `overlap.py`, `temporal_alignment.py`
- Test: `tests/unit/metrics/test_presence.py`, `test_overlap.py`, `test_temporal_alignment.py`

**Interfaces:**
- Produces: `presence_summary`, `jaccard_overlap`, `rank_correlations`, and `align_periods`.

- [ ] **Step 1: Test platform/country presence, effective common Top N, Jaccard, Spearman, Kendall, and unresolved reporting.**

```python
def test_overlap_uses_common_observed_depth():
    result = jaccard_overlap(apple_top_100, provider_top_200, requested_top_n=200)
    assert result.effective_top_n == 100
    assert result.method == "RESOLVED_CANONICAL_TRACK_JACCARD"


def test_weekly_daily_alignment_requires_explicit_policy():
    with pytest.raises(TemporalAlignmentRequired):
        align_periods(daily_rows, weekly_rows, policy=None)
```

- [ ] **Step 2: Verify failure before metric modules exist.**
- [ ] **Step 3: Implement `SAME_NATIVE_FREQUENCY` and `INTERVAL_OVERLAP`. Preserve charted-item counts so multiple videos mapped to one recording are not silently summed. Report shared-track sample size and return null correlations when insufficient.**
- [ ] **Step 4: Compare results with hand-calculated synthetic fixtures.**
- [ ] **Step 5: Human checkpoint.**

### Task 15: Build versioned exports and analysis-run manifests

**Files:**
- Create: `src/chart_observatory/db/models/analysis.py`
- Create: `src/chart_observatory/exports/models.py`, `writer.py`, `datasets.py`, `manifest.py`
- Create: `migrations/versions/0008_analysis_exports.py`
- Test: `tests/integration/exports/test_datasets.py`, `tests/unit/exports/test_manifest.py`

**Interfaces:**
- Produces five named datasets and `ExportManifest` with input snapshot IDs/checksums and analysis parameters.

- [ ] **Step 1: Test exact schemas for `track_master`, `chart_observations`, `track_platform_country_summary`, `cross_platform_presence`, and `coverage_matrix`.**
- [ ] **Step 2: Test that export is denied without `ANALYZE` and the requested export grant.**
- [ ] **Step 3: Write CSV and Parquet atomically. Manifests include dataset name/schema version, row count, file checksum, source rights profiles, chart/methodology versions, resolution-rule version, date window, Top N, temporal policy, input artifacts/snapshots, software version, Git revision when available, dirty-state/patch hash, and creation time.**
- [ ] **Step 4: Round-trip both formats and compare nulls, decimals, dates, and row order.**
- [ ] **Step 5: Human checkpoint.**

### Task 16: Expose CLI, FastAPI, Streamlit, and complete the 1A acceptance pass

**Files:**
- Create: `src/chart_observatory/api/app.py`, `dependencies.py`
- Create: `src/chart_observatory/api/routes/charts.py`, `tracks.py`, `coverage.py`, `rights.py`, `exports.py`
- Create: `src/chart_observatory/cli.py`
- Create: `src/chart_observatory/ui/app.py`, `pages/rankings.py`, `frequent.py`, `platforms.py`, `international.py`, `coverage.py`, `provenance.py`, `resolution.py`
- Create: `tests/integration/api/test_read_routes.py`, `test_import_route.py`
- Create: `tests/e2e/test_milestone_1a.py`
- Create: `research/data_dictionary.md`, `research/methodology.md`, `research/limitations.md`

**Interfaces:**
- Produces user workflows for preview/import, browsing, metrics, coverage, provenance, review queue, and exports.

- [ ] **Step 1: Write an end-to-end test that imports an authorized synthetic file and queries every 1A view.**

```python
def test_milestone_1a_without_spotify(app_client, synthetic_chart_file):
    preview = app_client.preview_import(synthetic_chart_file)
    result = app_client.confirm_import(preview.token)
    assert result.entry_count > 0
    assert app_client.rankings(country="BR").rows
    assert app_client.coverage(country="BR").cells
    assert app_client.export("chart_observations", "parquet").manifest_sha256
```

- [ ] **Step 2: Verify the test fails before entry points exist.**
- [ ] **Step 3: Implement Typer commands `collect current --source --country --chart`, `import-chart preview`, `import-chart apply`, `coverage show`, `metrics summarize`, and `export create`. `collect current` must return a clear denied/disabled result before network access when grants are absent. Implement read APIs and the Streamlit filters Country, Platform, Provider, Chart, Date Range, Native Frequency, Top N, and Resolution State. No endpoint may bypass application services or the rights gate.**
- [ ] **Step 4: Run `pytest -m "not live"`, migration upgrade/downgrade/upgrade, Ruff, type checking, and a Docker Compose smoke test. Verify the application starts with every Spotify adapter removed from the registry.**
- [ ] **Step 5: Generate a synthetic 1A acceptance report showing rankings, persistence, provenance, coverage, unresolved rates, and all five exports. Stop implementation for human review.**
- [ ] **Step 6: Human decides whether to commit and whether Milestone 1B may begin. The agent does neither automatically.**

---

## Milestone 1B — requires a new approval after 1A

### Task 17: Implement the YouTube video-most-popular adapter against fixtures

**Files:**
- Create: `src/chart_observatory/adapters/youtube_data/auth.py`, `categories.py`, `most_popular.py`, `mapper.py`
- Create: `tests/fixtures/youtube_data/most_popular_br.json`, `categories_br.json`, `quota_error.json`
- Test: `tests/contract/youtube_data/test_most_popular_source.py`

**Interfaces:**
- Produces: `YouTubeMostPopularSource` with `chart_family=YOUTUBE_VIDEO_MOST_POPULAR` and `ranked_item_kind=VIDEO`.

- [ ] **Step 1: Test region/category discovery, video identity, optional statistics, pagination, quota accounting, and the non-equivalence label.**
- [ ] **Step 2: Verify fixture tests fail before adapter creation.**
- [ ] **Step 3: Implement API-key injection, `videos.list` request construction, `i18nRegions.list`/`videoCategories.list` discovery, page-token traversal, response mapping, and raw preservation. Do not hardcode YouTube Music semantics or ISRC.**
- [ ] **Step 4: Test 400/401/403/429, quota exhaustion, missing statistics, deleted/private videos, category changes, timeouts, and the 2026 `viewCount` definition as a methodology-version boundary. Keep network disabled without an approved rights profile.**
- [ ] **Step 5: Human checkpoint.**

### Task 18: Validate 1B across nine countries without merging video and song constructs

**Files:**
- Create: `tests/e2e/test_milestone_1b.py`
- Modify: `src/chart_observatory/ui/pages/platforms.py`, `coverage.py`
- Modify: `research/methodology.md`, `limitations.md`

**Interfaces:**
- Consumes all 1A metrics and the YouTube adapter; produces an explicit video-chart comparison view.

- [ ] **Step 1: Add synthetic/authorized fixtures for BR, US, GB, FR, DE, ES, PT, IT, and SE.**
- [ ] **Step 2: Test that chart labels say “YouTube Video Most Popular,” that no view/stream aggregate is shared, and that two videos linked to one track remain two ranked observations.**
- [ ] **Step 3: Add coverage and methodology-break displays; expose YouTube category and view-count-definition version in provenance.**
- [ ] **Step 4: Run the complete non-live suite and produce the 1B acceptance report.**
- [ ] **Step 5: Stop for human review; the agent does not start 1C or commit.**

---

## Milestone 1C — historical provider decision gate

No production adapter is planned before the provider is selected, because endpoint schemas, coverage, price, and license are mutually constraining inputs. The gate deliverable is a signed decision record, not code.

Required sequence:

1. Request coverage extracts and order-form language from Luminate, Soundcharts, and Chartmetric using the 20 procurement questions in `research/historical_sources_assessment.md`.
2. Run each sample through a disposable schema profiler without adding it to the research corpus.
3. Compare verified `platform × country × date × chart family` coverage, gaps, methodology breaks, identifiers, units, depth, quotas, and total cost.
4. Obtain institutional/legal approval for storage, analysis, coauthor/reviewer access, aggregate publication, and replication.
5. Ask the user to select one provider and approve cost.
6. Write a provider-specific design addendum and TDD implementation plan using the exact contracted schema.

Exit evidence: approved rights profile, coverage matrix, sample checksum/schema, data dictionary, methodology, price, quota/SLA, and replication rule. Without all evidence, status remains `PENDING` and the adapter remains disabled.

## Milestone 1D — later authorized sources

Spotify, YouTube Music, Amazon Music, Apple network collection, and institutional/historical files enter only through existing ports. Each source must:

1. pass the rights gate for every intended operation;
2. declare origin platform separately from provider;
3. pass the common adapter conformance suite;
4. preserve native chart methodology/frequency/depth;
5. provide a verified coverage manifest;
6. avoid a domain migration unless the source introduces a genuinely new scientific construct;
7. receive a separate human activation decision.

## Final acceptance criteria for Milestone 1

- For every selected country/platform/provider/window, users can inspect rank, native period, peak, persistence, identifiers, ISRC when available, source, provider, rights, and coverage.
- The system can rank most persistent tracks, most Top-10/20/50 appearances, best mean rank, highest peak, most countries reached, and most platforms reached without a combined score.
- Cross-platform Jaccard and rank correlations use an explicit common Top N and report shared/unresolved sample sizes.
- A common observation window can be recommended from actual coverage but is never silently imposed.
- Every observation traces to an immutable artifact, snapshot, parser/collector version, provider/methodology, and rights profile.
- CSV and Parquet exports are reproducible from their manifests.
- Disabling or removing Spotify leaves every core capability operational.
- No feature answers what songs “are about”; content analysis remains a later milestone.
