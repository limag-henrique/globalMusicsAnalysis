# Source inventory — global-first extraction

Generated on 2026-09-07. The machine-readable files in this directory are the
authoritative inventory outputs; this page explains their scope and status.

| Provider | Origin platform | Status | Coverage currently materialized |
| --- | --- | --- | --- |
| `MGD` | `SPOTIFY` | Imported | 69 local CSV files, 68 markets including `GLOBAL`, 21,257,472 observations, `Top 200`, 2017-01-01 to 2022-03-13 |
| `CHARTMETRIC` | `SPOTIFY` | Capability discovered; historical collection not run | 73 accessible capabilities/markets in the current credential smoke test; 77 capability records including four non-available platform probes |
| `YOUTUBE_DATA_API` | `YOUTUBE_VIDEO` | Region/category discovery completed | 111 official regions; 14 assignable video categories inspected for `BR` |
| `PRO_MUSICA_BRASIL` | `MULTI_PLATFORM_AGGREGATE` | Current public chart imported | Official `TOP_50_STREAMING`, `BR`, 50 rows for the page's displayed period 2026-08 |
| `KAGGLE_DHRUVILDAVE` | `SPOTIFY` | Pending local dependency/data acquisition | Dataset adapter and schema contract exist; no download was silently assumed and no overlap estimate is reported yet |

## Main outputs

- [MGD source manifest](mgd_source_manifest.json) — checksums, file sizes, dates, markets and row counts.
- [MGD normalized observations](../data/normalized/mgd_observations.parquet) — source observations with provenance columns.
- [MGD artist/year rankings](mgd_artist_year_rankings.csv) — 187,728 source-preserving rows covering each market's latest five observed years.
- [Top artists by country/year](top_artists_by_country_latest5.csv) — top 25 artists within each available MGD market/year/chart, 8,200 rows.
- [Market capabilities](market_capabilities.csv) — merged dynamic inventory across all discovered providers.
- [Global coverage table](global_market_coverage.csv) — date coverage of the imported MGD files.
- [Pro-Música current Top 50](promusica_top50_current.csv) — raw-derived Brazilian validation sample.

The ranking report is deliberately not a final probabilistic dataset. It keeps
`provider` and `origin_platform` separate, preserves each provider observation,
and does not count MGD/Kaggle/Chartmetric equivalents as one event until an
explicit canonicalization/precedence decision is applied.
