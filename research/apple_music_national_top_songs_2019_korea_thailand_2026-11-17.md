# Apple Music national Top Songs: Korea and Thailand, 2019

Captured 2026-11-17 UTC. This note records two official Apple Music annual playlist series for 2019. Each series retains its chart-market storefront IDs, its own provider denominator, and its published positions. Neither is joined to the Spotify/YouTube cohort or to another publisher's ranks.

## Findings

| Market | Apple playlist | Published depth | Recovered ranks | Exact measurement period |
|---|---|---:|---:|---|
| Korea (`KR`) | Top Songs of 2019: Korea | 100 songs, 5 hours 52 minutes | 1–100 | Not stated |
| Thailand (`TH`) | Top Songs of 2019: Thailand | 100 songs, 5 hours 58 minutes | 1–100 | Not stated |

Apple Music identifies each as a year-end Top Songs playlist and publishes consecutive ranking labels 1 through 100. The captured local-storefront page representations and JSON-LD agree on all 100 track titles; each position has a distinct Apple Music song ID in the matching market storefront. Neither page supplies numeric stream counts or exact start/end dates. The playlist `datePublished` values are capture metadata, not measurement-period boundaries, so `period_start` and `period_end` remain null.

Apple Music is recorded as the publisher (`publisher_country_code=US`); the page's country label and matching storefront identify `KR` and `TH` as the chart markets. These are two distinct Apple Music series:

- `APPLE_MUSIC_TOP_SONGS_KR_2019` — 100 ranked positions, reported depth 100.
- `APPLE_MUSIC_TOP_SONGS_TH_2019` — 100 ranked positions, reported depth 100.

## Official Apple Music pages

- Korea: [Top Songs of 2019: Korea](https://music.apple.com/kr/playlist/top-songs-of-2019-korea/pl.6280e163d35b4ed6b1c9f2c7f8cc931c?l=en-GB). Apple reports 100 songs and displays ranks in the page.
- Thailand: [Top Songs of 2019: Thailand](https://music.apple.com/th/playlist/top-songs-of-2019-thailand/pl.2c9773629e18426aae4710aeca40fa53). Apple reports 100 songs and displays ranks in the page.

## Local packets and integrity

Each packet stores the captured official chart-market storefront HTML, ordered `rankings.jsonl`, and `manifest.json`:

- Korea: `data/derived/annual_revision/provider_series/apple-music-kr-2019-annual/`
  - Page SHA-256: `81cd99f30a32110481d5ef18be16c9f25b5d74851f9c96661418f31921357ef3`
  - Ranking SHA-256: `725a86fbd9956aae6861d6e9098bd1ee329412dca79241c38774d80bdbe61ddb`
- Thailand: `data/derived/annual_revision/provider_series/apple-music-th-2019-annual/`
  - Page SHA-256: `c0a58c10c5eed0e613998b5986c8e0ce8a9c5f314191068b35ed65b914b35689`
  - Ranking SHA-256: `204f1aedeab188f922da928b8cc782857cb2283cdc1f4909ad7027eee5f217ca`

For both pages, the JSON-LD track order was checked against the serialized page's explicit `rankingText` values 1–100. All track titles matched, all song links used the local storefront, and each series had 100 unique native Apple Music song IDs. Hashes, positions, counts, and denominator records are also included in the versioned supplemental catalog and provider-series index.
