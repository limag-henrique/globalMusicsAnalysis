+# Research Corpus and Article Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the available multi-source chart observations into reproducible, article-ready datasets for content, persistence, genre, and virality analysis without inventing unavailable history or lyrics.

**Architecture:** Keep the source-preserving catalog as the ingestion boundary, add a canonical analytical layer that resolves track identities while retaining source rows and conflicts, and expose pure metric builders plus versioned exports. MGD/Kaggle provide the current longitudinal track corpus; YouTube remains a separate video-virality corpus; Chartmetric is appended through its bounded authenticated backfill when available.

**Tech Stack:** Python 3.12, Polars, SQLAlchemy/Alembic, Typer, Streamlit, pytest, Ruff, mypy, statsmodels, lifelines.

**Spec:** `docs/superpowers/specs/2026-09-07-global-multi-source-corpus-design.md`, `docs/superpowers/specs/2026-09-07-canonical-scientific-corpus-design.md`, and `docs/superpowers/specs/2026-09-08-research-browser-classification-design.md`.

## Global Constraints

- Preserve every source observation and raw artifact.
- Keep `provider`, `origin_platform`, `item_kind`, chart family, native period, and metric type separate.
- Never treat YouTube Video Most Popular as YouTube Music Top Songs.
- Never use a provider-native ID as an unquestioned cross-source identity.
- Missing metrics and missing lyrics remain null or explicit pending statuses, never zero or fabricated content.
- Do not scrape lyrics or use unapproved private endpoints.
- Do not create commits or change branches.
- Every analytical output records source inputs, methodology/resolution versions, parameters, and hashes.

---

### Task 1: Make the catalog contract complete and auditable

**Files:**
- Modify: `src/chart_observatory/sources/catalog.py`
- Create: `tests/unit/sources/test_catalog_quality.py`
- Modify: `research/source_inventory.md`
- Modify: `research/limitations.md`

**Interfaces:**
- Produce `catalog_quality_report(paths) -> pl.DataFrame` with provider, chart family, market count, row count, date bounds, native frequency, null metric count, and item kind.
- Preserve the current 34-column normalized contract and explicitly report source-specific fields not represented in that contract.
- Keep source discovery deterministic and materialization idempotent.

- [x] Write a failing test for quality summaries and for distinguishing missing Chartmetric from zero Chartmetric rows.
- [x] Run `.venv\\Scripts\\pytest.exe tests/unit/sources/test_catalog_quality.py -q` and verify the expected failure.
- [x] Implement the summary using lazy scans and streaming aggregation; do not load the 47-million-row catalog eagerly.
- [x] Add the current source counts and the corrected Kaggle status to the documentation.
- [x] Run the focused test and the full non-live suite.

### Task 2: Add a canonical catalog reconciliation layer

**Files:**
- Create: `src/chart_observatory/corpus/catalog_reconciliation.py`
- Create: `tests/unit/corpus/test_catalog_reconciliation.py`
- Modify: `src/chart_observatory/exports/datasets.py`
- Modify: `research/corpus_v1_status.md`

**Interfaces:**
- Produce `reconcile_catalog(frame, precedence) -> tuple[pl.DataFrame, pl.DataFrame]`, returning canonical observations and a conflict table.
- Match only by normalized native identity within a provider/platform or by explicit cross-source evidence; title/artist matches remain candidate matches unless configured as exact evidence.
- Output `canonical_track_id`, `resolution_status`, `selected_provider`, `source_observation_keys`, and conflict metadata without deleting source rows.

- [x] Write tests for exact same-provider IDs, MGD/Kaggle overlap, unresolved title collisions, metric/rank conflicts, and source-row preservation.
- [x] Run the focused tests and verify failure before implementation.
- [x] Implement deterministic keys, precedence, conflict retention, and unresolved denominators with Polars.
- [x] Add canonical and conflict schemas to the export registry.
- [x] Run focused and regression tests.

### Task 3: Complete persistence, turnover, and genre analytical datasets

**Files:**
- Modify: `src/chart_observatory/exports/analytical.py`
- Create: `tests/unit/exports/test_article_analytics.py`
- Modify: `src/chart_observatory/metrics/turnover.py`
- Modify: `src/chart_observatory/metrics/diversity.py`

**Interfaces:**
- Produce `build_persistence_dataset(observations, top_n) -> pl.DataFrame`.
- Produce `build_market_anxiety_dataset(observations, top_n) -> pl.DataFrame` with turnover, Jaccard, new entries, exits, retained tracks, and rank displacement.
- Produce `build_genre_variation_dataset(observations, genre_claims) -> pl.DataFrame` and `build_genre_distance_dataset(distributions) -> pl.DataFrame`.
- Keep daily/weekly periods in native frequency and make the weighting policy explicit.

- [x] Write failing tests for persistence duration, censored exits, country comparisons, genre shares, Shannon/Simpson/HHI, and Jensen–Shannon distance.
- [x] Run focused tests and verify expected failures.
- [x] Implement pure functions over normalized/resolved observations, including explicit unresolved counts.
- [x] Materialize non-empty MGD persistence, turnover, genre variation, and genre-distance outputs.
- [x] Run focused tests, full tests, and schema validation.

### Task 4: Build content annotation inputs and RQ1–RQ4 exports

**Files:**
- Modify: `src/chart_observatory/ui/classifications.py`
- Modify: `src/chart_observatory/lyrics/annotations.py`
- Create: `src/chart_observatory/metrics/content_profile.py`
- Create: `tests/unit/metrics/test_content_profile.py`
- Create: `tests/unit/analysis/test_article_models.py`
- Modify: `src/chart_observatory/analysis/rq.py`
- Modify: `src/chart_observatory/exports/analytical.py`

