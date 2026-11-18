# Apple Music Israel annual song playlists: source audit for 2018, 2020, and 2021

Audit date: 2026-11-17.

## Findings

Apple Music has a first-party Israel storefront playlist for each requested year. The pages expose complete ordered lists with 100 rows and 100 distinct Apple Music song IDs resolved from the Israel storefront. Each series is suitable for a separate Apple Music provider packet. None belongs in the Spotify/YouTube core.

All three pages identify Israel in the playlist title and use the /il storefront. Their annual year labels are supported, but none declares exact chart-window start and end dates; the packets therefore leave period_start and period_end null. Each page and its recovered row count support a reported depth of 100, with no depth conflict.

| Year | First-party Israel storefront page | Publisher wording and depth | Playlist publication date | Captured page SHA-256 | Packet ranking SHA-256 |
|---|---|---|---|---|---|
| 2018 | [Top 100 Songs 2018: Israel](https://music.apple.com/il/playlist/top-100-songs-2018-israel/pl.d8c8870e9c5e42d69fb51dbd3908a173) | Title says “Top 100 Songs 2018: Israel”; page description says 100 songs. Its editorial description mentions Israel’s pop scene in 2018 but does not separately call the rows the most-played songs. Page list and schema.org track sequence each contain 100 entries and agree on all track IDs. | 2018-11-30T01:08:06Z | 00a6be759b7a3258d6b6120cbdbc3a1e3b12df6794822edfa632123e2b89f220 | 5d46dbed211568d942009299479f2ef7d1a5bab63235af3ec125bd8639d734f8 |
| 2020 | [השירים המובילים של 2020: ישראל (Top Songs of 2020: Israel)](https://music.apple.com/il/playlist/%D7%94%D7%A9%D7%99%D7%A8%D7%99%D7%9D-%D7%94%D7%9E%D7%95%D7%91%D7%99%D7%9C%D7%99%D7%9D-%D7%A9%D7%9C-2020-%D7%99%D7%A9%D7%A8%D7%90%D7%9C/pl.135873db139a4d83b82e5d19e5930d9d?l=he) | Apple says, “אלה 100 השירים המושמעים ביותר בישראל ב-2020” (“These are the 100 most-played songs in Israel in 2020”); the page reports 100 songs. The serialized page has ranks 1–100 and 100 unique IDs, all with /il/ song URLs. | 2020-11-12T20:19:31Z | 0607acc9bad5c0c34c5c2d43979c750c42ea581bfb50ce6d69a38a5d3ac50d2e | f964ef09d933391be26ca0a69e5908fc6cee158b919fa7e2191725dafd102e1b |
| 2021 | [Top Songs of 2021: Israel](https://music.apple.com/il/playlist/top-songs-of-2021-israel/pl.3a25ba7d6aa5440b9c2e4dc7b1625ca8) | Apple describes it as “Apple Music’s most-played songs of the year in Israel”; the page reports 100 songs. The serialized page has ranks 1–100 and 100 unique IDs, all resolved from the /il/ page payload. | 2021-11-29T17:51:06Z | 7372ee4b8106bda77d7e559eb7189ea093e714db0aa6d00cf7c9276fb4f56395 | e65eddeb77b4c6a3421e08dd4eea948dca1daf266c0c1b115196619fe22e446a |

The playlist publication dates are metadata, not chart-period boundaries. In particular, the 2018 page establishes an annual playlist title and 100-track depth, but does not state a play-count method. Its ranking rows are kept as published positions without a stronger methodology claim.

## Captures, ranking extractions, and packets

Each captured page returned HTTP 200 with text/html. The source body, response headers, and capture metadata are preserved under the matching raw evidence directory. The packet copies the captured page byte-for-byte; the page SHA-256 is unchanged.

| Year | Raw evidence directory | Source bytes / retrieval UTC | Raw extraction SHA-256 | Capture-manifest SHA-256 | Provider packet |
|---|---|---|---|---|---|
| 2018 | data/raw/national_charts/apple_music_il_2018/ | 704,392 bytes; 2026-11-17T15:40:49Z | 85039b38bed22fd2ba7fdf41ad6513be6b5c47500dd87837a379f503ee802c3c | 09dcaf61a98bae9fc6731b4410253da0afdd1288c977d5216e23f6d16b10e388 | data/derived/annual_revision/provider_series/apple-music-il-2018-annual/ |
| 2020 | data/raw/national_charts/apple_music_il_2020/ | 750,409 bytes; 2026-11-17T15:40:49Z | 7be0a4ff42034a6a15d059bae9d32108d26871e68a9aef43974dc2e4982900be | 8280fa7e57c6c83ae3b67e93f2dd84a4e5643104508eeed61887849f73b10b21 | data/derived/annual_revision/provider_series/apple-music-il-2020-annual/ |
| 2021 | data/raw/national_charts/apple_music_il_2021/ | 727,241 bytes; 2026-11-17T15:40:53Z | Ranking rows are in the packet rankings.jsonl | d035f84f419c202f5ac8df7733ceaba14846b2f39fc709eaff500e7ea9fa36b9 | data/derived/annual_revision/provider_series/apple-music-il-2021-annual/ |

The packet ranking-file SHA-256 values are recorded in the first table. Packet manifest SHA-256 values are:

- 2018: 90a2110e22ab89d0d776fb39a2e18892d13fe0510ceb9174064e4fc8ddc0b866
- 2020: f0400562dc2ad82b7477f76036086cd11a55764b50fb3c861996f635d081d8a5
- 2021: 10599f1146917272663359814e75a3ea385e1409e69566b4974520cdffdc6145

The original raw rank extractions for 2018 and 2020 remain preserved separately from the standardized packet files. Their hashes are included above and in the corresponding packet manifests. The 2021 rows were transcribed from the serialized page payload into the packet.

## Provider and market handling

The packets use provider_code APPLE_MUSIC, publisher_country_code US, and chart_market_code IL. Song IDs are the Apple Music IDs served on each Israel storefront page; no US storefront IDs were substituted. Each year has its own APPLE_MUSIC_TOP_SONGS_IL_<year> series, 100 published ranks, and unknown exact period boundaries. The packets remain outside the active supplemental catalog/index and the Spotify/YouTube core.
