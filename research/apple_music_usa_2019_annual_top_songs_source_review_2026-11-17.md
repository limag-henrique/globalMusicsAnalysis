# Apple Music US annual Top Songs 2019 source review

Audit date: 2026-11-17.

## Finding

Apple Music publishes a US-specific [Top Songs of 2019: USA playlist](https://music.apple.com/us/playlist/top-songs-of-2019-usa/pl.423d870bc29942aaa767ea0bf2c4aacc). Apple’s page identifies “Old Town Road” as its biggest song of 2019 and reports 100 songs. The source labels an annual playlist but does not expose exact chart-window boundaries or a complete methodology statement. The packet therefore records reporting year 2019 and leaves period_start and period_end unset.

The official US storefront page returned HTTP 200 on 2026-11-17. Its serialized-server-data contains rank labels 1–100; its schema:music-playlist JSON-LD declares 100 tracks. Every rank label matched the same-order JSON-LD title and US-storefront song ID. The recovered list has 100 unique Apple Music song IDs. The playlist publication date is 2019-11-21T21:24:04Z; it is not treated as the chart-period end date.

## Preserved evidence and packet

- Raw capture directory: data/raw/national_charts/apple_music_us_2019/
- Provider packet: data/derived/annual_revision/provider_series/apple-music-us-2019-annual/
- Source body SHA-256: 7f7c3b357cc6fdfd349b89cbb7d05c2ec6a6468b5da8b830bfa068577dd120a8
- Raw extracted-rank JSONL SHA-256: 3375d67f91e7989e0aae5ebd606f271b96e5efdad4d69712afd7acfd658cbf8c
- Standardized ranking JSONL SHA-256: f1cc49d547d550e69a74e11f51b57774c83c5e871709f36b498fc1626e5f3b3b
- Packet manifest SHA-256: b655ec5889722b2889082450383e22837fdd59c02259040b5b58dea12ef0b67c
- Capture retrieval time: 2026-11-17T16:28:38Z

The source page body, response headers, capture manifest, rank extraction, and byte-identical packet copy are retained locally. The packet assigns positions 1–100 from Apple’s serialized rank labels and records the matching native song IDs, titles, artist credits, album titles, and durations. No score values were published in the captured page.

## Provider handling and import

The series is APPLE_MUSIC_TOP_SONGS_US_2019 with provider_code APPLE_MUSIC, chart_market_code US, and 100 published positions. It remains separate from the Spotify/YouTube core selection and from every other provider’s positions. This source does not fill any of the 150,000 core positions.

The v32 supplemental snapshot contains 334 provider series and 38,099 ranked memberships; its denominator report totals 29,963 known reported-depth positions with 26 series whose depth remains unknown. The catalog has 18,992 normalized identity keys, which are not adjudicated canonical songs. At v32, Apple Music contributed 286 series and 28,587 ranked memberships. The v31 catalog, report, index, and active-index copy were preserved under data/runtime/supplemental-provider-snapshot-history-20261117-v31/ before promotion. All v31 series and memberships, and existing song rows, compare equal in v32; v32 adds this one series, 100 memberships, and 27 net normalized identity keys. SQLite quick_check is ok and foreign_key_check returns zero rows.

The subsequent v33 snapshot adds the separate Apple Music Top 100 Songs 2018: USA series. Its 100 positions come from the ordered playlist sequence because Apple prints no numeric rank labels; that limitation is recorded in the packet’s published_rank values and source review. V33 has 335 series, 38,199 ranked memberships, 30,063 known reported-depth positions, 26 unknown-depth series, and 19,052 normalized identity keys. The complete v32 snapshot is preserved under data/runtime/supplemental-provider-snapshot-history-20261117-v32/.

The Spotify/YouTube core remains at 69,032 of 150,000 observed memberships, with 80,968 positions missing across 1,555 cells lacking a verified annual source and 72 unresolved-quota cells. These Apple Music series are supplemental evidence and do not reduce that gap.