**Interfaces:**
- Produce nine category dimensions: `sexual_explicitness`, `objectification`, `transactional_sex`, `materialism`, `drugs`, `crime`, `violence`, `romantic_affection`, and `heartbreak`.
- Represent both presence/intensity and framing where applicable; distinguish “mentioned” from “glorified”.
- Produce prevalence, exposure, country effects, country-by-genre effects, and content-success datasets with Wilson confidence intervals and explicit missing-annotation denominators.
- Return `INSUFFICIENT_DATA` when lyrics/annotations are absent.

- [ ] Write failing tests for null versus zero, presence versus framing, country prevalence, genre-controlled comparisons, and empty authorized-lyrics input.
- [ ] Run focused tests and verify failure.
- [x] Implement the content profile and connect it to the existing classification workbench without creating lyrics.
- [ ] Replace placeholder empty-output paths with real builders that consume annotated records and preserve pending status when no records exist.
- [ ] Add RQ1 descriptive content summaries and complete RQ2, RQ3, and RQ4 exports.
- [ ] Run focused tests and regression tests.

### Task 5: Implement viralidade and cross-source relationship datasets

**Files:**
- Create: `src/chart_observatory/metrics/virality.py`
- Create: `tests/unit/metrics/test_virality.py`
- Create: `src/chart_observatory/analysis/virality.py`
- Create: `tests/unit/analysis/test_virality.py`
- Modify: `src/chart_observatory/exports/analytical.py`
- Modify: `research/methodology.md`

**Interfaces:**
- Produce `link_virality_to_tracks(track_observations, video_observations, resolved_links) -> pl.DataFrame`.
- Produce `build_virality_features(rows) -> pl.DataFrame` with video rank, views, view velocity where dates allow, count of linked videos, and platform/source flags.
- Produce `fit_rq5_virality(frame) -> ModelResult` for content × virality × chart-success interactions, with explicit insufficiency status.
- Never sum views across distinct videos unless a documented aggregation unit is selected.

- [x] Write failing tests for one-to-many video-to-track links, unresolved videos, null statistics, exposure windows, and interaction-model insufficiency.
- [x] Run focused tests and verify failure.
- [x] Implement deterministic aggregation and the RQ5 model over linked, resolved tracks only.
- [ ] Materialize `virality_features` and `rq5_virality` with methodology/version metadata.
- [x] Run focused tests and regression tests.

### Task 6: Complete Chartmetric historical ingestion and catalog refresh

**Files:**
- Modify: `src/chart_observatory/sources/chartmetric_backfill.py`
- Modify: `src/chart_observatory/cli.py`
- Create: `tests/integration/sources/test_chartmetric_backfill_artifact.py`
- Modify: `research/source_inventory.md`
- Modify: `research/ingestion_acceptance_report.md`

**Interfaces:**
- Use the existing explicit `sources chartmetric dates/collect/backfill` commands.
- Require an explicit market list, chart type, interval, start/end window, and `--allow-network`.
- Produce resumable per-market/per-period artifacts with source hashes and a missing-period manifest.
- Append Chartmetric rows to the unified catalog only after schema/coverage validation.

- [ ] Write a fixture test for resumable artifact discovery, null metric handling, and failed-period reporting.
- [ ] Run the focused test and verify failure.
- [ ] Implement artifact validation and catalog refresh; do not broaden collection defaults.
- [x] If the configured credential and rights profile are available, run a bounded pilot for one market and one historical window; otherwise record `NOT_CONFIGURED` or `NOT_AVAILABLE`.
- [x] Run the pilot, verify row counts/date bounds, then decide whether a broader backfill is operationally feasible.
- [x] Run full tests and update the acceptance report.

### Task 7: Operational PostgreSQL load, freeze, and export manifests

**Files:**
- Modify: `src/chart_observatory/application.py`
- Modify: `src/chart_observatory/corpus/repository.py`
- Create: `tests/integration/application/test_article_corpus_application.py`
- Modify: `src/chart_observatory/cli.py`
- Modify: `research/corpus_v1_status.md`

**Interfaces:**
- Load source-preserving observations and canonical memberships into PostgreSQL when the service is available.
- Produce immutable Corpus v1 membership, analytical artifact hashes, resolution version, and rights profile metadata.
- Fix strict typing in `application.py` without changing behavior.

- [ ] Write failing integration/type tests for populated exports, memberships, immutable freeze metadata, and typed SQL result handling.
- [ ] Run focused tests and verify failure.
- [ ] Implement the minimal typed fixes and operational load/export path.
- [ ] Start PostgreSQL only if the local environment supports it; otherwise preserve explicit pending status.
- [ ] Run SQLite integration, PostgreSQL checks when available, Ruff, mypy, and pytest.

### Task 8: Research browser and documentation acceptance

**Files:**
- Modify: `src/chart_observatory/ui/app.py`
- Modify: `src/chart_observatory/ui/pages/observations.py`
- Modify: `research/source_inventory.md`
- Modify: `research/provider_capabilities.md`
- Modify: `research/limitations.md`
- Modify: `research/methodology.md`

**Interfaces:**
- Show source coverage, missing artifacts, native metric units, unresolved counts, annotation status, and analysis availability.
- Keep country/year/provider/chart filters bounded and source-aware.
- Document which results are longitudinal, current-state, video-only, validation-only, or pending authorization.

- [ ] Write failing UI helper tests for pending Chartmetric, current YouTube video semantics, and missing lyrics.
- [ ] Run focused tests and verify failure.
- [x] Implement the smallest UI/documentation changes needed for honest interpretation.
- [x] Run Streamlit import/smoke verification and all automated checks.
- [x] Run `graphify update .` and inspect `git status --short`.
