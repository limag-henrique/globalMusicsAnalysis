# Operational PostgreSQL and Global Chart Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing research corpus operational through one PostgreSQL-backed application and expose a resumable, provider-neutral global Chartmetric backfill without losing the already materialized source artifacts.

**Architecture:** PostgreSQL is the operational source of truth for imported observations, identity evidence, coverage, and canonical memberships. CLI, FastAPI, and Streamlit construct the same configured `ResearchApplication`; large historical artifacts remain append-only Parquet/raw evidence and are loaded through explicit idempotent commands. Chartmetric collection remains rights-aware and opt-in, with discovery, date intersection, resumable checkpoints, raw JSON, normalized Parquet, and source-preserving catalog reconciliation.

**Tech Stack:** Python 3.12, SQLAlchemy 2, Alembic, PostgreSQL 16, Docker Compose, Typer, FastAPI, Streamlit, Polars, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-07-canonical-scientific-corpus-design.md` plus the user-confirmed Global Chart Backfill brief.

## Global Constraints

- Do not create commits or change branches.
- PostgreSQL is the production/default database; SQLite remains test-only.
- Preserve provider and origin-platform semantics separately.
- Preserve unresolved observations and raw provenance; never silently drop them.
- Chartmetric network collection requires explicit `--allow-network`.
- Existing MGD/Kaggle/YouTube/Pro-Música artifacts remain source-specific and auditable.
- Historical Chartmetric availability is discovered from the provider, not assumed from a calendar.

---

### Task 1: Make PostgreSQL the configured application seam

**Files:**
- Modify: `src/chart_observatory/application.py`
- Modify: `src/chart_observatory/api/app.py`
- Modify: `src/chart_observatory/ui/app.py`
- Modify: `src/chart_observatory/cli.py`
- Modify: `compose.yaml`
- Create: `tests/integration/application/test_operational_application.py`

- [ ] Add a failing test proving a fresh application/session can read rows imported by a previous application instance using the same database URL.
- [ ] Add a settings-backed application factory used by API, CLI, and Streamlit.
- [ ] Add an explicit `db upgrade` command and make the deployment path run Alembic before serving.
- [ ] Route Streamlit operational pages through the application/database while retaining Parquet for bounded analytical artifacts.
- [ ] Run the new test and all application/API tests.

### Task 2: Make manual imports provider-neutral and identity-rich

**Files:**
- Modify: `src/chart_observatory/adapters/files/schema.py`
- Modify: `src/chart_observatory/adapters/files/manual.py`
- Modify: `config/schemas/manual_generic.yaml`
- Create: `config/schemas/manual_spotify_legacy.yaml`
- Modify: `src/chart_observatory/db/models/tracks.py`
- Create: `migrations/versions/0012_track_metadata.py`
- Create: `tests/unit/adapters/files/test_generic_metadata.py`
- Create: `tests/integration/adapters/files/test_generic_sql_import.py`

- [ ] Write failing tests for import metadata (`provider`, `origin_platform`, `chart_family`, frequency, metric) and artist/ISRC fields.
- [ ] Implement explicit import metadata in CLI/API requests and schema validation; remove Spotify/Streams assumptions from the generic profile.
- [ ] Persist artist, ISRC, duration, and release-date evidence on platform items and external-ID claims.
- [ ] Keep the existing fixtures working through an explicitly named Spotify legacy profile.
- [ ] Run importer, API, and SQL integration tests.

### Task 3: Add artist-aware review-safe resolution

**Files:**
- Modify: `src/chart_observatory/tracks/normalization.py`
- Modify: `src/chart_observatory/tracks/repository.py`
- Modify: `src/chart_observatory/tracks/resolution.py`
- Modify: `src/chart_observatory/db/models/tracks.py`
- Create: `tests/unit/tracks/test_artist_aware_resolution.py`

- [ ] Write failing tests for exact ISRC, normalized artist+title, artist+title+duration/release evidence, and ambiguous fuzzy candidates.
- [ ] Implement deterministic normalized artist/title matching and evidence scores.
- [ ] Keep fuzzy candidates in `NEEDS_REVIEW`; never auto-confirm a fuzzy-only match.
- [ ] Persist every attempt and candidate evidence with a versioned rule.
- [ ] Run all track-resolution tests.

### Task 4: Complete Chartmetric historical discovery and platform inventory

**Files:**
- Modify: `src/chart_observatory/sources/chartmetric.py`
- Modify: `src/chart_observatory/cli.py`
- Create: `tests/unit/sources/test_chartmetric_discovery.py`

- [ ] Write failing tests proving `fromDaysAgo=9999`, `--all-history`, platform discovery, and per-platform market listing.
- [ ] Remove the artificial 28-day limit and expose `chartmetric platforms` and `chartmetric markets --platform`.
- [ ] Support Spotify, Apple Music, YouTube Top Tracks, and Amazon using explicit provider/origin-platform mappings, recording entitlement failures as unavailable.
- [ ] Run Chartmetric unit/CLI tests without network.

### Task 5: Connect discovered dates to resumable global backfill

**Files:**
- Modify: `src/chart_observatory/sources/chartmetric_backfill.py`
- Modify: `src/chart_observatory/cli.py`
- Modify: `src/chart_observatory/sources/catalog.py`
- Create: `tests/unit/sources/test_chartmetric_backfill_dates.py`

- [ ] Write failing tests for market/date intersection, `--all-markets`, `--all-dates`, `--resume`, and stable empty/unavailable results.
- [ ] Extend the backfill request with discovered provider dates and plan only valid market/date cells.
- [ ] Consolidate task Parquets into `chartmetric_observations.parquet` with raw JSON and source manifest entries.
- [ ] Preserve provider and origin-platform fields in the unified catalog.
- [ ] Run offline backfill tests and a bounded live smoke test for BR historical dates when credentials/network are available.

### Task 6: Canonicalize and load the existing corpus operationally

**Files:**
- Modify: `src/chart_observatory/ingestion/corpus.py`
- Modify: `src/chart_observatory/corpus/catalog_reconciliation.py`
- Modify: `src/chart_observatory/cli.py`
- Create: `tests/integration/ingestion/test_operational_corpus_load.py`
- Modify: `research/corpus_v1_status.md`
- Modify: `research/limitations.md`

- [ ] Write a failing idempotence test for loading a bounded source-preserving corpus into PostgreSQL.
- [ ] Load existing MGD, Kaggle, YouTube video, Pro-Música, and any completed Chartmetric artifacts without collapsing source rows.
- [ ] Reconcile by source precedence (`MGD` through 2022-03-13, Chartmetric afterward, Kaggle validation) and preserve conflicts.
- [ ] Materialize genre claims/diversity and coverage in the operational database or explicit derived manifests.
- [ ] Run migrations, bounded load, reconciliation, and freeze commands.

### Task 7: Full verification and operational handoff

**Files:**
- Modify: `README.md` or operational documentation if present
- Modify: `research/corpus_v1_status.md`
- Modify: `research/limitations.md`

- [ ] Start PostgreSQL with Compose and wait for health.
- [ ] Apply Alembic to head and verify schema version.
- [ ] Run unit, integration, API, CLI, Ruff, and mypy checks.
- [ ] Run the three historical Chartmetric smoke dates and the multi-market sample when credentials permit.
- [ ] Verify a row imported by CLI is visible after process restart through API and Streamlit data access.
- [ ] Record exact completed counts, unavailable entitlements, and remaining external-data limitations.

