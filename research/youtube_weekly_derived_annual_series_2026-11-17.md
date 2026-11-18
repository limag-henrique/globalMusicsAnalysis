# YouTube Weekly Top Songs: Derived Annual Series Audit

**Research date:** 2026-11-17  
**Scope:** provenance and method for the additive YouTube annual view-sum series proposed for the 150k music-ranking project.

## Source and provenance

Zenodo record [10.5281/zenodo.23645386, version 1.0.1](https://zenodo.org/records/23645386) deposits weekly YouTube Top Songs charts for 43 country markets and the global chart. Its README says the YouTube chart data were retrieved from `charts.youtube.com` in October 2026 and that the year-partitioned `youtube_top100_positions_YYYY.csv.gz` files preserve chart market, Thursday `week_end`, weekly rank, weekly views, a native `key`, title, credited artists, and related fields. The README describes `key` as a YouTube video identifier. The dataset and documentation are released under CC BY 4.0; the record cautions that the listings reproduce platform rankings and that the platform's terms still apply to redistribution.

YouTube's [official Charts & Insights description](https://support.google.com/youtube/answer/9014376?hl=en) describes Weekly Top Songs as view-based and says it combines views across official music videos, user-made videos using the official song, and lyric videos. This is distinct from YouTube's Shorts chart, which is based on Shorts creations.

## Project derivation and limits

The project reproduced 15 complete market-year cells from the archive: BE 2023, BR 2023, CH 2023, DK 2023, ES 2024, FI 2024, FR 2020, FR 2022, IT 2022, IT 2024, MX 2024, NG 2025, NL 2019, NL 2023, and PL 2024. Each cell covers all 52 Thursday chart weeks for its calendar year, except FR 2020, which covers 53. Weekly views were summed by the archive's native `key`; rows were ordered by descending sum, then the project's normalized title, artist credit, and native ID tie-break. The resulting 500 ranked rows per cell reproduce the existing `new_market_rankings.parquet` entries exactly.

These 7,500 positions are **project-derived annual view-sum rankings**, not annual charts published by YouTube. The 500-row cutoff is a project candidate limit, not a reported YouTube annual chart depth; retain `reported_depth` as unknown. The archive's `key` is video-level, so this procedure preserves native IDs and does not claim that separate IDs have been resolved to canonical recordings or songs.

The source has incomplete artist text for one top-500 entry in each of FR 2022, IT 2022, MX 2024, and NG 2025. Those artist credits remain blank in the derived rows; no artist name is inferred. Two weekly charts in the selected cells contain 101 archived rows (BE 2023 and DK 2023); all rows are retained in the view sums. No repeated nonblank native IDs were found within the selected market-week charts.

The source's weekly rank field also has ties and gaps: 48 of the 781 selected market-week charts contain repeated rank values, and 45 have missing rank values in the recorded sequence. Those weekly rank labels do not enter the annual calculation; all chart rows remain included and the annual ranking is based on the archived view counts.

These rankings are stored as separate provider-tagged series and must not be merged into Spotify ranks or counted toward the 150,000-position core selection. YouTube’s [Terms of Service](https://www.youtube.com/t/terms?hl=en) identify Google LLC, operating under Delaware law and located in California, as the service provider; the publisher jurisdiction is therefore distinct from the chart market.

## Local evidence

- [Zenodo source capture manifest](../data/raw/zenodo-23645386-youtube-audit-20261117/capture-manifest-annual-series-20261117-v2.json) records the six downloaded year files (2019, 2020, 2022–2025) and their Zenodo-posted MD5 matches plus local SHA-256 values.
- [Zenodo README snapshot](../data/raw/zenodo-23645386-youtube-audit-20261117/README.md) documents the fields, collection method, and license.
- [Existing annual ranking artifact](../data/derived/annual_revision/global-rescan-2018-2026-20261111/new_market_rankings.parquet) is the comparison source for the reproduced 500-row rankings.

**Decision:** Keep the series additive, label the annual ranks as derived, leave the publisher-reported depth unknown, and keep these ranks outside the Spotify/YouTube core quota.
