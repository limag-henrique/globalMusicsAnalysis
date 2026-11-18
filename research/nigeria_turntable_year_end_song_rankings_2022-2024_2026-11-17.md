# Nigeria year-end song rankings: TurnTable Charts, 2022–2024

Research note: 2026-11-17. This follow-up checks TurnTable Charts first-party evidence for annual overall song rankings. National publisher results are stored as separate provider series and do not fill or change the Spotify/YouTube core cohort.

## Findings

For 2025, see [Nigeria 2025 year-end Top 100: TurnTable Charts](nigeria_turntable_2025_year_end_top100_2026-11-17.md).


### 2022 route is not a historical 2022 table

TurnTable’s [2022 year-end recap](https://www.turntablecharts.com/news/697) links to the full chart at [`/charts/20`](https://www.turntablecharts.com/charts/20). The direct capture on 2026-11-17 serves a page titled “End of the Year Charts — TurnTable Top 100” with a displayed date of “Dec 13th - Dec 19th, 2024” and 100 entries matching the 2024 year-end context. This is a current rendering of the linked route, not a preserved 2022 table, so it is not assigned to 2022. The 2022 recap remains useful context, but no 2022 full rank sequence was imported from that dynamic route.

### 2024 year-end Top 100

The current official [TurnTable Top 100 page](https://www.turntablecharts.com/charts/20) displays numeric ranks 1–100 and the title “End of the Year Charts — TurnTable Top 100.” Its 100 rows were captured directly from the page HTML; all ranks are contiguous and each row retains the publisher’s song title, artist credit, and displayed weekly metadata. The page’s displayed “Dec 13th - Dec 19th, 2024” date is recorded as page metadata only. Exact annual aggregation boundaries are unknown and remain null.

TurnTable’s [2024 Year-End Charts overview](https://www.turntablecharts.com/magazine/6th/131) frames the charts as covering music that resonated with fans in Nigeria and says the charts are backed by streaming and airplay data. It names “Twe Twe (Remix)” by Kizz Daniel & Davido as the overall No. 1 song. The separate [Year-End Top Songs of 2024 article](https://www.turntablecharts.com/magazine/6th/128) lists a Top 10 whose titles and order match table positions 2–10; its first entry matches the table’s first entry by artist credit but adds “Remix” to the title. At rank 1, the chart table says “Twe Twe,” while both year-end articles use “Twe Twe (Remix)” / “Twe Twe Remix”; the provider’s suffix variation is recorded without inferring edition equivalence. No ranking weights or exact annual window are published in the captured sources.

## Provider-specific import

The packet [`turntable-charts-ng-2024-year-end-top100`](../data/derived/annual_revision/provider_series/turntable-charts-ng-2024-year-end-top100/manifest.json) contains series `TURNTABLE_CHARTS_YEAR_END_SONGS_NG_2024`: 100 observed ranked positions, reported depth 100, publisher TurnTable Charts (NG), chart market NG. It remains a separate provider series and contributes zero positions to the 150,000-position Spotify/YouTube core.

Raw captures, HTTP headers, retrieval times, and body hashes are preserved in [`source_snapshots`](../data/derived/annual_revision/provider_series/turntable-charts-ng-2024-year-end-top100/source_snapshots/). Key hashes:

- Ranked rows: `9cef1e5e49f5e103285e07d65f2b7045f8d3fa2ae4debb19b6c3c5feee537293`
- Top 100 source page: `cb037abda15239822abaf18600c540896314e84b3fa0eeaf0a241777a163d25e`
- 2024 top-ten article: `d9866c66961446f8297b75bf5870a7c4dcea6739b5bcb207107bc46b4f53c715`
- 2024 year-end overview: `ed72d985dac2cd472aeb4902ef77b9f1b96a32a0092f4459690ad56c959b4f83`
- 2022 recap (dynamic route context): `d319d0f48a960abb91d61f79a6380e7b62c0020be714752aa074fd5ff5ef477e`

## Sources

All ranking evidence above comes from TurnTable Charts’ own pages. The current Top 100 table is not backdated to 2022 based on a dynamic link, and its displayed weekly date is not treated as the annual aggregation window.
