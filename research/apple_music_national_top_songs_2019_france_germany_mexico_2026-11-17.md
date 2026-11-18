# Apple Music national Top Songs of 2019: France, Germany, and Mexico

Date consulted: 2026-11-17 UTC. Direct requests to the matching Apple Music storefronts returned HTTP 200. Each page's serialized playlist data exposes 100 consecutive `rankingText` positions, and every song URL uses its chart-market storefront.

| Market | Official Apple Music page | Ranked positions | Source-page SHA-256 |
|---|---|---:|---|
| Germany | [Top Songs 2019: Deutschland](https://music.apple.com/de/playlist/top-songs-of-2019-germany/pl.c6758547290847fc9a2ee49a56e79171) | 1–100 | `0ab98d67b072dc2bb7870b0573fbaf0276e35e9ad742a4e68e336b4a846ed1d9` |
| France | [Les meilleurs titres de 2019 : France](https://music.apple.com/fr/playlist/top-songs-of-2019-france/pl.edf89c316d114195886568ea5182300b) | 1–100 | `3d6fa381f3ef1e1c9a1872f8e14cf0dc05fb0b8f40a63cd54edbae8e776ee286` |
| Mexico | [Top canciones de 2019: México](https://music.apple.com/mx/playlist/top-songs-of-2019-mexico/pl.960e4515a85442acadcc442b56d186b5) | 1–100 | `c8385e94f099636598a9c18674f0444e72724a41d9a8738cda12809d3fcc163b` |

The response bodies and ranked rows are preserved in `apple-music-de-2019-annual`, `apple-music-fr-2019-annual`, and `apple-music-mx-2019-annual` under [`provider_series`](../data/derived/annual_revision/provider_series/). Exact chart period bounds are not stated, so the packets keep `period_start` and `period_end` null. These are separate Apple Music series and are not merged into the Spotify/YouTube selection.
