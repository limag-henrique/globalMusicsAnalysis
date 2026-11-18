# YouTube 2021 weekly chart archive: duplicate native-key conflicts

**Audit date:** 2026-11-17  
**Scope:** Verify whether the archived YouTube Top Songs weekly rows for 2021 support the same annual view-sum derivation used for clean full-year market cells. The 2021 source bytes were captured, but conflicting weekly observations prevent an unqualified annual ranking.

## Provenance and captured bytes

The [Zenodo dataset record](https://zenodo.org/records/23645386), DOI [10.5281/zenodo.23645386](https://doi.org/10.5281/zenodo.23645386), publishes version 1.0.1 and lists [`youtube_top100_positions_2021.csv.gz`](https://zenodo.org/records/23645386/files/youtube_top100_positions_2021.csv.gz?download=1) as 8,167,549 bytes with MD5 `4da53365358afa2b65a921e9e01f85c5`. The local file matches that byte count and MD5; local SHA-256 is `503ebb8ae1112d5e83915ba83605cc53d3edfafcf9edfdcb0900cae6eff3e3e4`. Capture time, request endpoint, and checksums are recorded in the [capture manifest](../data/raw/zenodo-23645386-youtube-audit-20261117/capture-manifest-2021-2026-20261117-v1.json).

The Zenodo README says the weekly YouTube charts were retrieved from `charts.youtube.com` in October 2026 and that `youtube_top100_positions_YYYY.csv.gz` preserves weekly market, week ending, rank, views, native key, title, and artists. It also describes repeated chart keys and other source anomalies. YouTube describes Weekly Top Songs as view-based ([official Charts & Insights description](https://support.google.com/youtube/answer/9014376?hl=en)). The derived annual view-sum is a project calculation, not a YouTube-published year-end chart; retain it as separate provider data if a cell can be reconstructed without unresolved metric conflicts.

## 2021 coverage and conflict audit

The captured 2021 file contains 44 chart codes (43 country markets plus `GLOBAL`) and 2,288 market-weeks. Every code has all 52 Thursdays from 2021-01-07 through 2021-12-30. However, there are **420 repeated native-key/week groups**. Every repeated group carries different `views` values across its duplicate rows; one group also has different title and artist metadata. The project source-coverage ledger correspondingly marks every 2021 market as `CONFLICT_OR_INVALID`.

A view-sum keyed by the repeated native ID cannot choose which conflicting weekly view count to use without more first-party evidence or an explicit, justified correction rule. Summing both rows would double-count the same key; selecting the larger, smaller, or first value would introduce an unsupported policy. Therefore this capture is retained as source evidence, but no 2021 annual ranking positions were derived or imported. Keep the 2021 cells open pending primary-source resolution.

## Local artifacts and decision

- Raw weekly source: [`youtube_top100_positions_2021.csv.gz`](../data/raw/zenodo-23645386-youtube-audit-20261117/youtube_top100_positions_2021.csv.gz)
- Capture metadata and hashes: [`capture-manifest-2021-2026-20261117-v1.json`](../data/raw/zenodo-23645386-youtube-audit-20261117/capture-manifest-2021-2026-20261117-v1.json)
- Source-coverage reconciliation: [`source_coverage.json`](../data/derived/annual_revision/global-rescan-2018-2026-20261111/source_coverage.json)

**Decision:** Do not derive or import 2021 view-sum ranks from this packet until the 420 repeated-key view conflicts are resolved. Preserve all source rows and rank anomalies; do not infer missing or corrected counts. This restriction applies to the derived YouTube series and does not reclassify any separate national-publisher chart series.
