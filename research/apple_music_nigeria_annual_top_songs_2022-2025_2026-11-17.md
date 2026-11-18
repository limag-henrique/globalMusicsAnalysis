# Apple Music Nigeria annual Top Songs playlists, 2022–2025

Research note: 2026-11-17. Each official Apple Music playlist is an independent provider series for the Nigeria market. These positions stay separate from Spotify, YouTube, and other providers.

## Findings

Apple Music publishes a 100-song year-end playlist titled “Top Songs of {year}: Nigeria” for each year below. Its official page states the listening window. The captures preserve the order shown on the page and 100 distinct Apple Music song IDs per year.

| Reporting year | Published play window | Chart depth | First position | 100th position | Official page |
|---:|---|---:|---|---|---|
| 2022 | 2021-11-01 to 2022-10-31 | 100 | “Sungba” — Asake | “IDG (feat. Wizkid)” — Aṣa | [Apple Music Nigeria](https://music.apple.com/ng/playlist/top-songs-of-2022-nigeria/pl.ec79cd99c95446518a07db647a08ffd0) |
| 2023 | 2022-11-01 to 2023-10-31 | 100 | “soso” — OMAH LAY | “Real Life (feat. Stormzy)” — Burna Boy | [Apple Music Nigeria](https://music.apple.com/ng/playlist/top-songs-of-2023-nigeria/pl.7f3dfa8824a3413fad725355f96a294c) |
| 2024 | 2023-11-01 to 2024-10-31 | 100 | “Different Pattern” — Seyi Vibez | “Man of The Year” — Seyi Vibez | [Apple Music Nigeria](https://music.apple.com/ng/playlist/top-songs-of-2024-nigeria/pl.c0ca9fcf2dd54a19ab1e98614d9979c9) |
| 2025 | 2024-11-01 to 2025-10-31 | 100 | “WHY LOVE” — Asake | “Gimme Dat” — Ayra Starr & Wizkid | [Apple Music Nigeria](https://music.apple.com/ng/playlist/top-songs-of-2025-nigeria/pl.98ef66bcdb944ea39b180927216526da) |

The source HTML exposes the playlist title, play-window text, ordered track rows, Apple song IDs, and song URLs. Each captured series was checked for 100 consecutive positions (1–100), unique native Apple song IDs, and a matching ranking-file hash. The playlist pages report play windows but do not publish play counts or a more detailed weighting formula.

## Provider packets

- `data/derived/annual_revision/provider_series/apple-music-ng-2022-annual/`
- `data/derived/annual_revision/provider_series/apple-music-ng-2023-annual/`
- `data/derived/annual_revision/provider_series/apple-music-ng-2024-annual/`
- `data/derived/annual_revision/provider_series/apple-music-ng-2025-annual/`

Each packet contains the captured official page (`source-page.html`), its SHA-256 and retrieval metadata in `manifest.json`, plus 100 ordered rows in `rankings.jsonl`. The publisher is recorded as Apple Music / US and the chart market as Nigeria (`NG`).

The 2020–2021 Apple Music Nigeria playlists are documented separately in [the earlier research note](apple_music_nigeria_pakistan_annual_top_songs_2018-2021_2026-11-16.md); those page captures did not state exact play-window boundaries.
