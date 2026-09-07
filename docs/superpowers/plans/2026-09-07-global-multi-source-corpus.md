# Global Multi-Source Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an auditable global-first corpus and operational source inventory with recent ranked artists/tracks by country and year.

**Architecture:** Preserve the current chart/track/provenance seams and add a deep source-inventory module that streams files into normalized observations, manifests, coverage cells, and reports. Network providers implement discovery/collection adapters behind injected HTTP transports; blocked capabilities remain explicit rather than silently omitted.

**Tech Stack:** Python 3.12, Polars, PyArrow, SQLAlchemy/Alembic, Typer, Streamlit, httpx, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-07-global-multi-source-corpus-design.md`

## Global Constraints

* Never use a provider ID as the canonical research identity.
* Always persist `provider` separately from `origin_platform`.
* Ingest broadly and filter analytically; do not hardcode a country whitelist.
* Stream large CSVs; never load the full MGD or Kaggle charts file into RAM.
* Preserve raw artifacts and null metrics; imports must be idempotent.
* Never perform credential bypass, CAPTCHA bypass, paywall bypass, or private endpoint replay.
* Never create commits automatically; the human decides when to commit.

---

### Task 1: Source-agnostic inventory contracts

**Files:**
- Create: `src/chart_observatory/sources/models.py`
- Create: `src/chart_observatory/sources/manifest.py`
- Create: `src/chart_observatory/sources/__init__.py`
- Test: `tests/unit/sources/test_models.py`

**Interfaces:**
- `SourceObservation`, `SourceManifest`, `MarketCapability`, `SourceStatus`.
- `observation_key()` and `canonical_equivalence_key()` return deterministic tuples.

- [ ] Write tests proving provider/platform separation, null metric preservation, and conflict-key distinction.
- [ ] Implement frozen dataclasses and checksum/coverage helpers.
- [ ] Run `pytest tests/unit/sources/test_models.py -q`.

### Task 2: MGD inspection and streaming import

**Files:**
- Create: `src/chart_observatory/sources/mgd.py`
- Create: `tests/unit/sources/test_mgd.py`
- Create: `tests/fixtures/mgd/spotify_charts_regional_br.csv`
- Modify: `src/chart_observatory/cli.py`

**Interfaces:**
- `MGDSource.inspect() -> SourceManifest`.
- `MGDSource.iter_observations(...) -> Iterator[SourceObservation]`.
- `MGDSource.import_to(path) -> ImportSummary`.

- [ ] Test schema detection, market discovery, row streaming, and idempotent checksum import with a small fixture.
- [ ] Implement recursive file discovery while ignoring notebook checkpoints, SHA-256 manifests, Polars chunk scans, and Top 200 chart mapping.
- [ ] Generate `research/mgd_source_manifest.json` and CLI commands `sources mgd inspect` and `sources mgd import`.
- [ ] Run fixture tests and a bounded real `inspect` against `./mgd`.

### Task 3: Ranked artist/year corpus and coverage reports

**Files:**
- Create: `src/chart_observatory/sources/reports.py`
- Create: `tests/unit/sources/test_reports.py`
- Modify: `src/chart_observatory/cli.py`

**Interfaces:**
- `write_artist_year_report(observations, output_dir) -> ReportSummary`.
- `write_global_market_coverage(manifests, output_dir) -> Path`.
- `write_overlap_report(left, right, output_dir) -> Path`.

- [ ] Test aggregation by country/year/artist without treating provider IDs as identities.
- [ ] Implement CSV/Markdown outputs containing source count, origin platforms, date bounds, rank statistics, and market coverage.
- [ ] Run on the full MGD corpus with streaming aggregation and write `research/mgd_artist_year_rankings.csv`.

### Task 4: Kaggle Spotify Charts adapter

**Files:**
- Create: `src/chart_observatory/sources/kaggle.py`
- Create: `tests/unit/sources/test_kaggle.py`
- Modify: `src/chart_observatory/cli.py`

**Interfaces:**
- `KaggleSpotifyChartsSource.download() -> Path`.
- `iter_observations(chart="top200"|"viral50")`.
- CLI `sources kaggle download` and `sources kaggle import`.

- [ ] Test schema mapping, chart separation, null viral streams, country discovery, and cache reuse.
- [ ] Implement optional `kagglehub` download, checksum/manifest, chunked Polars reading, and explicit missing-package status.
- [ ] Generate MGD×Kaggle overlap when both corpora are present.

### Task 5: Chartmetric authenticated adapter

**Files:**
- Create: `src/chart_observatory/sources/chartmetric.py`
- Create: `tests/unit/sources/test_chartmetric.py`
- Modify: `src/chart_observatory/config.py`, `src/chart_observatory/cli.py`

**Interfaces:**
- `ChartmetricClient.access_token()` with cached refresh.
- `discover_capabilities()` and `collect_chart(...)` with injected transport.

- [ ] Test token exchange/cache, one-time 401 refresh, 429/5xx retry, pagination, and resumable checkpoints.
- [ ] Implement redacted logging, timeout handling, rate-limit headers, and explicit 403/404/unsupported statuses.
- [ ] Add `sources chartmetric auth-test`, `discover`, and `collect` commands without broad collection by default.

### Task 6: YouTube and Pro-Música discovery adapters

**Files:**
- Create: `src/chart_observatory/sources/promusica.py`
- Modify: `src/chart_observatory/adapters/youtube_data/categories.py`, `src/chart_observatory/adapters/youtube_data/most_popular.py`, `src/chart_observatory/cli.py`
- Test: `tests/unit/sources/test_promusica.py`, `tests/contract/youtube_data/test_market_discovery.py`

- [ ] Test official YouTube region discovery and the Pro-Música invalid date configuration review.
- [ ] Implement Pro-Música domain-restricted inventory/download/parser seams and preserve raw artifact metadata.
- [ ] Expose `sources youtube discover` and `sources promusica discover`.

### Task 7: Database/UI integration and documentation

**Files:**
- Create: `migrations/versions/0009_source_inventory.py`
- Create: `src/chart_observatory/db/models/sources.py`
- Modify: `src/chart_observatory/db/models/__init__.py`, `src/chart_observatory/ui/app.py`, `src/chart_observatory/ui/pages/coverage.py`
- Create: `research/source_inventory.md`, `research/provider_capabilities.md`, `research/ingestion_acceptance_report.md`

- [ ] Test source/provider/platform rows and coverage query behavior against the existing PostgreSQL fixture.
- [ ] Add source status/capability/coverage persistence and Streamlit Data Sources/Global Coverage views.
- [ ] Document all real blocks, source windows, markets, overlap, and unresolved Pro-Música date range.

### Task 8: Verification and acceptance

**Files:**
- Modify: `research/methodology.md`, `research/data_dictionary.md`, `research/limitations.md`

- [ ] Run `pytest -m "not live"`, Ruff, mypy, and Alembic migration checks.
- [ ] Run controlled smoke tests for MGD, Kaggle if cached, Chartmetric auth/discovery, YouTube one region, and Pro-Música one public document.
- [ ] Refresh `graphify-out/` with `graphify update .` when the command is available.
- [ ] Report files, migrations, commands, working/partial providers, row counts, coverage, conflicts, tests, and real pending work; do not commit.
