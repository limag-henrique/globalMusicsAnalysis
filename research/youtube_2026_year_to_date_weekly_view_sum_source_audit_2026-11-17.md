# YouTube 2026 year-to-date weekly Top Songs coverage

**Audit date:** 2026-11-17  
**Question:** Can the archived 2026 YouTube weekly charts support a project-derived ranking through the source cutoff, and how should it be represented?

## First-party chart method and archive provenance

YouTube describes Weekly Top Songs as a weekly chart based on total views for each song's official versions, combining the official music video, user-made videos that use the official song, and lyric videos ([YouTube Charts & Insights](https://support.google.com/youtube/answer/9014376?hl=en), “Weekly Top Songs”). This supports using the archived weekly `views` field as the input metric for a project calculation; YouTube does not describe that calculation as its own annual chart.

The [Zenodo record 10.5281/zenodo.23645386](https://zenodo.org/records/23645386) identifies version 1.0.1, published 2026-10-25. Its description says the deposit contains weekly YouTube Top 100 charts for 43 country markets plus the global chart, covering 442 weeks through 2026-10-15, and identifies YouTube Charts as the source, retrieved in October 2026. The record lists [`youtube_top100_positions_2026.csv.gz`](https://zenodo.org/records/23645386/files/youtube_top100_positions_2026.csv.gz?download=1) with Zenodo MD5 `24a08b2096a445dece92eda5235a52a3` and a listed size of 6,685,059 bytes. The dataset is released under CC BY 4.0; the record says the chart listings reproduce platform rankings and that platform terms apply to redistribution.

The [Zenodo README snapshot](../data/raw/zenodo-23645386-youtube-audit-20261117/README.md) documents the year-partitioned CSV fields, including market code, Thursday `week_end`, published weekly `rank`, `views`, native key, title, and credited artists. It also describes known duplicate-key, tied-rank, and missing-rank records. Those weekly source properties must remain visible in the audit; they are not annual ties or annual chart gaps.

## Project coverage ledger

The project's current [`source_coverage.json`](../data/derived/annual_revision/global-rescan-2018-2026-20261111/source_coverage.json) labels eight 2026 YouTube market cells complete for all 42 expected Thursdays from 2026-01-01 through 2026-10-15, with zero invalid items, conflicting items, or duplicate observations:

| Market | Weeks | Observed range |
|---|---:|---|
| AR | 42/42 | 2026-01-01–2026-10-15 |
| CA | 42/42 | 2026-01-01–2026-10-15 |
| CL | 42/42 | 2026-01-01–2026-10-15 |
| FI | 42/42 | 2026-01-01–2026-10-15 |
| GB | 42/42 | 2026-01-01–2026-10-15 |
| IT | 42/42 | 2026-01-01–2026-10-15 |
| NZ | 42/42 | 2026-01-01–2026-10-15 |
| US | 42/42 | 2026-01-01–2026-10-15 |

This is the project's coverage-ledger result, not an independent re-parse of the 2026 CSV. At audit time, `youtube_top100_positions_2026.csv.gz` was not present in the local Zenodo capture directory. Capture the raw asset and verify its checksum before building ranked rows; then rerun coverage against those exact bytes.

## Representation decision

If the captured file reproduces the coverage ledger, the eight cells can support **year-to-date derived view-sum series through 2026-10-15**. For each market, sum weekly `views` by the dataset's native key across the 42 observed weeks and apply the project's deterministic ordering rule. Preserve all source IDs and blank source credits. A 500-entry output cap is a project limit, not a publisher-reported chart depth, so keep `reported_depth` unknown.

These ranks would be an **as-of year-to-date derivation**, not a completed 2026 annual ranking and not a YouTube-published year-end chart. Record the observed period as 2026-01-01 through 2026-10-15, label the series provisional/YTD, and keep it separate from the Spotify/YouTube core ranks. Do not fill the remaining 2026 weeks or call the derived order a final annual order. The project's existing [complete-year YouTube derivation audit](youtube_weekly_derived_annual_series_2026-11-17.md) documents the parallel series policy and reproducibility requirements.

## Next acquisition step

Capture the official Zenodo 2026 file with HTTP retrieval metadata, its published MD5, local SHA-256, and retrieval time. Reconcile the eight market/week sets and duplicate checks against the local coverage ledger before creating a packet. No 2026 rank packet was created in this source audit.


## Follow-up capture and direct CSV validation (2026-11-17)

The 2026 raw asset was subsequently captured by ordinary HTTPS from the Zenodo record API. Its 6,685,059 bytes and MD5 `24a08b2096a445dece92eda5235a52a3` match the record metadata; local SHA-256 is `6d4d9ee2e06661d367bb7c696157f42efe656130a6e008ec5c5270216f84f4ca`. The capture time, request URL, record-listed checksum, and local hashes are recorded in [`capture-manifest-2021-2026-20261117-v1.json`](../data/raw/zenodo-23645386-youtube-audit-20261117/capture-manifest-2021-2026-20261117-v1.json).

I re-parsed the captured CSV for AR, CA, CL, FI, GB, IT, NZ, and US. Each market has the exact 42 Thursday dates from 2026-01-01 through 2026-10-15, 100 source rows in every week, no repeated native keys, no empty/`T:` keys, and no invalid rank/view values. Weekly published-rank anomalies remain in CA (2 weeks), CL (3), FI (12), GB (1), and NZ (11); those rank labels do not enter the view-sum derivation and should be recorded in the packet audit. The eight cells yield more than 500 distinct native keys each. These checks establish clean observed-period inputs; they do not turn the YTD results into full-year annual charts.

At this follow-up, the raw source has been captured and directly checked, but no 2026 YTD ranking packet has yet been created or imported. The next step is a separate, explicitly provisional YTD series, with period bounds 2026-01-01 to 2026-10-15, reported depth unknown, and no rows merged into the 150,000-position core.

## Packet build and supplemental import (2026-11-17)

The independently checked source rows were converted into [`youtube-weekly-derived-ytd-20261117-01`](../data/derived/annual_revision/provider_series/youtube-weekly-derived-ytd-20261117-01/manifest.json). It contains eight separate YOUTUBE series (AR, CA, CL, FI, GB, IT, NZ, US), 500 derived positions per market, and an unknown publisher-reported depth. The rankings file SHA-256 is `cd5d7ae0ec934e849a39d93aa96a534efcd6b5db9290cb75038d6d6e608c6b01`; the packet manifest records the derivation, period, weekly rank anomalies, preserved blank credits, capture hashes, and selection policy.

The packet was appended after all 323 ranked packets in the v37 order. The resulting v38 supplemental catalog contains 356 series and 43,498 memberships, an additive change of 8 series and 4,000 positions. All v37 series, membership, and song records remain present and unchanged; the new SQLite catalog reports `integrity_check = ok` and no foreign-key violations. Its denominator report explicitly records that supplemental series are not merged into the core. At this checkpoint the active provider-series index was v38, with `core_selection_changed=false`. The versioned database, denominator report, index, import output, and exact packet order are preserved in the [v38 snapshot](../data/runtime/supplemental-provider-snapshot-history-20261117-v38/snapshot-manifest.json). A later additive v39 snapshot appends the separate NetEase 2020 new-song series; the eight YouTube YTD series remain in v39 unchanged ([current snapshot](../data/runtime/supplemental-provider-snapshot-history-20261117-v39/snapshot-manifest.json)).

These are project-derived year-to-date positions through 2026-10-15, not completed annual charts. Weekly rank anomalies remain source audit metadata and do not become annual rank ties or gaps. The 2021 weekly file was also captured for conflict inspection, but its conflicting repeated native-key/week view counts prevent a defensible annual view-sum derivation until reconciled.
