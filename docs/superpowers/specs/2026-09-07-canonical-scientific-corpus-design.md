# Canonical Scientific Music Corpus — Design Specification

**Status:** Approved for implementation
**Date:** 2026-09-07
**Scope:** operational PostgreSQL corpus, frozen Corpus v1, comparable/balanced panels, and article-ready analytical datasets

## Goal

Turn the already-ingested chart observations into a reproducible, canonical,
cross-market corpus. The system must preserve source observations, resolve
recordings across markets and providers, distinguish chart-market geography from
track language, expose coverage eligibility, freeze a versioned Corpus v1, and
materialize datasets for RQ1–RQ5.

## Scientific defaults

- The longitudinal primary corpus is the observed MGD Spotify-origin window;
  the exact bounds are derived from the data and recorded in the freeze manifest.
- Contemporary Pro-Música/Chartmetric observations are validation material only
  unless their coverage profile independently passes the same eligibility rules.
- Comparable-cell defaults are configuration, not code: coverage ratio >= 0.95,
  at least 3 observed years, and median chart depth >= 100.
- Prevalence counts distinct canonical tracks once per country/period stratum;
  exposure weights chart appearances by observation/rank and never substitutes for
  prevalence.
- Unresolved tracks remain in denominators and are reported explicitly; they do
  not enter resolved-track numerators.
- A chart entry is not duplicated merely because multiple sources report it.
  Reconciliation is additive, precedence is explicit, and disagreement emits a
  SOURCE_CONFLICT record.

## Architecture

`ResearchApplication` owns a PostgreSQL session factory and composes repositories
for artifacts, tracks, charts, reconciliation, corpus selection, and exports.
CLI, API, and UI receive the same application object. Existing immutable source
snapshots and chart entries remain the raw observation boundary. New canonical
tables are derived and versioned, so re-running reconciliation or analysis never
mutates source records.

The frozen layer is a manifest plus membership tables. A Corpus v1 freeze records
the exact source snapshot IDs, rules, software revision, date bounds, eligible
chart cells, and SHA-256 hashes of every analytical artifact. A balanced panel is
derived from comparable cells using a common intersection of periods rather than
silently imputing missing charts.

## Data model additions

- `market_geography`: ISO alpha-2/alpha-3, UN M49, region, subregion, and
  intermediate region, with source/version metadata.
- `chart_cell_profiles`: provider/platform/market/chart-family coverage metrics:
  first/last date, expected/observed periods, ratio, longest gap, track count,
  and median depth.
- `corpus_versions` and `corpus_memberships`: immutable freeze metadata and
  eligible/balanced membership.
- `canonical_chart_entries` and `source_conflicts`: one deduplicated analytical
  observation with source IDs, chosen precedence, conflict status, and retained
  alternatives.
- `genre_taxonomy` and `genre_claims`: normalized genre, original label, source,
  source version, confidence, and review status.
- `track_languages`: one or more language claims per canonical track with source,
  confidence, and multilingual support.
- `lyric_documents` and `semantic_annotations`: rights/provenance-aware lyric
  corpus records and category-level annotations with model/version metadata.
- `analysis_runs`: existing provenance table extended through export manifests;
  each dataset is reproducible from frozen inputs.

## Analytical contracts

The export layer provides these datasets:

- `category_prevalence_by_country` and `category_exposure_by_country`, each with
  counts, denominators, estimates, and confidence intervals.
- `rq2_content_country` for content ~ country.
- `rq3_content_country_genre` for content ~ country + genre + year + language +
  rank + country × genre.
- `rq4_content_success` for peak rank, chart days, Top-10 days, and streams.
- `turnover_by_market_period` with new entries, exits, retained tracks, Jaccard,
  turnover rate, and mean rank displacement.
- `survival_by_track` and `survival_model_summary` for chart-entry-to-exit
  duration, Kaplan–Meier estimates, and Cox proportional-hazards results.
- `genre_diversity_by_market_period` and `genre_distance` with Shannon, Simpson,
  HHI, and Jensen–Shannon divergence.
- `coverage_eligibility`, `balanced_panel`, `track_master`,
  `chart_observations`, and `cross_platform_presence`.

Model runners use statsmodels for regression/mixed effects and lifelines for
survival analysis. If a model cannot be fit because a dataset is empty, singular,
or lacks an outcome, the run is recorded as `INSUFFICIENT_DATA` with the exact
reason; no fabricated estimate is emitted.

## Source policy

MGD is imported from the local corpus in streaming mode. Kaggle is optional and
is used for validation/gap detection when its artifact is present or can be
downloaded through the configured adapter. Pro-Música and Chartmetric use the
existing explicit network opt-in and preserve raw artifacts. YouTube
`mostPopular` remains a video/viral dataset and is never merged into Spotify
Top-200 chart observations. Apple Music code, tests, configuration, and project
references are removed because it is outside the study design.

## Testing and acceptance

Every new public seam gets a red-green test first. Unit tests cover aggregation,
eligibility, reconciliation, taxonomy normalization, and statistical formulas.
SQLite-backed integration tests cover repository behavior; PostgreSQL migration
and operational tests run when the local service is available. Full acceptance
includes the non-live test suite, Ruff, mypy, Alembic upgrade, a bounded MGD
import, corpus freeze, and dataset hash verification.

