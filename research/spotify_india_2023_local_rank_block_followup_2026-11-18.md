# Spotify Wrapped Mapped 2023: India list binding follow-up

**Disposition:** the India label-to-list association is verified and five positions are recovered. The source remains review-only for a completed 2023 annual series because it gives no period end date and no ranking formula.

## Finding

Spotify’s 29 November 2023 article describes local streaming trends and says the map highlights the top songs that have sounded 2023 “since January 1.” It also instructs readers to click a map box to view a city or market’s listening habits. The article does not state when the period ends or how the songs are ranked. ([Spotify Newsroom article](https://newsroom.spotify.com/2023-11-29/wrapped-top-songs-worldwide-map/); immutable captured HTML SHA-256 `20e56da774c937110ccdf05d69c9920227a24aad30db5ae3d368c173d4a67510`.)

The static embed had separate sequences of 87 market labels and 87 five-row song blocks, so sequence order alone did not establish which block belonged to India. This follow-up rendered the captured Spotify embed, generated Hype script, runtime, and map assets locally. After navigating to Asia, expanding it, and selecting the India market box, the rendered panel showed **“Top Songs in India”** above five numbered songs. That interaction directly resolves the label-to-list binding. The local screenshot and concise state record are in the [packet’s render evidence](../data/runtime/spotify-india-2023-local-rank-block-followup-20261118-01/render-evidence/spotify-india-rendered.png) and [rendered-state.json](../data/runtime/spotify-india-2023-local-rank-block-followup-20261118-01/rendered-state.json).

## Recovered India positions

| Rank | Song | Artist |
| ---: | --- | --- |
| 1 | Maan Meri Jaan | King |
| 2 | Kahani Suno 2.0 | Kaifi Khalil |
| 3 | Kesariya | Pritam |
| 4 | Malang Sajna | Sachet Tandon |
| 5 | Cheques | Shubh |

## Rank and period accounting

- **Provider and series:** Spotify Wrapped Mapped 2023, local-market song list; India (`IN`). The visible heading is “Top Songs in India.” The official page describes the feature as local streaming trends, not as a separately titled Spotify chart product. ([Article](https://newsroom.spotify.com/2023-11-29/wrapped-top-songs-worldwide-map/); [embedded map](https://newsroom.spotify.com/wp-content/themes/ftr/assets/animations/wrapped2023/WRAPPEDMAPPEDV8/WRAPPEDMAPPEDV8.html).)
- **Published depth:** five rows in the selected India panel.
- **Recovered positions:** 1–5, all explicitly numbered in the rendered panel.
- **Ties and gaps:** no tied rank or missing rank is displayed within 1–5. Spotify states no tie or gap policy.
- **Positions beyond the displayed block:** not provided; no larger list depth is stated.
- **Period:** starts 2023-01-01 by the article’s “since January 1” wording. The end date is unstated, so full-calendar-year coverage is unverified. The article itself identifies a 2023 feature and was published 2023-11-29.
- **Method:** the article refers to local streaming trends and top songs. It provides no counting window end, metric, weighting, or ranking formula.
- **Qualification:** review-only for annual-series use. The market/list binding and five displayed ranks are resolved, but the period and method do not establish a completed calendar-year ranking.

## Evidence and limits

The map interaction was replayed against local copies of Spotify’s captured embed and its referenced first-party Hype script/runtime and image assets; no live page was used for the final render. A third-party clipping helper was omitted from the local preview to avoid an external request. The rendered screenshot is therefore a reproducible local render of captured source assets, not a screenshot captured from Spotify’s live page. The binding is also supported by Spotify’s own instruction to click market boxes and by the resulting India heading and numbered rows.

The targeted follow-up made five serial unauthenticated public GET requests for dependencies explicitly referenced by the captured embed/script. It did not re-fetch the immutable article or embed, and it did not modify the active index, catalogs, or core selection. Request details, raw-source hashes, immutable-input verification, position accounting, and packet checksums are recorded in `data/runtime/spotify-india-2023-local-rank-block-followup-20261118-01/`.

### Primary sources

- [Spotify Newsroom: Wrapped Mapped: Top Songs Streamed Around the World](https://newsroom.spotify.com/2023-11-29/wrapped-top-songs-worldwide-map/)
- [Spotify embedded Wrapped Mapped V8 HTML](https://newsroom.spotify.com/wp-content/themes/ftr/assets/animations/wrapped2023/WRAPPEDMAPPEDV8/WRAPPEDMAPPEDV8.html)
- [Spotify Hype generated script referenced by the embed](https://newsroom.spotify.com/wp-content/themes/ftr/assets/animations/wrapped2023/WRAPPEDMAPPEDV8/WRAPPEDMAPPED%20V8.hyperesources/wrappedmappedv8_hype_generated_script.js?56002)
