# Pakistan annual chart source audit (2018–2025)

Date consulted: 2026-11-17. Scope: primary/official publisher evidence for Pakistan-market annual song rankings, with emphasis on 2018 and coverage through 2025. The purpose was source discovery only. No active supplemental catalog/index, core selection, or canonical lyrics catalog was changed.

## Finding

No complete, ranked annual Pakistan song series could be verified from an accessible official source in this pass. The strongest candidate is Popnable's official Pakistan Top 40 year-end series: its official index advertises year-end charts for 2018–2025 and describes them as songs popular at year end, but every tested direct year page and index route returned a Cloudflare HTTP 403 challenge. A web open of the 2018 localized page returned HTTP 503. No chart rows were transcribed from search snippets or challenge bodies.

Spotify has two useful but limited Pakistan-specific records. Its official 2022 article says “Pasoori” was the most-streamed Pakistani song on Spotify for 2022 and quotes Shae Gill describing it as the top track for Pakistan; this supports a narrow rank-1 claim, but not a complete annual chart, and the article does not fully define whether “Pakistani song” denotes artist/song origin or the listening market. Spotify's 2023 Wrapped Mapped embed contains a panel label “Top Songs in Pakistan,” but the static generated bundle contains multiple five-track blocks and the heading-to-list mapping is ambiguous. The existing Bangladesh extraction audit explicitly records that market assignments beyond Bangladesh must not be inferred from block order. I therefore leave both records outside a Pakistan ranked series pending clearer publisher evidence.

The pre-existing Apple Music note was reviewed first: it found no Pakistan-specific Apple Music annual Top Songs playlist for 2018–2021 in its bounded search, and states this is not proof that no page existed. See [the existing Apple Music search note](apple_music_nigeria_pakistan_annual_top_songs_2018-2021_2026-11-16.md).

## Year coverage

| Year | Verified Pakistan-market annual ranking? | Evidence and limitation |
|---:|---|---|
| 2018 | No | Popnable's official index lists “Pakistan Year-End 2018,” but its direct year page was blocked on ordinary retrieval. The indexed official localized page result exposed a title with `01/01/2018–31/12/2018`; the underlying official body could not be retrieved, so neither that period nor its ranked rows is recorded as verified. Apple Music's prior 2018–2021 search found no Pakistan annual playlist. |
| 2019 | No | Popnable's index lists a 2019 year-end chart; its direct page returned HTTP 403. No ranked body was captured. Apple Music's prior search found no Pakistan annual playlist for 2019. |
| 2020 | No | Popnable's index lists a 2020 year-end chart; its direct page returned HTTP 403. No ranked body was captured. Apple Music's prior search found no Pakistan annual playlist for 2020. |
| 2021 | No | Popnable's index lists a 2021 year-end chart; its direct page returned HTTP 403. Spotify's official Pakistan article says the service launched in Pakistan in 2021, but no official public Pakistan annual ranked list for 2021 was located. Apple Music's prior search found no Pakistan annual playlist for 2021. |
| 2022 | No complete list verified | Spotify's official 2023 article says “Pasoori” was the most-streamed Pakistani song on Spotify for 2022 and quotes the artist calling it the top track for Pakistan. This is rank-1-only evidence with ambiguous category/market wording; no ranked list, list depth, or exact listening-period boundaries are supplied. Popnable's 2022 page was blocked. |
| 2023 | No | Spotify's official Wrapped Mapped source labels a Pakistan panel and the article says the map covers top songs that “since January 1” soundtracked 2023. However, the static embed's multiple chart blocks cannot be uniquely tied to the Pakistan heading from the generated source alone. Candidate lists include both “Maan Meri Jaan / Kahani Suno 2.0 / Kesariya / Malang Sajna / Cheques” and “Kahani Suno 2.0 / Iraaday / Bikhra / Siyah / Pasoori”; neither is recorded as Pakistan ranks without a verified live panel mapping. The article does not state the period end. Popnable's 2023 page was blocked. |
| 2024 | No | Popnable's 2024 page was blocked. Spotify's 2024 Wrapped media kit lists global and U.S. top-song assets; Spotify's official 2024 global celebrations article mentions a Pakistan Wrapped event but publishes no Pakistan annual song ranking. |
| 2025 | No | Popnable's 2025 page was blocked. Spotify's public 2025 year-end article states that its full published top lists are global and U.S.; no Pakistan national list was located. |

