# Apple Music Japan Top Songs of 2018

Retrieved: 2026-11-17T06:28:36Z (UTC)

## Finding

Apple Music’s first-party [Japan playlist, “2018年トップソング100：日本”](https://music.apple.com/jp/playlist/2018%E5%B9%B4%E3%83%88%E3%83%83%E3%83%97%E3%82%BD%E3%83%B3%E3%82%B0100-%E6%97%A5%E6%9C%AC/pl.fdb5f070258048afbbb8d3f033de5db2) explicitly identifies the series as its 100 most-played songs in Japan during 2018. The official page declares 100 tracks. The playlist page’s JSON-LD contains 100 ordered recording rows; its serialized page data contains 100 unique JP-storefront song records in the same ID and title order. The page’s `music:song:track` metadata labels ranks 1 through 100. All 100 native song IDs are distinct, and every row has a title and artist credit. The playlist metadata reports `datePublished=2018-11-29T17:40:36Z`; that is the page’s publication timestamp and does not establish chart-period boundaries.

## Series treatment

- Provider: Apple Music (`APPLE_MUSIC`); publisher jurisdiction: United States (`US`).
- Chart market: Japan (`JP`), based on the playlist title and description, captured through Apple’s JP storefront.
- Published/recovered depth: 100 ranked memberships, ranks 1–100; no published gaps or ties.
- Exact period start/end and numeric play counts: not stated; stored as null.
- Provider song IDs and positions remain in this separate Apple Music series and are not merged into the Spotify/YouTube 150,000-position selection.

## Capture and validation

- HTTP status: 200; response bytes: 719424.
- Source SHA-256: `50f9e1d90c502b7885c7f374d2f14e42e5185ff93e265519ad7c8c00736ccc34`.
- The serialized track IDs and titles were checked against the official playlist JSON-LD array; rank labels were checked against `music:song:track` metadata.
- Packet: `data/derived/annual_revision/provider_series/apple-music-jp-2018-annual/`.
- Packet files: `manifest.json`, `rankings.jsonl`, and `source-page.html`.
- `rankings.jsonl` SHA-256: `6f7bb29122ea498643222b3f2c8a4e56e141794efb2ac1f5834331aae92af1a2`.

No song-to-audio lyric verification is implied by this ranking capture.
