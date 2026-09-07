# Ingestion acceptance report

## Accepted

- MGD discovery found 69 files and automatically imported all non-empty markets.
- MGD normalized Parquet import wrote 21,257,472 rows with no skipped rows.
- MGD artist/year aggregation produced 187,728 rows for the latest five observed years per market, currently 2018–2022 in the report.
- MGD top-artist extraction produced 8,200 rows: up to 25 ranked artists per market/year/chart across 68 markets and five observed years.
- Chartmetric authentication succeeded and Spotify market capability discovery returned 77 records, of which 73 are available.
- YouTube official region discovery returned 111 regions; Brazil category discovery returned 14 assignable categories.
- Pro-Música official Top 50 HTML produced 50 rows, retaining `PRO_MUSICA_BRASIL` as provider and `MULTI_PLATFORM_AGGREGATE` as origin platform.
- All source unit/contract tests pass together with the pre-existing test suite: 116 passed.
- Chartmetric `auth-test` and `discover` now require an explicit `--allow-network` opt-in;
  without it, no HTTP transport is constructed even when a refresh token is configured.

## Deliberately incomplete

- Chartmetric historical chart collection was not run in bulk; only authentication and bounded capability/smoke discovery were performed.
- YouTube historical chart extraction was not inferred from current `mostPopular`; the adapter records the semantic boundary explicitly.
- Kaggle download/import and MGD × Kaggle overlap remain pending a local data acquisition dependency.
- Canonical-track resolution and source precedence are modeled at the observation boundary but require a reviewable production mapping before cross-source probability calculations.
