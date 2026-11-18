# Apple Music national Top Songs of 2019: Italy, Netherlands, Portugal, Spain, and Sweden

Date consulted: 2026-11-17 UTC. Direct requests to each matching Apple Music storefront returned HTTP 200. The serialized playlist rows expose 100 consecutive `rankingText` positions, and each song link uses its local storefront.

| Market | Official Apple Music page | Ranked positions | Source-page SHA-256 |
|---|---|---:|---|
| Italy | [Top brani del 2019: Italia](https://music.apple.com/it/playlist/top-songs-of-2019-italy/pl.f75c502538c647adbb6824f6e582a004) | 1–100 | `3cbdd790d6f0cdef8250e5b8f43f14d5ef23abd307f7b468a37ba53e0eb039f6` |
| Netherlands | [Topnummers 2019: Nederland](https://music.apple.com/nl/playlist/top-songs-of-2019-netherlands/pl.f0b422df67b040a583bd5694492aebf4) | 1–100 | `e1d06ef49722b9d430c57d7e0d3ed2f030b23fee1aeb5f7531a9de1501c44e38` |
| Portugal | [Top músicas 2019: Portugal](https://music.apple.com/pt/playlist/top-songs-of-2019-portugal/pl.7ca69158c76d45edadd51c7aaec2a4b2) | 1–100 | `44784dce7c9b62728d980c90e62db258c339bb2c8998828b55e25722aa3d602e` |
| Spain | [Top canciones de 2019: España](https://music.apple.com/es/playlist/top-songs-of-2019-spain/pl.7c900cbf05a34e90af5bcb89b534292d) | 1–100 | `8100c47c7b8e85f9958a86578a189ec44505b4518967cee16d3c8b94149a2e38` |
| Sweden | [De största låtarna 2019: Sverige](https://music.apple.com/se/playlist/top-songs-of-2019-sweden/pl.9aa0ba9c0e0c401fb309e5c9bf906dd3) | 1–100 | `017169f5efccf41161f7b70cda8a28ce34e9da48a7607fedb1fbb9aebce32e2d` |

Source bodies and 500 ranked positions are preserved in `apple-music-it-2019-annual`, `apple-music-nl-2019-annual`, `apple-music-pt-2019-annual`, `apple-music-es-2019-annual`, and `apple-music-se-2019-annual` under [`provider_series`](../data/derived/annual_revision/provider_series/). Apple labels each playlist as 2019 but gives no exact chart-period bounds; packet dates remain null. Each is a separate Apple Music provider series, not a Spotify/YouTube ranking.
