# TopHit Russia Top All Internet Hits Annual Chart 2025 — source review

## Finding

TopHit’s archived first-party page identifies a **Top All Internet Hits Russia Annual Chart** for calendar year 2025. The page payload declares the chart filter as `variant=top`, `category=internet`, `type=hits`, `region=ru`, `period=annual`, and `periodStart=2025`. It reports 200 positions, numbered continuously from 1 through 200, with a publisher depth of 200 on every row.

The positions are imported as the separate `TOPHIT_TOP_ALL_INTERNET_HITS_RU_2025` provider series (market RU, year 2025). This is a distinct ranking and denominator from TopHit’s 2025 radio chart and from the project’s Spotify/YouTube core. It does not change the 150,000-position core selection.

## Primary source and capture

- Official chart page: <https://tophit.com/chart/top/internet/hits/ru/annual/2025>
- Wayback replay captured 2026-01-06 18:44:55 UTC: <https://web.archive.org/web/20260106184455/https://tophit.com/chart/top/internet/hits/ru/annual/2025>
- Raw archived HTML saved at [`data/raw/national_charts/tophit_ru_annual_2025/tophit-top-all-internet-hits-russia-annual-2025-archive-20260106.html`](../data/raw/national_charts/tophit_ru_annual_2025/tophit-top-all-internet-hits-russia-annual-2025-archive-20260106.html)
- Raw HTML SHA-256: `b93bfcc57c8cc373f50b2fe94132f8124d66d493dcbed50c62828c829dc0eaaf`
- Retrieval check on 2026-11-17: live page returned HTTP 403; archived page returned HTTP 200.

The saved page contains the Next.js server payload. That payload was Base64-decoded and zlib-decompressed; no ranks or counts were calculated from other charts. The payload identifies the series title and market itself. Individual rows carry the annual dates 2025-01-01 through 2025-12-31 and the reported position.

## Coverage and validation

- 200 rows; positions 1–200 complete and unique.
- Publisher-reported depth is 200; no ties or gaps were found in the captured sequence.
- All 200 TopHit track IDs and row IDs are present and unique; each row’s `itemId` matches its track ID.
- One source artist-credit anomaly: rank 178 (`Теряют Люди Друг Друга`) has an empty `artists` array. Its credit remains blank; no artist was inferred.
- TopHit reports `airs`, `youtubeViews`, and `spotifyStreams` on every row. Each value is nonnegative, and the repeated values in the nested `track.statSummary` agree with the row-level metric fields. Zero values are retained.
- The captured page does not disclose a weighting formula for the published positions. The packet therefore preserves the publisher’s ranks and all three reported metrics separately; it does not synthesize a composite score.

## Provider and market attribution

The chart filter identifies RU as the chart market. The chart page does not state the publisher’s legal jurisdiction. The packet uses UA as a qualified inference because the matching legal entity TOV TOPHIT (EDRPOU 42089400) is registered in Ukraine and names Igor Kraev as director; matching that entity to the TopHit chart publisher is inferred from its name and the chart branding. Registry reference: <https://opendatabot.ua/c/42089400>. The chart market remains RU independently of that inference.

## Packet and catalog

- Packet: [`data/derived/annual_revision/provider_series/tophit-russia-top-all-internet-hits-annual-2025/`](../data/derived/annual_revision/provider_series/tophit-russia-top-all-internet-hits-annual-2025/)
- Rankings SHA-256: `1a157e68c89bb284b5c8a39b5967e1ffaa1c7c62e776446586cf6397a0c9e322`
- Versioned provider index v26: [`provider-series-index-20261117-26.json`](../data/derived/annual_revision/provider_series/provider-series-index-20261117-26.json)
- v26 supplemental catalog: 322 provider series and 37,078 ranked position memberships. Both TopHit series remain separately denominated at 200 positions each.

