# Apple Music national annual song rankings: additional 2019 markets

Captured 2026-11-17 UTC. This note records 12 additional Apple Music country/market-specific annual playlists for 2019. Each remains a separate provider series with its own published denominator and chart-market storefront IDs. None is merged into Spotify/YouTube ranks or the core 150,000-position selection.

## Findings

Apple Music provides an ordered national playlist for each market below. Eleven pages report 100 songs and publish ranks 1–100; Norway reports 99 songs and publishes ranks 1–99. The exact start/end of the measurement period and numeric play counts are not stated on these pages. Playlist publication timestamps are retained as metadata and are not treated as measurement-period boundaries; `period_start` and `period_end` remain null.

The 12 series contain **1,199 observed ranked positions** total. Apple Music is recorded as publisher (`publisher_country_code=US`); each chart market is assigned from the playlist’s country label and matching storefront. The series keep each provider, year, market, chart family, and denominator distinct.

## Official Apple Music pages and packets

| Market | Apple Music playlist | Observed / reported depth | Series ID | Local packet |
|---|---|---:|---|---|
| `AT` | [Top Songs of 2019: Austria](https://music.apple.com/at/playlist/top-songs-of-2019-austria/pl.babc5b9545e34b039423f95e6dfe511a?l=en-GB) | 100 / 100 | `APPLE_MUSIC_TOP_SONGS_AT_2019` | `data/derived/annual_revision/provider_series/apple-music-at-2019-annual/` |
| `BE` | [Top Songs of 2019: Belgium](https://music.apple.com/be/playlist/top-songs-of-2019-belgium/pl.2eeb6855a39244589f7e8206eb8fda0f) | 100 / 100 | `APPLE_MUSIC_TOP_SONGS_BE_2019` | `data/derived/annual_revision/provider_series/apple-music-be-2019-annual/` |
| `CH` | [Top Songs of 2019: Switzerland](https://music.apple.com/ch/playlist/top-songs-of-2019-switzerland/pl.5d09425cd2cd4f8aa86485e1d1ee1052?l=en-GB) | 100 / 100 | `APPLE_MUSIC_TOP_SONGS_CH_2019` | `data/derived/annual_revision/provider_series/apple-music-ch-2019-annual/` |
| `DK` | [Top Songs of 2019: Denmark](https://music.apple.com/dk/playlist/top-songs-of-2019-denmark/pl.77f6b20449b543e0b9332742b13a6206) | 100 / 100 | `APPLE_MUSIC_TOP_SONGS_DK_2019` | `data/derived/annual_revision/provider_series/apple-music-dk-2019-annual/` |
| `FI` | [Top Songs of 2019: Finland](https://music.apple.com/fi/playlist/top-songs-of-2019-finland/pl.aaedf3117fef4d8095989218b5216482) | 100 / 100 | `APPLE_MUSIC_TOP_SONGS_FI_2019` | `data/derived/annual_revision/provider_series/apple-music-fi-2019-annual/` |
| `IE` | [Top 100 Songs of 2019: Ireland](https://music.apple.com/ie/playlist/top-100-songs-of-2019-ireland/pl.623387864e0d47019a90cad2930fdf91) | 100 / 100 | `APPLE_MUSIC_TOP_100_SONGS_IE_2019` | `data/derived/annual_revision/provider_series/apple-music-ie-2019-annual/` |
| `IL` | [Top Songs of 2019: Israel](https://music.apple.com/il/playlist/top-songs-of-2019-israel/pl.8766657c2dca449783ee8a682b37e5b1) | 100 / 100 | `APPLE_MUSIC_TOP_SONGS_IL_2019` | `data/derived/annual_revision/provider_series/apple-music-il-2019-annual/` |
| `LU` | [Top Songs of 2019: Luxembourg](https://music.apple.com/lu/playlist/top-songs-of-2019-luxembourg/pl.b65f5cbad87e4a4eb7394fc99ddaf69d) | 100 / 100 | `APPLE_MUSIC_TOP_SONGS_LU_2019` | `data/derived/annual_revision/provider_series/apple-music-lu-2019-annual/` |
| `NO` | [Top Songs of 2019: Norway](https://music.apple.com/no/playlist/top-songs-of-2019-norway/pl.16709b6512e04d86b919cc8f5d43f970) | 99 / 99 | `APPLE_MUSIC_TOP_SONGS_NO_2019` | `data/derived/annual_revision/provider_series/apple-music-no-2019-annual/` |
| `RU` | [Top Songs of 2019: Russia](https://music.apple.com/ru/playlist/top-songs-of-2019-russia/pl.d68d8813e8a34daea76f9d61bbfc9422?l=en-GB) | 100 / 100 | `APPLE_MUSIC_TOP_SONGS_RU_2019` | `data/derived/annual_revision/provider_series/apple-music-ru-2019-annual/` |
| `TR` | [Top Songs of 2019: Türkiye](https://music.apple.com/tr/playlist/top-songs-of-2019-t%C3%BCrkiye/pl.a44dba866af347dab855121514e45387) | 100 / 100 | `APPLE_MUSIC_TOP_SONGS_TR_2019` | `data/derived/annual_revision/provider_series/apple-music-tr-2019-annual/` |
| `UA` | [Top Songs of 2019: Ukraine](https://music.apple.com/ua/playlist/top-songs-of-2019-ukraine/pl.e05d7a6639f14a459b4961ce10e4890f) | 100 / 100 | `APPLE_MUSIC_TOP_SONGS_UA_2019` | `data/derived/annual_revision/provider_series/apple-music-ua-2019-annual/` |

## Capture and integrity

Every packet contains the official chart-market storefront HTML, ordered `rankings.jsonl`, and `manifest.json`. The manifest records the retrieved source URL/time, source HTML SHA-256, ranking-file SHA-256, publisher, market, chart family, reported depth, and whether a score was published. The imported catalog verified packet source and ranking hashes. The serialized Apple page’s explicit rank labels matched the JSON-LD track order for every recovered row; each row retained a unique native Apple song ID from the matching local storefront.

No positions were inferred beyond the page’s reported song count. For Norway, the denominator is 99 because Apple reports 99 songs; no 100th rank was added.

## Series and rank coverage

| Market | Ranks captured | Depth note | Source HTML SHA-256 | Ranking SHA-256 |
|---|---:|---|---|---|
| `AT` | 1–100 | Published depth 100 | `cc4c20b45631d979014efc556f520188b4039272d392fa3def9c5ea9f65a179a` | `25a19a37a4a362f3d8f555655928be849c9a6ca836205d8811caf657641ad497` |
| `BE` | 1–100 | Published depth 100 | `6a7152fb1aa999c6d0c49e98b4864ee499c449d0eafc798b91d366bee28c3b3f` | `6450d9313822f2c4a122695c75574634fd261ca3edade2b4a4dc9ee5f1c81c7a` |
| `CH` | 1–100 | Published depth 100 | `6d47d911b49fe12a44dc4b14dd2646c92d1a1df0803257e75d50c343274f187b` | `9c893f6a10a5053244ac2d0cc07b58c8e76307975749bf77f9453f5449af5a40` |
| `DK` | 1–100 | Published depth 100 | `0d8a9aaa9f8b6bcb69afbe42f7e3408c8e8c8f2567efb422223e6e06701c717d` | `422bd148e9f739d0caee2cc71a158fc8645290a9c25eea726160007264c06a1e` |
| `FI` | 1–100 | Published depth 100 | `05c342f64b9d38175b26138218d732434c4f67f49516e43506ae08d59e5983d6` | `3b121d95ca32366aaf397ba5579bab2f9e3fad947d67c54720c7a00e690624d0` |
| `IE` | 1–100 | Published depth 100 | `72795536524ae6d59fc0748dade72fb9e0bcea3efc43fc7e5b70d99e6a94c7dd` | `de1abe394dfecd490a172deac3296e79244bfbb53374e98d6d8f2a1832cac3b2` |
| `IL` | 1–100 | Published depth 100 | `62e4413d4000b76af140ae8bb9506bd3631ce9f4f0d9a90777ba8a13c5c5a8e7` | `0a5431750d331b64e6b9b3680d3fea5dbb8a777ea08421217ab1b1153a314b38` |
| `LU` | 1–100 | Published depth 100 | `852e68453ebac8b4c279ebd349129fa175ac3d9f170591ed7cfe4481a6c48dcc` | `1cb5b6cc780d607e509d02d8a040251537617cf5809b1d642fe168ce171d3e54` |
| `NO` | 1–99 | Published depth 99 | `ee2663788b83a3db89e3b64b97a6700b917d32dc81eb9c71500ba444d76be64b` | `4dbb430db69445e61bae6a43687ccfd6f0123195b6819954c02078ed991f1891` |
| `RU` | 1–100 | Published depth 100 | `abcc9c3ac0d1dd5aa2140ea091352711ceecde68961773d13c64faa8b88823b2` | `84b9dc5b1c78bfa250b4ceba7b7992dbaeb405c7d260b0c29d8adbd1e614a78f` |
| `TR` | 1–100 | Published depth 100 | `9567cac180d9fcafffaddb57ee0d5e24ba291d8462bdc9d8eaa181967826dfff` | `ea6cae874084df5cae87e9f211d5d5b82248a46621d6b2375361818644c9d6fb` |
| `UA` | 1–100 | Published depth 100 | `d847de41fcb80607fded9d415b7b4bcc70d958575ffefd532ed7d72f0480c26c` | `a5be0ed8ddc2943da9846812f985d614f80382b283e5ff110699ca48b35374c2` |

