# Canonical Scientific Music Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing chart corpus operational, canonical, comparable, frozen as Corpus v1, and ready for RQ1–RQ5 analysis.

**Architecture:** Keep immutable provider snapshots as the source boundary and add PostgreSQL-backed derived repositories for canonical entries, geography, coverage profiles, eligibility, corpus freezes, metadata claims, and analytical outputs. One `ResearchApplication` composes those repositories for CLI/API/UI.

**Tech Stack:** Python 3.12, SQLAlchemy/Alembic, PostgreSQL/SQLite tests, Polars, SciPy, statsmodels, lifelines, Typer, FastAPI, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-07-canonical-scientific-corpus-design.md`

## Global Constraints

- Never mutate immutable source chart snapshots or entries.
- Never use provider IDs as canonical track identity.
- Preserve unresolved rows and expose their denominators.
- Keep provider and origin platform separate.
- Use configuration for scientific thresholds; do not hide them in algorithms.
- Do not invent missing historical observations or silently treat missing as zero.
- Do not create git commits or change branches.
- Keep network collection explicit, bounded, and rights-aware.

---

### Task 1: Make the PostgreSQL application the operational seam

**Files:**
- Create: `src/chart_observatory/application/research.py`
- Modify: `src/chart_observatory/application.py`
- Modify: `src/chart_observatory/api/app.py`
- Modify: `src/chart_observatory/api/dependencies.py`
- Modify: `src/chart_observatory/cli.py`
- Test: `tests/integration/application/test_research_application.py`

**Interfaces:**
- `ResearchApplication(root: Path, database_url: str | None = None, manual_authorized: bool = False)`
- `session_factory`, `charts`, `tracks`, `export(dataset_name, format)`, and `import_manual(path, schema)` are public seams.
- Keep a short compatibility alias only while all callers move to `ResearchApplication`.

- [ ] Write a test proving imported chart rows are persisted and readable after a new SQLAlchemy session.
- [ ] Implement engine/session construction and PostgreSQL-backed repositories.
- [ ] Route API, CLI, and existing exports through the application object.
- [ ] Run the focused integration tests and the existing API tests.

### Task 2: Add canonical reconciliation, geography, claims, and corpus freeze tables

**Files:**
- Create: `migrations/versions/0010_canonical_scientific_corpus.py`
- Create: `src/chart_observatory/db/models/corpus.py`
- Modify: `src/chart_observatory/db/models/__init__.py`
- Create: `src/chart_observatory/corpus/repository.py`
- Test: `tests/integration/corpus/test_corpus_repository.py`

**Interfaces:**
- `reconcile_entries(session, precedence) -> ReconciliationSummary`
- `profile_chart_cells(session, ...) -> list[ChartCellProfile]`
- `freeze_corpus(session, request) -> CorpusVersion`
- `normalize_genre(label) -> str` and `normalize_language(code) -> str`

- [ ] Write tests for same-track duplicate collapse, rank conflict retention, geography lookup, claim provenance, and immutable freeze membership.
- [ ] Add migration/model tables and indexes.
- [ ] Implement source precedence and `SOURCE_CONFLICT` records without deleting source rows.
- [ ] Add ISO/UN M49 metadata for every observed market and fail loudly for unknown codes.
- [ ] Run SQLite integration tests and Alembic metadata checks.

### Task 3: Implement comparable corpus and balanced panel selection

**Files:**
- Modify: `config/research.yaml`
- Create: `src/chart_observatory/corpus/eligibility.py`
- Create: `src/chart_observatory/corpus/freeze.py`
- Create: `src/chart_observatory/exports/corpus.py`
- Test: `tests/unit/corpus/test_eligibility.py`
- Test: `tests/integration/corpus/test_freeze.py`

**Interfaces:**
- `EligibilityRules(minimum_coverage, minimum_years, minimum_chart_depth, minimum_source_quality)`
- `evaluate_cell(observations, rules) -> EligibilityResult`
- `select_comparable_cells(profiles, rules) -> list[EligibilityResult]`
- `select_balanced_panel(cells, corpus_start, corpus_end) -> BalancedPanel`

- [ ] Write failing tests for expected-period calculation, longest gaps, inclusive years, and common-period intersection.
- [ ] Implement profile metrics and deterministic eligibility reasons.
- [ ] Freeze the observed MGD corpus as Corpus v1 and emit manifest plus membership exports.
- [ ] Run the selector against the full local corpus and record row counts and bounds.

### Task 4: Add genres, languages, lyrics, and semantic annotations

**Files:**
- Create: `src/chart_observatory/metadata/taxonomy.py`
- Create: `src/chart_observatory/lyrics/repository.py`
- Create: `src/chart_observatory/lyrics/annotations.py`
- Create: `src/chart_observatory/metadata/mgd.py`
- Test: `tests/unit/metadata/test_taxonomy.py`
- Test: `tests/unit/lyrics/test_annotations.py`

**Interfaces:**
- `GenreTaxonomy.normalize(raw_label) -> normalized_label`
- `ingest_genre_claim(...)`, `ingest_language_claim(...)`, `ingest_lyric_document(...)`
- `annotate_document(document, annotations, model_version) -> list[SemanticAnnotation]`

- [ ] Write tests for funk label normalization, multilingual language claims, confidence/review status, and category prevalence inputs.
- [ ] Load MGD artist genre metadata as source claims without overwriting raw labels.
- [ ] Add rights/provenance-aware lyric document and category annotation persistence.
- [ ] Run claim and annotation tests; leave missing lyrics explicit rather than scraping unapproved sources.

### Task 5: Implement turnover, exposure/prevalence, and genre diversity metrics

**Files:**
- Create: `src/chart_observatory/metrics/turnover.py`
- Create: `src/chart_observatory/metrics/content.py`
- Create: `src/chart_observatory/metrics/diversity.py`
- Test: `tests/unit/metrics/test_turnover.py`
- Test: `tests/unit/metrics/test_content.py`
- Test: `tests/unit/metrics/test_diversity.py`

**Interfaces:**
- `compute_turnover(period_a, period_b, top_n=50) -> TurnoverMetrics`
- `category_prevalence(rows) -> DataFrame`
- `category_exposure(rows) -> DataFrame`
- `genre_diversity(distribution) -> DiversityMetrics`
- `jensen_shannon(left, right) -> float`

- [ ] Write red tests for Jaccard, new/exit/retained counts, rank displacement, weighted exposure, and standard diversity formulas.
- [ ] Implement pure functions over resolved canonical observations and explicit unresolved denominators.
- [ ] Produce the analytical dataset schemas and confidence intervals using deterministic bootstrap/Wilson methods.
- [ ] Run metric tests and a bounded local MGD calculation.

### Task 6: Implement RQ1–RQ4 and survival models

**Files:**
- Create: `src/chart_observatory/analysis/models.py`
- Create: `src/chart_observatory/analysis/rq.py`
- Create: `src/chart_observatory/analysis/survival.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/analysis/test_models.py`
- Test: `tests/unit/analysis/test_survival.py`

**Interfaces:**
- `fit_rq2_content_country(frame) -> ModelResult`
- `fit_rq3_content_country_genre(frame) -> ModelResult`
- `fit_rq4_success(frame, outcome) -> ModelResult`
- `fit_survival(frame) -> SurvivalResult`

- [ ] Write tests against small independent fixtures for coefficient names, confidence intervals, group effects, and censoring.
- [ ] Add statsmodels/lifelines dependencies and model adapters with explicit `INSUFFICIENT_DATA` results.
- [ ] Implement mixed-effects random intercepts for track/artist/country where supported and document fallback behavior.
- [ ] Implement Kaplan–Meier and Cox proportional hazards with diagnostics.
- [ ] Run focused model tests and verify no model runs on empty semantic data.

### Task 7: Materialize datasets and replace empty exports

**Files:**
- Modify: `src/chart_observatory/exports/datasets.py`
- Modify: `src/chart_observatory/application.py`
- Create: `src/chart_observatory/exports/analytical.py`
- Modify: `src/chart_observatory/api/routes/exports.py`
- Test: `tests/integration/exports/test_scientific_datasets.py`

**Interfaces:**
- `build_dataset(session, dataset_name, corpus_version_id) -> polars.DataFrame`
- Dataset names include prevalence, exposure, turnover, diversity, eligibility, balanced panel, RQ2, RQ3, RQ4, survival, and canonical master tables.

- [ ] Write tests proving `track_master`, `track_platform_country_summary`, and `cross_platform_presence` are populated from PostgreSQL.
- [ ] Implement all requested analytical datasets with schema validation and manifest hashes.
- [ ] Add API/CLI dataset listing and export support.
- [ ] Run integration exports against SQLite and PostgreSQL when available.

### Task 8: Pull and ingest the maximum authorized data available

**Files:**
- Modify: `src/chart_observatory/cli.py`
- Modify: `src/chart_observatory/sources/mgd.py`
- Modify: `src/chart_observatory/sources/kaggle.py`
- Modify: `src/chart_observatory/sources/promusica.py`
- Create: `src/chart_observatory/ingestion/corpus.py`
- Test: `tests/integration/ingestion/test_local_corpus.py`

- [ ] Inspect all local MGD files and existing normalized artifacts before importing.
- [ ] Import MGD idempotently into PostgreSQL, resolve available tracks, load geography/genre claims, and freeze Corpus v1.
- [ ] If Kaggle is configured/cached, download/import it for validation and conflict reporting; otherwise record `NOT_AVAILABLE`.
- [ ] If public Pro-Música collection is explicitly configured, discover/download/parse historical items; otherwise preserve current artifact and report the gap.
- [ ] Run a bounded YouTube discovery/viral collection only when an API key and explicit opt-in are present.

### Task 9: Remove Apple Music and finish verification

**Files:**
- Delete: `src/chart_observatory/adapters/apple_music/`
- Delete: `tests/contract/apple_music/`, `tests/unit/adapters/apple_music/`
- Modify: documentation and inventories that mention Apple Music as an active source
- Modify: `graphify-out/` only through `graphify update .` if available

- [ ] Identify exact Apple Music files and references before deletion.
- [ ] Remove only project-owned Apple Music implementation/tests/configuration; do not touch unrelated historical citations.
- [ ] Run non-live tests, Ruff, mypy, Alembic upgrade, and corpus freeze verification.
- [ ] Report actual row counts, coverage, unresolved resolution, conflicts, model statuses, and remaining external-data blocks without committing.

