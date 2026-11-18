# Apple Music India Top Songs of 2018

Retrieved: 2026-11-17T06:57:18Z (UTC)

## Finding

Apple Music's first-party [India playlist, “Top 100 Songs 2018: India”](https://music.apple.com/in/playlist/top-100-songs-2018-india/pl.7df4aa48d58c4689bad274bfe7c54cce) identifies an annual India series for 2018. The India storefront page reports **99 songs**, and its `music:song:track` metadata explicitly assigns ranks 1–99. The page's JSON-LD contains 99 recordings; the serialized playlist has 99 unique native song IDs and artist credits, and titles and IDs align with the JSON-LD and rank metadata. Apple gives a `datePublished` timestamp of `2018-11-29T17:59:35Z`; this is the playlist publication date, not a chart-period boundary.

The title says “Top 100” while the page's stated count is 99. Because these first-party depth signals conflict, reported depth is stored as unknown. The packet includes only ranks 1–99; no missing position or 100th entry is inferred. Exact period dates and numeric scores are not stated.

## Series treatment

- Provider: Apple Music (`APPLE_MUSIC`); publisher country: US, following the project's Apple Music publisher convention.
- Chart market: India (`IN`), based on the localized playlist title and India storefront page.
- Captured rows: 99, explicit ranks 1–99; reported depth unknown because of the title/count conflict.
- The Apple Music series remains separate from the Spotify/YouTube selection.

## Capture and validation

- HTTP status: 200; response bytes: 713574.
- Source SHA-256: `ac89a2b1f87ce39a71a771934ee05e2b66d44a5c67c0e42ddce7dc17f565db93`.
- JSON-LD tracks, `music:song` metadata URLs, rank metadata, and serialized playlist entries each yield 99 records; native IDs are unique and titles agree across structures.
- Packet: `data/derived/annual_revision/provider_series/apple-music-in-2018-annual/`.
- `rankings.jsonl` SHA-256: `e8bb85613b45e605018123b60344a4e429bf37d3a842f6903834449584140ca5`.

No lyric-to-audio identity verification is implied by this chart capture.
