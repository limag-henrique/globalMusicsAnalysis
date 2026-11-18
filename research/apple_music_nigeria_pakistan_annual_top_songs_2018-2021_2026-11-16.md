# Apple Music Nigeria and Pakistan annual Top Songs (2018–2021)

Date consulted: 2026-11-16 UTC. This note checks first-party Apple Music pages for the missing Nigeria (`NG`) and Pakistan (`PK`) country/year cells. It records only Apple Music source evidence; no chart packets or project data were changed.

## Findings

| Market / year | Apple Music page | Playlist label and depth | Published at | Track metadata |
|---|---|---|---|---|
| NG 2020 | [Top Songs of 2020: Nigeria](https://music.apple.com/ng/playlist/top-songs-of-2020-nigeria/pl.0c68e46213554381b4b9f5afaba7699f) | `Apple Music African`; 100 songs | 2020-11-12T21:12:39Z | Full ordered list of 100 tracks and 100 unique numeric Apple Music song IDs are present in the page's structured data. |
| NG 2021 | [Top Songs of 2021: Nigeria](https://music.apple.com/ng/playlist/top-songs-of-2021-nigeria/pl.3771c53436734784955bb4e0ecd95b4f) | `Apple Music`; 100 songs | 2021-11-30T02:08:26Z | Full ordered list of 100 tracks and 100 unique numeric Apple Music song IDs are present in the page's structured data. |
| PK 2018–2021 | No Pakistan-specific annual Top Songs playlist was located in Apple Music search results for any of these four years. | — | — | No corresponding ordered track list or Apple song IDs available from a PK annual page found in this lookup. |
| NG 2018–2019 | No Nigeria-specific annual Top Songs playlist was located in Apple Music search results for either year. | — | — | No corresponding country-page track list or Apple song IDs available from a Nigeria annual page found in this lookup. |

Apple's 2021 Nigeria page describes the playlist as its “most-played songs of the year in Nigeria.” Both Nigeria pages publish a year in the title, but neither states the exact listening-period start and end dates; the timestamps above are Apple's page `datePublished` values, not measurement-window boundaries. The 2020 page's displayed publisher label is `Apple Music African`; its structured playlist author is Apple Music.

The Apple playlist structured data exposes each ordered track as a `MusicRecording` with a song URL ending in its numeric Apple Music catalog ID. The first three 2020 entries are “Bad Influence,” “Vibration,” and “Again”; the last is “No Stress.” The first three 2021 entries are “Essence (feat. Tems),” “Ginger (feat. Burna Boy),” and “Bounce”; the last is “Fade (feat. Bella Shmurda).”

## Checking the earlier years and Pakistan

Exact-title searches on Apple Music's Nigeria storefront did not return country-specific `Top Songs of 2018: Nigeria` or `Top Songs of 2019: Nigeria` playlists. The 2019 search does surface a [regional Top Songs of 2019: Sub Saharan Africa playlist](https://music.apple.com/ng/playlist/top-songs-of-2019-sub-saharan-africa/pl.331cfc7a801a48fea654bf2c5377da52) with 99 songs; its title identifies a regional market, so it is not evidence for the Nigeria cell.

Exact-title searches on Apple Music's Pakistan storefront did not surface Pakistan-specific annual pages for 2018, 2019, 2020, or 2021. This is a bounded finding from the current Apple Music search results, not proof that Apple never published an unindexed or removed page.

## Primary sources

- Apple Music — [Top Songs of 2020: Nigeria](https://music.apple.com/ng/playlist/top-songs-of-2020-nigeria/pl.0c68e46213554381b4b9f5afaba7699f)
- Apple Music — [Top Songs of 2021: Nigeria](https://music.apple.com/ng/playlist/top-songs-of-2021-nigeria/pl.3771c53436734784955bb4e0ecd95b4f)
- Apple Music Nigeria search — [Top Songs of 2018 Nigeria](https://music.apple.com/ng/search?term=Top%20Songs%20of%202018%20Nigeria)
- Apple Music Nigeria search — [Top Songs of 2019 Nigeria](https://music.apple.com/ng/search?term=Top%20Songs%20of%202019%20Nigeria)
- Apple Music Pakistan search — [Top Songs of 2018 Pakistan](https://music.apple.com/pk/search?term=Top%20Songs%20of%202018%20Pakistan)
- Apple Music Pakistan search — [Top Songs of 2019 Pakistan](https://music.apple.com/pk/search?term=Top%20Songs%20of%202019%20Pakistan)
- Apple Music Pakistan search — [Top Songs of 2020 Pakistan](https://music.apple.com/pk/search?term=Top%20Songs%20of%202020%20Pakistan)
- Apple Music Pakistan search — [Top Songs of 2021 Pakistan](https://music.apple.com/pk/search?term=Top%20Songs%20of%202021%20Pakistan)
- Apple Music — [Top Songs of 2019: Sub Saharan Africa](https://music.apple.com/ng/playlist/top-songs-of-2019-sub-saharan-africa/pl.331cfc7a801a48fea654bf2c5377da52)

## Nigeria playlist captures

On 2026-11-17 UTC, the official Nigeria playlist pages were captured locally as independent Apple Music series:

- `APPLE_MUSIC_TOP_SONGS_NG_2020`: 100 published positions, 100 distinct Apple Music song IDs.
- `APPLE_MUSIC_TOP_SONGS_NG_2021`: 100 published positions, 100 distinct Apple Music song IDs.

For each page, Apple's `serialized-server-data` track list exposes positions 1–100 and native song IDs. Those IDs and their order were cross-checked against the page's JSON-LD playlist track array before writing the ranking rows. The source HTML, manifest, and `rankings.jsonl` are stored under `data/derived/annual_revision/provider_series/apple-music-ng-2020-annual/` and `data/derived/annual_revision/provider_series/apple-music-ng-2021-annual/`. The exact measurement windows remain null because the pages do not state start or end dates. These remain provider-specific Apple Music series and are not merged into Spotify/YouTube positions.
