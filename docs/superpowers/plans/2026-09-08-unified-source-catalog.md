# Unified Source Catalog Implementation Plan

**Goal:** Provide one source-preserving, filterable catalog of every locally available MGD, Kaggle, Chartmetric, Pro-Música, and YouTube observation.

**Architecture:** Normalize each source lazily into the same observation schema, retain provider and platform semantics, and expose the catalog through a bounded CLI export and the Streamlit observations page. Source-specific fields remain columns in the unified artifact; unresolved identity is explicit and no source observation is deleted.

**Tech Stack:** Python 3.12, Polars lazy scans, Typer, Streamlit, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-07-global-multi-source-corpus-design.md` and `docs/superpowers/specs/2026-09-08-research-browser-classification-design.md`

## Global Constraints

- Never use a provider ID as the canonical research identity.
- Always persist `provider` separately from `origin_platform`.
- Preserve all raw source observations and null metrics.
- Keep YouTube video rankings separate from music-track charts.
- Network collection remains explicit, bounded, and rights-aware.
- Do not create git commits or change branches.
- Lyrics remain a future authorized input and are never inferred.

---

### Task 1: Source-preserving lazy catalog contract

**Files:**
- Create: `src/chart_observatory/sources/catalog.py`
- Create: `tests/unit/sources/test_catalog.py`

**Interfaces:**
- `CatalogFilters(provider, origin_platform, country_code, year, chart_name, query, limit)`
- `catalog_source_paths(root) -> tuple[Path, ...]`
- `scan_source_catalog(paths) -> polars.LazyFrame`
- `filter_source_catalog(paths, filters) -> polars.DataFrame`
- `write_source_catalog(paths, output) -> Path`

- [x] Write tests proving MGD/Kaggle/YouTube/Pro-Música schema normalization, ISO country filtering, year filtering, text filtering, bounded results, null metrics, and video semantic separation.
- [x] Run the focused tests and observe the expected import failure.
- [x] Implement lazy source scans, deterministic source ordering, normalized market codes, and source-specific columns.
- [x] Re-run focused tests and then the complete non-live suite.

### Task 2: CLI and export surface

**Files:**
- Modify: `src/chart_observatory/cli.py`
- Modify: `src/chart_observatory/exports/datasets.py`
- Create: `tests/integration/exports/test_source_catalog.py`

- [x] Add `corpus catalog` with provider/platform/country/year/chart/text filters, bounded JSON output, and Parquet/CSV export.
- [x] Add the `source_catalog` dataset schema and verify exported columns and source counts.
- [x] Make the catalog source discovery include the locally imported Kaggle artifact and optional Chartmetric/Pro-Música/YouTube artifacts when present.
- [x] Run CLI help and catalog tests.

### Task 3: Research browser integration

**Files:**
- Modify: `src/chart_observatory/ui/data.py`
- Modify: `src/chart_observatory/ui/pages/observations.py`
- Create: `tests/unit/ui/test_source_catalog_ui.py`

- [x] Replace the MGD-only query with the unified lazy catalog.
- [x] Add provider, platform, year, chart, country, rank, text, and classification filters while retaining a visible result limit.
- [x] Display provider, platform, item kind, period, rank, title, artist, metric, native ID, source artifact, and semantic status.
- [x] Keep classification joins limited to tracks and never classify YouTube videos.
- [x] Run UI helpers and complete tests.

### Task 4: Materialize the available source set and synchronize documentation

**Files:**
- Modify: `research/source_inventory.md`
- Modify: `research/provider_capabilities.md`
- Modify: `research/ingestion_acceptance_report.md`
- Create: `data/normalized/source_catalog.parquet`

- [x] Materialize MGD, Kaggle, current YouTube, and current Pro-Música into the unified artifact; include Chartmetric files automatically if present.
- [x] Record exact counts, date bounds, market counts, chart families, and missing historical sources.
- [x] Preserve the explicit YouTube video boundary and future lyrics status.
- [x] Run Ruff, mypy, pytest, and Graphify update.

No commit is part of this implementation; the human decides whether and when to commit.
