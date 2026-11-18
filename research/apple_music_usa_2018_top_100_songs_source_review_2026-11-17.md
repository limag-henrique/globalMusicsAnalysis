# Apple Music US Top 100 Songs 2018: source review

Review date: 2026-11-17.

## Finding

Apple's first-party United States storefront has a playlist titled **Top 100 Songs 2018: USA**. The [Apple Music playlist](https://music.apple.com/us/playlist/top-100-songs-2018-usa/pl.35df5bcc4c3e4dccbe902e70bfeded69) reports 100 songs. Its captured page contains 100 ordered serialized track records; the ordered JSON-LD `MusicPlaylist.track` sequence has 100 entries and matches the serialized list on every title and Apple song ID. All track URLs resolve under Apple's `/us/` storefront and all 100 IDs are unique.

The page does **not** embed numeric rank labels (`rankingText` is absent); it exposes list order only. A 1–100 ordinal could therefore be assigned from the playlist sequence, but those numbers would be derived from order rather than publisher-printed rank labels. Preserve this limitation if a provider packet is later created. The exact annual chart window is not stated. Keep `period_start` and `period_end` unset; `datePublished` is playlist publication metadata, not a chart-window boundary.

## Source capture and verification

- Official page: <https://music.apple.com/us/playlist/top-100-songs-2018-usa/pl.35df5bcc4c3e4dccbe902e70bfeded69>
- Page title: `Top 100 Songs 2018: USA`
- Apple page metadata: Listen to the Top 100 Songs 2018: USA playlist on Apple Music. 100 Songs. Duration: 5 hours 47 minutes.
- Playlist publication timestamp: `2018-11-29T18:56:11Z`
- Retrieval: HTTP 200, `text/html`, 692,171 bytes, retrieved 2026-11-17T16:38:32Z
- Captured page SHA-256: `f68d67728af48291945057c9e4150f0b6f0b97cee56b69f4c23e1529ae5da003`
- Extracted ordered rows: 100; unique US-storefront Apple song IDs: 100
- Ordered track comparison: 100/100 serialized track IDs and titles match the schema.org playlist sequence
- Rank labels: none embedded; order is preserved as source sequence
- Raw capture directory: `data/raw/national_charts/apple_music_us_2018/`
- Extracted track-order JSONL SHA-256: `4f5a513c63a660e944439ffe8ac910602c042cce9bb2793be48f9706e4ba0fe3`
- Capture manifest SHA-256: `24b0e3b6dc5806e53de730b6174c6c8a8b78ec87e17a4a0e5ff10de570b2781e`

At the time of the source review, no provider packet, catalog import, or index update had been made. The subsequent additive packet and import are recorded below.

## Packet and additive import

The provider packet is data/derived/annual_revision/provider_series/apple-music-us-2018-annual/. It stores positions 1–100 as 1-based playlist-order ordinals. Because Apple prints no numeric rank labels, each published_rank field is explicitly marked playlist_order:<n>; the positions must not be described as numeric labels printed on the page. Exact chart-window boundaries remain unknown.

- Standardized ranking JSONL SHA-256: 858b69596aae0b544ba609fdf8d3557b8fc970d98b58e746d2e21228ebf12c0a
- Packet manifest SHA-256: 290c09f42f6a2ded562c463892de53d3647ae77278a6c156b2f2d0610dd4bd8c
- Series: APPLE_MUSIC_TOP_SONGS_US_2018, with 100 distinct local Apple song IDs
- Supplemental snapshot v33: 335 series and 38,199 ranked memberships; 30,063 known reported-depth positions, 26 unknown-depth series, and 19,052 normalized identity keys
- Apple Music subtotal: 287 series and 28,687 ranked memberships
- v33 database SHA-256: ecd0c457aaa967a8d2948d6bcadb706da865a1725da72f5a599efb4610107b8d
- v33 denominator report SHA-256: b303a554dd87c16f8daa8c75adf60fc7f1f53fc9e8571db595ebf7d77a6c13e8
- v33 active index SHA-256: c7578bdf9c4880fbc5533ccb8ba7305d5219580a4e8bef1eb3ece4af5a56d46e

The exact v32 catalog, report, index, active-index copy, import output, and packet order are preserved at data/runtime/supplemental-provider-snapshot-history-20261117-v32/. All v32 series, memberships, and existing song rows compare equal in v33. The importer verified packet hashes; SQLite quick_check is ok and foreign_key_check returns zero rows.

This Apple Music series remains separate from the Spotify/YouTube core. The core still has 69,032 of 150,000 planned memberships observed and 80,968 missing.
