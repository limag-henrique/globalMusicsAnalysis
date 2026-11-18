# YouTube 2021 weekly archive: duplicate-key conflict audit

**Audit date:** 2026-11-17  
**Question:** Can the archived 2021 weekly YouTube Top Songs rows support project-derived annual view-sum rankings?

## Captured source

The [Zenodo record 10.5281/zenodo.23645386](https://zenodo.org/records/23645386) contains the 2021 weekly archive `youtube_top100_positions_2021.csv.gz`. Its record metadata lists 8,167,549 bytes and MD5 `4da53365358afa2b65a921e9e01f85c5`. The captured local file is [preserved here](../data/raw/zenodo-23645386-youtube-audit-20261117/youtube_top100_positions_2021.csv.gz); SHA-256 is `503ebb8ae1112d5e83915ba83605cc53d3edfafcf9edfdcb0900cae6eff3e3e4`. Capture URL, retrieval time, listed and verified checksums are recorded in the [additive capture manifest](../data/raw/zenodo-23645386-youtube-audit-20261117/capture-manifest-additional-years-20261117-v1.json).

## Reparse and blocker

The gzip CSV has 44 chart markets (43 country codes plus `global`) and all 52 weekly dates in 2021 in every market. Repeated `(market, week_end, native key)` groups cannot be safely reduced to one weekly observation:

- 420 repeated key/week groups were found.
- All 420 groups contain differing `views` values.
- One group also varies in title and one group varies in artist credit.

Because an annual view-sum requires a defensible weekly metric per native key, summing every repeated row would double-count some items, while choosing one row, the maximum, or another reduction would invent a rule absent from the archive documentation. No 2021 derived annual positions were created from this file. The raw archive remains available for later reconciliation if an authoritative duplicate-resolution rule is found.

This is a source-integrity blocker, not evidence that YouTube published a particular year-end rank order. No 2021 series or positions were added to either the supplemental provider catalog or the 150,000-position Spotify/YouTube core.
