# Apple Music Singapore and Thailand annual playlists, 2020–2021

Audit date: 2026-11-17.

## Findings

Apple Music has first-party annual playlists for Singapore and Thailand in 2020 and 2021. Each chart-market storefront page returned HTTP 200 and contains 100 ranked songs, with positions 1–100, 100 distinct Apple Music song IDs, and song URLs from the matching `/sg` or `/th` storefront. The captured serialized-server-data rank sequence agrees with the schema.org `MusicPlaylist` track-ID sequence for all 100 rows.

These are separate Apple Music series. The playlist publication date is preserved as page metadata; Apple does not state exact measurement-period boundaries, so packet `period_start` and `period_end` remain null.

| Market/year | First-party chart-market page | Publisher wording and scope | Published | Captured page SHA-256 | Packet ranking SHA-256 |
|---|---|---|---|---|---|
| Singapore 2020 | [Top Songs of 2020: Singapore](https://music.apple.com/sg/playlist/top-songs-of-2020-singapore/pl.d872e45bd56245f4b3afa182db49e444) | The page describes these as the biggest songs in Singapore on Apple Music in 2020; it does not state a specific calculation formula. 100 songs. | 2020-11-12T21:11:35Z | 71edc638082162dc181870b8941523e81aac7fb2f8c7084a1ebb97afb6d4e126 | 126820fac1e67a26755d3da4af14c46215536ba31095f6038761ecc91e7e4526 |
| Singapore 2021 | [Top Songs of 2021: Singapore](https://music.apple.com/sg/playlist/top-songs-of-2021-singapore/pl.7a2a61218ad540c4b1ad708c032ae9ad) | Apple calls these its most-played songs of the year in Singapore. 100 songs. | 2021-11-29T17:53:45Z | 07fe14836ddb34c6277ad8d59433ef8c6e289e21dd1778763572df480e866d3e | fc471d5ff9411d40919e83231100966e11b802b5b2c71c9deca22bf2c704256d |
| Thailand 2020 | [Top Songs of 2020: Thailand](https://music.apple.com/th/playlist/top-songs-of-2020-thailand/pl.9bd219a0938a4af29cc8a588ad37d375) | The page title identifies Thailand and 2020 and reports 100 songs; it does not state a separate measurement formula. | 2020-11-12T20:54:45Z | f7a7128fd11739559587f51aaccfc01a8e5a2111a55b703365c39fe4b303c095 | 34db5e8530c01a8e8bda942ae0212427fbf5b4516444f7b286b2294323b6336d |
| Thailand 2021 | [Top Songs of 2021: Thailand](https://music.apple.com/th/playlist/top-songs-of-2021-thailand/pl.c30591918b8c492c9c125158c975807d) | Apple calls these its most-played songs of the year in Thailand. 100 songs. | 2021-11-29T17:54:40Z | 0110ab399524bdfbce5f71db70036e0943aec1ff44e15f6aa1696e5a38e3fcfb | b2f9dee8804db77b0513d3dc128edf5f43b3d923f741c08e173849ae70ce7309 |

The annual year labels and page descriptions do not establish exact chart-window start or end dates. No Spotify or YouTube positions were inferred from these Apple lists.

## Captures and packets

The response headers, decoded HTML bodies, capture manifests, and extracted rank/ID rows are under `data/raw/national_charts/apple_music_sg_2020/`, `apple_music_sg_2021/`, `apple_music_th_2020/`, and `apple_music_th_2021/`. Each corresponding provider packet copies the captured page byte-for-byte and preserves the same body SHA-256.

| Market/year | Retrieval UTC | Raw extraction SHA-256 | Capture-manifest SHA-256 | Provider packet | Packet manifest SHA-256 |
|---|---|---|---|---|---|
| Singapore 2020 | 2026-11-17T16:09:42Z | 35d2a4ec3b49c23c82e47c6eb9d22b88e266efadc4fb15b153a9f1cd3f92effb | 167f9731cd7343543cafc3efcf014cfa8d42d58055a5c0133f6382a315e0fbc8 | `apple-music-sg-2020-annual/` | b14b35fa8f6c80c49da43136f35bdc36ada302c65ada73af5f2481ecdbfbfa5d |
| Singapore 2021 | 2026-11-17T16:09:42Z | e8ab577df3c192a64c150e3d9307a14d96b355bd5abea4b200da894a813c7533 | 155dabed5d26275fc2528fdbed30175ae886d241dfa9806aad8808ca20696c7c | `apple-music-sg-2021-annual/` | d38f27ce3af3a3aa63413e6709146fd0151df628b5d8ff68eeba0b78b31cf340 |
| Thailand 2020 | 2026-11-17T16:09:42Z | c11666c6a2d550a006a9e9b58cefb039c0913aefa17aaf548d415be1db2cdcea | 48d0eba0a4c14d431a99db580eaaa1ba2ab3c94747104c3729d04f4cb8b9fe86 | `apple-music-th-2020-annual/` | d8b771c3b2d0d3753a6f7a5bbfcc5a85008c2235d9ebd96d54fd2d5b1927236a |
| Thailand 2021 | 2026-11-17T16:09:43Z | 0c2e33366f47ccfdb600b0e2808df4241453194e71a9c70cf806c0d8014a80fd | 94290e10ada2b386ea8a610df4e5bec630c1305dd3d42006fb3f812d3d897744 | `apple-music-th-2021-annual/` | 5d79371a2c81b9a8350360003e051e1683d74bc3fa79e77f081a4cacd8fd37df |

Packets use `provider_code=APPLE_MUSIC`, `publisher_country_code=US`, and market-specific `chart_market_code=SG` or `TH`. Each packet reports depth 100, stores the local storefront song IDs only, and keeps its rows separate from the Spotify/YouTube selection.

## Supplemental catalog integration

The four packets were appended after the v30 packet order and imported as v31. The supplemental catalog now contains 333 provider series and 37,999 ranked memberships; the report sums 29,863 publisher-reported depth, lists 26 depth-unknown series, and has 18,965 normalized provider identity keys (not adjudicated canonical songs). The four packets add 400 memberships and 87 normalized identity keys.

SQLite `quick_check` returned `ok`, foreign-key violations were zero, and the v30 series, memberships, and song rows are unchanged in v31. All packet source/ranking hashes passed, three review-only packets remain unranked, and no packets were skipped. The active provider-series index matches the versioned v31 index. The Spotify/YouTube core was not changed.

The inherited v29 index/report chart-depth disagreement for seven older Circle Chart/TME UNI series remains flagged for source-level reconciliation; none of the four new packets is part of that discrepancy.