## Official routes tested

Popnable's official index says Pakistan's Top 40 charts are ranked weekly, monthly, and yearly, and its year-end index labels itself “Top 40 of most popular songs at the end of the years.” The index displayed year-end entries for 2018–2025. The following official routes were tested with ordinary unauthenticated HTTP GETs on 2026-11-17; all returned Cloudflare 403 responses:

- `https://popnable.com/pakistan/charts/top-40/year-2018` through `.../year-2025` (each year tested individually)
- `https://popnable.com/pakistan/charts`
- `https://popnable.com/pakistan/charts/top-40`
- `https://su.popnable.com/pakistan/grafik-musik/top-40/taun-2018` (official localized route)

The Popnable year pages were not accessed by solving the Cloudflare challenge. Their raw 403 response bodies and per-request status, byte count, final URL, timestamp, Cloudflare Ray ID, and SHA-256 are preserved in [the raw capture manifest](../data/raw/national_charts/pakistan_annual_sources_audit_2026-11-17/capture_manifest.json). A web open of the Popnable 2018 localized result also returned HTTP 503.

The official Popnable index is [Pakistan Top 40 charts](https://popnable.com/pakistan/charts/top-40). The official category index is [Pakistan charts](https://popnable.com/pakistan/charts). These pages establish that a publisher-specific annual series is advertised; their search-indexed summaries are not used as ranked observations.

## Spotify source checks

- Spotify's official [2022 Pasoori article](https://newsroom.spotify.com/2023-02-15/pakistani-artist-shae-gill-breaks-streaming-records-with-viral-hit-pasoori/) gives a single rank-1 statement, but not a complete national Top Songs list. The successfully retrieved raw article is saved in the raw capture directory with SHA-256 and retrieval metadata in `capture_manifest.json`.
- Spotify's official [2023 Wrapped Mapped article](https://newsroom.spotify.com/2023-11-29/wrapped-top-songs-worldwide-map/) says the interactive map highlights local streaming trends and top songs since January 1, 2023. The embedded chart is [here](https://newsroom.spotify.com/wp-content/themes/ftr/assets/animations/wrapped2023/WRAPPEDMAPPEDV8/WRAPPEDMAPPEDV8.html). Existing captures of the official article, embed, and generated script are preserved in `data/derived/annual_revision/provider_series/spotify-wrapped-mapped-bd-2023-top5/`; the script SHA-256 is `cd9525dd31166599c7ea4ab4c9bc3151b81c90693cd83bea8cc8287e4ecfc0f0` (11,824,012 bytes, retrieved 2026-11-17T02:12:52Z). The existing [Bangladesh audit](spotify_bangladesh_wrapped_mapped_2023_annual_top_songs_2026-11-16.md) records the map-label/block-order ambiguity for markets beyond Bangladesh. No Pakistan chart rows were copied from that candidate source.
- Spotify's official [2024 Wrapped media kit](https://newsroom.spotify.com/media-kit/2024-wrapped/) exposes global and U.S. song lists. Its [2024 global celebrations article](https://newsroom.spotify.com/2024-12-06/go-inside-the-global-celebrations-for-spotifys-biggest-wrapped-yet/) mentions a Pakistan Wrapped event but not a Pakistan song ranking.
- Spotify's official [2025 top lists article](https://newsroom.spotify.com/2025-12-03/wrapped-top-artists-songs-albums-podcasts-audiobooks/) describes its full published lists as global and U.S.; it does not supply a Pakistan annual chart.

## Disposition

Leave Pakistan annual series unfilled for 2018–2025. Do not infer rows from search snippets, blocked publisher pages, a single 2022 rank-1 assertion, or static ordering of the 2023 interactive embed. Keep Spotify, Popnable, YouTube, and any other publisher positions as independent series if a verifiable full source is later obtained. A follow-up can resume if Popnable serves its page body or the Spotify interactive map's Pakistan panel can be verified through an unambiguous rendered state.
