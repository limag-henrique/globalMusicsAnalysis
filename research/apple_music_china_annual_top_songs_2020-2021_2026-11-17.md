# Apple Music China annual Top Songs playlists, 2020–2021

Captured 2026-11-17 UTC. These two official Apple Music country storefront playlists are preserved as independent Apple Music provider series. They remain separate from Spotify, YouTube, and the core annual ranking.

## Findings

The captured Apple Music pages each contain 100 song rows. Their serialized page data has explicit `rankingText` values 1–100, and the 100 distinct Apple Music song IDs in each ordered list match the page JSON-LD track array. The full ranked records, including positions and native track IDs, are stored in each packet's `rankings.jsonl`.

For 2020, a prior first-party page rendering reported 99 songs and 6 hours 47 minutes, while the preserved page body and a re-opened page rendering report 100 songs and 6 hours 51 minutes. The captured page payload has 100 tracks and ranks 1–100. Because those page readings conflict, the 2020 manifest leaves `reported_depth` null while retaining the 100 observed ranked rows. The earlier rendering was not captured as a raw HTML artifact, so it has no source hash in the packet.

The 2021 page reports 100 songs and 7 hours 6 minutes, matching the 100 ordered rank labels and JSON-LD tracks. Its description calls these Apple Music's most-played songs of the year in China. The 2020 page title identifies Top Songs of 2020: China, but its description only invites listeners to play the playlist.

Neither page states an exact measurement-window start/end or a ranking methodology. Page `datePublished` metadata (2020-11-12T20:59:26Z and 2021-12-01T02:36:05Z) is retained only as publication metadata, not used as the ranking window. `period_start` and `period_end` remain null. Neither page publishes numeric play counts or scores.

The English page titles say “China”; Apple’s Chinese storefront title is “2020 年度最热歌曲：中国大陆” / “2021 年度最热歌曲：中国大陆”, and the storefront region selector labels the market “中国大陆” (China mainland). The packets therefore use chart market `CN`. Apple Music is recorded as the publisher (`publisher_country_code=US`).

## Official Apple Music pages and packets

| Year | Official page | Page statement | Observed ranks / tracks | Reported depth |
|---|---|---|---:|---:|
| 2020 | [Top Songs of 2020: China](https://music.apple.com/cn/playlist/top-songs-of-2020-china/pl.53a96646b417422fae690a428c45f3e2?l=en-GB) | Current captured page: 100 songs, 6h51; previous page rendering: 99 songs, 6h47 | 1–100 / 100 | Unknown due conflicting page readings |
| 2021 | [Top Songs of 2021: China](https://music.apple.com/cn/playlist/top-songs-of-2021-china/pl.f057c52242794b47bfb950d4e99eda37?l=en-GB) | 100 songs, 7h06; “most-played songs of the year in China” | 1–100 / 100 | 100 |

Each packet contains the official CN storefront HTML, its SHA-256 and retrieval metadata in `manifest.json`, and the ordered Apple Music track IDs and rows in `rankings.jsonl`:

- 2020: `data/derived/annual_revision/provider_series/apple-music-cn-2020-annual/` (`APPLE_MUSIC_TOP_SONGS_CN_2020`)
- 2021: `data/derived/annual_revision/provider_series/apple-music-cn-2021-annual/` (`APPLE_MUSIC_TOP_SONGS_CN_2021`)

The capture uses the CN storefront page payload. The same playlist IDs under a US storefront returned different displayed track records at some positions, so US storefront IDs were not substituted for China-market IDs.

## Capture and integrity

The source pages were retrieved at 2026-11-17T14:22:51Z. Integrity review verified that both ranking files contain 100 rows in positions 1–100, with 100 unique Apple song IDs per page; the serialized page rank labels, JSON-LD track order, and packet ranking order agree. No ranking positions were inferred. The packets are provider-tagged and do not merge into Spotify or YouTube rankings.

| Year | Source HTML SHA-256 | `rankings.jsonl` SHA-256 |
|---|---|---|
| 2020 | `d22491470221752a3c463c1a2a44594f8c583ca6c6f7cc0fd6b4fce41e6147a1` | `5ca134da3311457ab4318abac7bf693ee97c7a101a3da845ab641fcbdf12c483` |
| 2021 | `a191a25edf792be98771143f2356e9191bedcd411792a3579ea1f1a9e172cc54` | `85f1ea9de29c09ad1121d8cccc857bd10ac9b547e5cdfea32b414d5d98f8a075` |