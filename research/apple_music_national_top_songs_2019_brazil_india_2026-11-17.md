# Apple Music national Top Songs of 2019: Brazil and India

Date consulted: 2026-11-17 UTC. Both first-party market storefront pages returned HTTP 200. Their serialized playlist rows carry contiguous `rankingText` positions 1–100 and local storefront song URLs.

| Market | Apple Music page | Playlist ID | Published rows | Page snapshot SHA-256 |
|---|---|---|---:|---|
| Brazil | [O melhor de 2019: Brasil](https://music.apple.com/br/playlist/top-songs-of-2019-brazil/pl.3a5fdd7488734424bec161aa9e506215) | `pl.3a5fdd7488734424bec161aa9e506215` | 100 | `df99371b95894926a0fe1936e07869a4f76e99f26f8039bebec4d943fb340e79` |
| India | [Top Songs of 2019: India](https://music.apple.com/in/playlist/top-songs-of-2019-india/pl.bd84436418654c3f86ad5f99700d4738) | `pl.bd84436418654c3f86ad5f99700d4738` | 100 | `c99d91b24be89b243b0bd89312b289870d3d270947fa8f206ce7aa0a1b0e3868` |

The captured source pages are stored in `apple-music-br-2019-annual` and `apple-music-in-2019-annual` under [`provider_series`](../data/derived/annual_revision/provider_series/). The packets retain 200 provider-ranked positions with the matching Brazilian and Indian storefront song IDs. Apple identifies the annual list but provides no exact chart-period bounds; `period_start` and `period_end` remain null. These Apple Music series remain separate from the Spotify/YouTube selection.
