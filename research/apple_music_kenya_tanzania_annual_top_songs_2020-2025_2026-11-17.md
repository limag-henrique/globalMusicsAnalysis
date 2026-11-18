# Apple Music annual Top Songs: Kenya and Tanzania (2020–2025)

Date captured: 2026-11-17 UTC. This note records ten newly captured Apple Music playlist series for Kenya (KE) and Tanzania (TZ), 2020–2025. Each remains a separate Apple Music series with its own 100-position denominator; none is merged into Spotify, YouTube, or another publisher’s ranks.

## Captured series

| Market | Reporting year | Published list | Period Apple Music states |
|---|---:|---|---|
| TZ | 2020 | 100 songs | Exact dates not stated on captured page |
| TZ | 2021 | 100 songs | Exact dates not stated on captured page |
| TZ | 2022 | 100 songs | 2021-11-01 to 2022-10-31 |
| TZ | 2023 | 100 songs | 2022-11-01 to 2023-10-31 |
| KE | 2020 | 100 songs | Exact dates not stated on captured page |
| KE | 2021 | 100 songs | Exact dates not stated on captured page |
| KE | 2022 | 100 songs | 2021-11-01 to 2022-10-31 |
| KE | 2023 | 100 songs | 2022-11-01 to 2023-10-31 |
| KE | 2024 | 100 songs | 2023-11-01 to 2024-10-31 |
| KE | 2025 | 100 songs | 2024-11-01 to 2025-10-31 |

For 2020 and 2021, Apple Music calls these its most-played songs of the named year but the captured pages do not provide exact period dates or numeric play counts. No calendar-year boundaries or scores are inferred. The 2022–2025 pages explicitly define November–October end-of-year chart periods.

## Source pages

- Tanzania: [2020](https://music.apple.com/us/playlist/top-songs-of-2020-tanzania/pl.719c61e35a4844aa9f7b84a40314b5c7), [2021](https://music.apple.com/us/playlist/top-songs-of-2021-tanzania/pl.a244575a739e471aaf51d8f32cd5981b), [2022](https://music.apple.com/tz/playlist/top-songs-of-2022-tanzania/pl.b59a50907cde4b69b154bda1679c4355), [2023](https://music.apple.com/us/playlist/top-songs-of-2023-tanzania/pl.e0f05adaf0d44eb4a3836342ac377a1a).
- Kenya: [2020](https://music.apple.com/us/playlist/top-songs-of-2020-kenya/pl.0aa717f083c348729c23a59c3fac455f), [2021](https://music.apple.com/gb/playlist/top-songs-of-2021-kenya/pl.2bb2a5510f104f22b9f5980317dc78ee), [2022](https://music.apple.com/us/playlist/top-songs-of-2022-kenya/pl.a05dbe4729ba4d56aecb88d5088489e5), [2023](https://music.apple.com/ke/playlist/top-songs-of-2023-kenya/pl.c05bf8be3fd04e558fb8d00edc0a922b), [2024](https://music.apple.com/us/playlist/top-songs-of-2024-kenya/pl.430ae3ccdd2d46d88b23c8af4519c7db), [2025](https://music.apple.com/ke/playlist/top-songs-of-2025-kenya/pl.39eb6078811543b4acc4cb334bdabcb7).

## Local evidence and validation

Each series has a captured `source-page.html`, `rankings.jsonl`, and `manifest.json` under `data/derived/annual_revision/provider_series/apple-music-{ke|tz}-<year>-annual/`. The serialized Apple Music page data reports 100 tracks for each playlist; extracted rows preserve that order and the Apple Music song ID, track URL, title, and artist credit. Validation confirmed positions 1–100, 100 unique native track IDs per series, null scores, and agreement between page/ranking hashes and packet manifests. The provider index now has 30 independent series and 2,040 ranked memberships across all providers. Apple Music contributes 12 series and 1,200 positions for KE/TZ over 2020–2025.

These are platform-specific charts whose titles identify the chart market. Apple Music’s publisher jurisdiction is recorded separately as US. The 2020–2025 rankings remain independent of the main 150,000-position Spotify/YouTube cohort.

The earlier Tanzania 2024–2025 capture is documented in [Apple Music Tanzania annual Top Songs](apple_music_tanzania_annual_top_songs_2024-2025_2026-11-17.md).
