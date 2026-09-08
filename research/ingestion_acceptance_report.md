# Ingestion acceptance report

## Accepted

- Milestone 1D source-rights activation was approved by the project owner. Technical
  availability and credential state remain recorded independently per source.

- MGD discovery found 69 files and automatically imported all non-empty markets.
- MGD normalized Parquet import wrote 21,257,472 rows with no skipped rows.
- MGD artist/year aggregation produced 187,728 rows for the latest five observed years per market, currently 2018–2022 in the report.
- MGD top-artist extraction produced 8,200 rows: up to 25 ranked artists per market/year/chart across 68 markets and five observed years.
- Chartmetric authentication succeeded and Spotify market capability discovery returned 77 records, of which 73 are available.
- A bounded Chartmetric smoke collection succeeded for Spotify/BR (`2025-04-23`, one row, `type=plays`) using the configured `.env` refresh token; the temporary artifact was not added to the corpus.
- YouTube official region discovery returned 111 regions; Brazil category discovery returned 14 assignable categories.
- Pro-Música official Top 50 HTML produced 50 rows, retaining `PRO_MUSICA_BRASIL` as provider and `MULTI_PLATFORM_AGGREGATE` as origin platform.
- All source unit/contract tests pass together with the pre-existing test suite: 120 passed.
- Chartmetric `auth-test`, `discover`, `dates`, and `collect` require an explicit
  `--allow-network` opt-in; without it, no HTTP transport is constructed even
  when a refresh token is configured.

## Deliberately incomplete

- Chartmetric historical chart collection was not run in bulk; only authentication and bounded capability/smoke discovery were performed.
- YouTube historical chart extraction was not inferred from current `mostPopular`; the adapter records the semantic boundary explicitly.
- Kaggle download/import and MGD × Kaggle overlap remain pending a local data acquisition dependency.
- Canonical-track resolution and source precedence are modeled at the observation boundary but require a reviewable production mapping before cross-source probability calculations.
