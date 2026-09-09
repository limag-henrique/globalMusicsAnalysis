# Source inventory — global-first extraction

Generated on 2026-09-08. The machine-readable files in this directory are the
authoritative inventory outputs; this page explains their scope and status.

Milestone 1D rights activation was approved by the project owner and is recorded in
`milestone_1d_activation_record.md`. “Approved” means the source may be used through
its configured rights profile; it does not turn an unavailable endpoint or missing
credential into observed coverage.

| Provider | Origin platform | Status | Coverage currently materialized |
| --- | --- | --- | --- |
| `MGD` | `SPOTIFY` | Imported | 69 local CSV files, 68 markets including `GLOBAL`, 21,257,472 observations, `Top 200`, 2017-01-01 to 2022-03-13 |
| `CHARTMETRIC` | `SPOTIFY` | Capability discovered; historical collection not materialized | 73 accessible capabilities/markets in the current credential smoke test; no local observation artifact is claimed |
| `YOUTUBE_DATA_API` | `YOUTUBE_VIDEO` | Region/category discovery completed | 111 official regions; 14 assignable video categories inspected for `BR` |
| `PRO_MUSICA_BRASIL` | `MULTI_PLATFORM_AGGREGATE` | Current public chart imported | Official `TOP_50_STREAMING`, `BR`, 50 rows for the page's displayed period 2026-08 |
| `KAGGLE_DHRUVILDAVE` | `SPOTIFY` | Imported | 70 regions, `top200` and `viral50`, 26,173,514 observations, 2017-01-01 to 2021-12-31 |

The PostgreSQL migration `0009_source_inventory` persists these manifests together
with per-market capabilities and native-period coverage claims. The repository keeps
provider and origin platform as independent query fields and deduplicates repeated
imports by artifact SHA-256.

## Main outputs

- [MGD source manifest](mgd_source_manifest.json) — checksums, file sizes, dates, markets and row counts.
- [MGD normalized observations](../data/normalized/mgd_observations.parquet) — source observations with provenance columns.
- [MGD artist/year rankings](mgd_artist_year_rankings.csv) — 187,728 source-preserving rows covering each market's latest five observed years.
- [Top artists by country/year](top_artists_by_country_latest5.csv) — top 25 artists within each available MGD market/year/chart, 8,200 rows.
- [Market capabilities](market_capabilities.csv) — merged dynamic inventory across all discovered providers.
- [Global coverage table](global_market_coverage.csv) — date coverage of the imported MGD files.
- [Pro-Música current Top 50](promusica_top50_current.csv) — raw-derived Brazilian validation sample.
- [Unified source catalog](../data/normalized/source_catalog.parquet) — 47,434,073
  source-preserving rows from the locally available MGD, Kaggle, YouTube and
  Pro-Música artifacts. It is queryable with `corpus catalog` and keeps videos
  separate from track charts.
- [Article analytics manifest](../data/derived/article/manifest.json) — hashes,
  parameters and row counts for the reproducible persistence, market-anxiety,
  genre-variation and genre-distance outputs.

## Unified catalog contract

The catalog is an analytical union, not an unverified deduplication. Every row
retains `provider`, `origin_platform`, `source_artifact`, `source_row_number`,
`native_id`, source metrics and its original chart semantics. `canonical_track_id`
and `resolution_status` remain unresolved until an explicit identity-resolution
step is run. YouTube rows are `item_kind=VIDEO` and carry
`semantic_equivalence=NOT_YOUTUBE_MUSIC_TOP_SONGS`; they must not be interpreted
as YouTube Music Top Songs.

Example queries:

```text
python -m chart_observatory.cli corpus catalog --country BR --year 2021 --limit 200
python -m chart_observatory.cli corpus catalog --provider KAGGLE_DHRUVILDAVE --chart-family VIRAL_50
python -m chart_observatory.cli corpus catalog --output data/normalized/source_catalog.parquet
```

The ranking report is deliberately not a final probabilistic dataset. It keeps
`provider` and `origin_platform` separate, preserves each provider observation,
and does not count MGD/Kaggle/Chartmetric equivalents as one event until an
explicit canonicalization/precedence decision is applied.
