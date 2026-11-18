# Apple Music Tanzania annual Top Songs (2024–2025)

Date consulted: 2026-11-17 UTC. This note records two Apple Music year-end playlist series for Tanzania as separate provider-specific rankings. They are not merged with Spotify, YouTube, CAVCA, or other chart positions.

## Scope and periods

Apple Music labels both playlists as end-of-year charts based on plays over a rolling November-to-October period. The published periods are not calendar years, so the source dates are retained exactly:

| Series | Positions | Period stated by Apple Music |
|---|---:|---|
| Top Songs of 2024: Tanzania | 100 | 2023-11-01 to 2024-10-31 |
| Top Songs of 2025: Tanzania | 100 | 2024-11-01 to 2025-10-31 |

The playlist title supplies the Tanzania chart-market tag (`TZ`). Apple Music does not publish numeric play counts on these playlist pages; scores remain null. Each year has a distinct series ID and its own 100-position denominator.

## Local evidence and validation

Each official playlist page is saved as `source-page.html` beside its `rankings.jsonl` and `manifest.json` in `data/derived/annual_revision/provider_series/apple-music-tz-<year>-annual/`. Positions and song metadata were extracted in the serialized page-data order. The captured pages identify 100 tracks each; local checks confirmed consecutive positions 1–100, unique Apple Music song IDs within each year, null scores, and source-page hash agreement with every ranking row and manifest.

- 2024 rankings SHA-256: `0cd77e7fea3d5bdd6a795aa23e38478065ef120f5047695e93326f9d3286cd1b`
- 2025 rankings SHA-256: `7c0f54f36b3875bb144725b23007ffa1d20eafd79ae78218372ce964aa640c47`

## Primary sources

- [Apple Music — Top Songs of 2024: Tanzania](https://music.apple.com/us/playlist/top-songs-of-2024-tanzania/pl.829114e39979400fbf65d0176d0f9772)
- [Apple Music — Top Songs of 2025: Tanzania](https://music.apple.com/us/playlist/top-songs-of-2025-tanzania/pl.f03421d314de4ce58cf983d6632c2433)

These are complementary Apple Music provider series; they do not fill or overwrite positions in the current 150,000-position Spotify/YouTube selection.
