# Bangladesh annual chart source check (2018–2026)

Date consulted: 2026-11-16. Scope: first-party/official national-market annual song rankings for Bangladesh (`BD`), 2018–2025, and whether a 2026 annual source is published yet. A publisher's country and the chart's listening market are tracked separately. No selection, catalog, or code was changed.

## Finding

One fully verifiable Bangladesh-market annual ranking was found: Spotify Wrapped Mapped's 2023 **Top Songs in Bangladesh** list. It is a Spotify-published market chart, not a Bangladesh-publisher chart. The Spotify AB company contact page identifies Spotify AB in Stockholm and says it provides Spotify to all markets outside the United States; the interactive Wrapped map separately labels the chart market Bangladesh. Record these independently as `publisher_country=SE` and `chart_market=BD`. ([Spotify contact/entity page](https://www.spotify.com/se/about-us/contact/); [Spotify's 2023 Wrapped Mapped article and embedded chart](https://newsroom.spotify.com/2023-11-29/wrapped-top-songs-worldwide-map/))

The chart is explicitly annual in Spotify's 2023 Wrapped context: the article calls it local streaming trends and says it shows the top songs that, “since January 1,” soundtracked 2023. The interactive chart labels the Bangladesh panel **Top Songs in Bangladesh** and shows five ordered entries. The published end date is not stated, so do not assume a complete January–December period. The page gives ranks, but no stream counts or detailed ranking formula. ([Spotify 2023 Wrapped Mapped](https://newsroom.spotify.com/2023-11-29/wrapped-top-songs-worldwide-map/); [embedded map](https://newsroom.spotify.com/wp-content/themes/ftr/assets/animations/wrapped2023/WRAPPEDMAPPEDV8/WRAPPEDMAPPEDV8.html))

### Spotify Wrapped Mapped — Bangladesh, 2023

| Rank | Song | Artist |
|---:|---|---|
| 1 | Seven (feat. Latto) | Jung Kook |
| 2 | Kahani Suno 2.0 | Kaifi Khalil |
| 3 | Choo Lo | The Local Train |
| 4 | Iraaday | Rovalio |
| 5 | Maan Meri Jaan | King |

The map's Bangladesh panel was opened from Spotify's official page. The five positions and track links are visible in the official interactive embed; this is a five-entry list, not a complete Top 50/100. Do not invent a score field or missing positions. Preserve this as its own provider/category series and keep its ranks separate from other publishers' charts.

## Year-by-year coverage

| Year | First-party Bangladesh-market annual ranking verified? | Evidence and exact gap |
|---:|---|---|
| 2018 | No | Spotify did not launch in Bangladesh until its February 2021 market expansion. No other Bangladesh-market annual ranking was verified in the inspected official sources. ([Spotify's 2021 market expansion](https://newsroom.spotify.com/2021-02-22/spotify-expands-international-footprint-bringing-audio-to-80-new-markets/)) |
| 2019 | No | Same gap as 2018: before Spotify's Bangladesh launch; no other official Bangladesh annual ranking verified. ([Spotify's 2021 market expansion](https://newsroom.spotify.com/2021-02-22/spotify-expands-international-footprint-bringing-audio-to-80-new-markets/)) |
| 2020 | No | Same gap as 2018: before Spotify's Bangladesh launch; no other official Bangladesh annual ranking verified. ([Spotify's 2021 market expansion](https://newsroom.spotify.com/2021-02-22/spotify-expands-international-footprint-bringing-audio-to-80-new-markets/)) |
| 2021 | No | Spotify's official year-end article publishes global and U.S. top lists, with no Bangladesh category. No other official Bangladesh annual ranking verified. ([Spotify 2021 Wrapped top lists](https://newsroom.spotify.com/2021-12-01/what-the-world-streamed-most-in-2021/)) |
| 2022 | No | Spotify's official year-end article publishes global and U.S. lists, with no Bangladesh category. No other official Bangladesh annual ranking verified. ([Spotify 2022 Wrapped top lists](https://newsroom.spotify.com/2022-11-30/the-top-songs-artists-podcasts-and-listening-trends-of-2022/)) |
| 2023 | **Yes — Spotify Wrapped Mapped** | Bangladesh **Top Songs**, 5 ranked tracks; source says the listening period began January 1, but gives no end date or detailed rank formula. ([official article and embed](https://newsroom.spotify.com/2023-11-29/wrapped-top-songs-worldwide-map/)) |
| 2024 | No | Spotify's official media kit identifies global and U.S. song lists, with no Bangladesh annual chart. No other official Bangladesh annual ranking verified. ([Spotify 2024 Wrapped media kit](https://newsroom.spotify.com/media-kit/2024-wrapped/)) |
| 2025 | No | Spotify's official year-end article says its full published top lists are global and U.S.; no Bangladesh list is published there. No other official Bangladesh annual ranking verified. ([Spotify 2025 Wrapped top lists](https://newsroom.spotify.com/2025-12-03/wrapped-top-artists-songs-albums-podcasts-audiobooks/)) |
| 2026 | No completed annual source verified as of 2026-11-16 | The calendar year was still in progress on the consultation date, and no Bangladesh-specific annual source was located. Treat as pending, not as a complete-year chart. |

## Source audit and limitations

- YouTube's current official Charts & Insights help page lists supported chart locations and does not include Bangladesh. It describes song and video charts as daily or weekly, so this page does not supply an official annual Bangladesh chart for the requested years. This is a current availability check, not proof that no historical page ever existed. ([YouTube Charts & Insights](https://support.google.com/youtube/answer/9014376?hl=en))
- The inspected Spotify sources establish only one publishable Bangladesh-market annual list, 2023. The 2021 and 2022 year-end pages provide global/U.S. lists; the 2024 media kit provides global/U.S. song lists; and the 2025 year-end page explicitly limits its full lists to global/U.S. ([2021](https://newsroom.spotify.com/2021-12-01/what-the-world-streamed-most-in-2021/), [2022](https://newsroom.spotify.com/2022-11-30/the-top-songs-artists-podcasts-and-listening-trends-of-2022/), [2024](https://newsroom.spotify.com/media-kit/2024-wrapped/), [2025](https://newsroom.spotify.com/2025-12-03/wrapped-top-artists-songs-albums-podcasts-audiobooks/))
- No Bangladesh-local publisher's annual chart series for 2018–2025 was verified in the official sources inspected. That is a research gap, not a claim that no local broadcaster or publisher ever issued an annual list. No third-party ranking was promoted to a primary-source observation.

For data entry, use only the verified Spotify 2023 rows if this supplemental series is accepted. Keep the missing years blank/unverified; do not extrapolate from the Spotify 2023 ranks or fill from global/U.S. rankings. The 2023 period end, numeric stream counts, and ranking formula remain unspecified by the published source.


## Addendum (2026-11-17): local source capture

The official article iframe resolves to [Spotify’s Wrapped Mapped embed](https://newsroom.spotify.com/wp-content/themes/ftr/assets/animations/wrapped2023/WRAPPEDMAPPEDV8/WRAPPEDMAPPEDV8.html). Its generated chart script contains the Bangladesh panel's five ordered track rows and Spotify track URIs. The captured article, embed, script, and position rows are preserved in `data/derived/annual_revision/provider_series/spotify-wrapped-mapped-bd-2023-top5/`. The series records publisher country `SE`, chart market `BD`, positions 1–5, and `period_start=2023-01-01`; `period_end` and scores remain null because the source does not specify them. It remains separate from the 150,000-position selection.

## Follow-up extraction check (2026-11-17)

The generated script includes many additional five-song blocks, but its animated heading states and ranking blocks do not form a consistent one-to-one sequence in the static source. Country-to-list assignments beyond Bangladesh remain ambiguous, so no additional map markets were imported from block order alone.
