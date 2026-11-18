# Apple Music Ghana, South Africa, and India annual Top Songs playlists, 2020–2025

Research note: 2026-11-17. This capture adds three official Apple Music country playlists across six years. Each is preserved as its own Apple Music provider series and remains separate from Spotify, YouTube, and other providers.

## Findings

Each captured playlist publishes 100 songs in position order. Source HTML exposes 100 consecutive ranking values and 100 distinct native Apple Music song IDs per playlist. No score or play-count values are published.

| Chart market | Years captured | Position depth | Published play window |
|---|---|---:|---|
| Ghana (`GH`) | 2020–2025 | 100 each year | Apple states 1 November of the prior year through 31 October for 2022–2025. Exact boundaries are not stated on the 2020–2021 pages. |
| South Africa (`ZA`) | 2020–2025 | 100 each year | Apple states 1 November of the prior year through 31 October for 2022–2025. Exact boundaries are not stated on the 2020–2021 pages. |
| India (`IN`) | 2020–2025 | 100 each year | Exact boundaries are not stated on any of the six captured pages. |

For Ghana and South Africa, the explicit windows are 2022: 2021-11-01–2022-10-31; 2023: 2022-11-01–2023-10-31; 2024: 2023-11-01–2024-10-31; and 2025: 2024-11-01–2025-10-31. For other years and for India, `period_start` and `period_end` remain null rather than being inferred from playlist titles.

The publisher is recorded as Apple Music (`publisher_country_code=US`); the chart markets come from each playlist’s explicit country title and matching Apple storefront (`GH`, `ZA`, or `IN`). Ranking positions are retained as published, with no merge into Spotify or YouTube ranking series.

## Official Apple Music pages

### Ghana

- 2020: [Top Songs of 2020: Ghana](https://music.apple.com/gh/playlist/top-songs-of-2020-ghana/pl.9c920ac2090e4e17b3a1b06b2a855d2f)
- 2021: [Top Songs of 2021: Ghana](https://music.apple.com/gh/playlist/top-songs-of-2021-ghana/pl.5ccaf204833d43b5b01915737b0cf6c7)
- 2022: [Top Songs of 2022: Ghana](https://music.apple.com/gh/playlist/top-songs-of-2022-ghana/pl.3be0959424884fc7a74c9f63e79e3c11)
- 2023: [Top Songs of 2023: Ghana](https://music.apple.com/gh/playlist/top-songs-of-2023-ghana/pl.84375ba243eb449e81a2cf0d226a7e24)
- 2024: [Top Songs of 2024: Ghana](https://music.apple.com/gh/playlist/top-songs-of-2024-ghana/pl.3532ba9ec97343e89fca71682406ddef)
- 2025: [Top Songs of 2025: Ghana](https://music.apple.com/gh/playlist/top-songs-of-2025-ghana/pl.2aeca8270e8b4be7965c00f0d0b6e667)

### South Africa

- 2020: [Top Songs of 2020: South Africa](https://music.apple.com/za/playlist/top-songs-of-2020-south-africa/pl.2093435fe878475db412c8c07030ea87)
- 2021: [Top Songs of 2021: South Africa](https://music.apple.com/za/playlist/top-songs-of-2021-south-africa/pl.74282e60780842148625504c638d862b)
- 2022: [Top Songs of 2022: South Africa](https://music.apple.com/za/playlist/top-songs-of-2022-south-africa/pl.c44ce501a5334b65af80677ee57b79ae)
- 2023: [Top Songs of 2023: South Africa](https://music.apple.com/za/playlist/top-songs-of-2023-south-africa/pl.0791d1a0ff6e4c1aa32c9290afa14277)
- 2024: [Top Songs of 2024: South Africa](https://music.apple.com/za/playlist/top-songs-of-2024-south-africa/pl.b11d4ec32d1e4c649d58b21a891b675c)
- 2025: [Top Songs of 2025: South Africa](https://music.apple.com/za/playlist/top-songs-of-2025-south-africa/pl.7da57a068d684b7cb8823c57eba04dea)

### India

- 2020: [Top Songs of 2020: India](https://music.apple.com/in/playlist/top-songs-of-2020-india/pl.50efe94a89ae45669a975286c9e5f921)
- 2021: [Top Songs of 2021: India](https://music.apple.com/in/playlist/top-songs-of-2021-india/pl.462fb4ea214e474d83fd722f0c00a71e)
- 2022: [Top Songs of 2022: India](https://music.apple.com/in/playlist/top-songs-of-2022-india/pl.c1d60bc3fb1741cbbcefe9cf27f17219)
- 2023: [Top Songs of 2023: India](https://music.apple.com/in/playlist/top-songs-of-2023-india/pl.5c9e3709553647d2b0ce7f29dc80b9e4)
- 2024: [Top Songs of 2024: India](https://music.apple.com/in/playlist/top-songs-of-2024-india/pl.4b5c275b693c433192c2d5a43abfb809)
- 2025: [Top Songs of 2025: India](https://music.apple.com/in/playlist/top-songs-of-2025-india/pl.79dab52e4bfc4f779a85a91cc634f94c)

## Provider packets

Each packet includes an official captured page, hash and retrieval metadata in `manifest.json`, and ordered rows in `rankings.jsonl`:

- Ghana: `data/derived/annual_revision/provider_series/apple-music-gh-{2020..2025}-annual/`
- South Africa: `data/derived/annual_revision/provider_series/apple-music-za-{2020..2025}-annual/`
- India: `data/derived/annual_revision/provider_series/apple-music-in-{2020..2025}-annual/`

Integrity review confirmed 100 positions, 100 unique Apple song IDs, and a matching ranking-file hash in each of the 18 packets. The Nigeria Apple Music captures are documented in [the 2020–2021 note](apple_music_nigeria_pakistan_annual_top_songs_2018-2021_2026-11-16.md) and [the 2022–2025 note](apple_music_nigeria_annual_top_songs_2022-2025_2026-11-17.md).
