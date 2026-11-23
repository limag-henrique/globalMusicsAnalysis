# Kugou annual chart and whitepaper search, 2018–2020 and 2022–2023

Consulted: 2026-11-18. This bounded shard searched first-party Kugou annual charts and official whitepaper tables for 2018–2020 and 2022–2023. It excludes 2021, 2024, existing 2025 evidence, and 2026 YTD.

## Result

No independent Kugou-only annual song chart series qualified. A Kugou-branded 2020 whitepaper contains explicit ranked song tables, but its footnotes attribute those tables to TME UniChart or QQ Music and NetEase Cloud Music comment data. They are preserved as review-only candidates with publisher and underlying source kept separate. The 2022 lists appear only as visual sequences in organizer-provided images republished by a media outlet; the graphic has no numeric song ranks. 2023 coverage describes a Top 10 but does not reproduce its complete ordered table. The bounded first-party search did not locate annual ranked song tables for 2018 or 2019.

The additive review-only packet is [manifest.json](../data/derived/annual_revision/provider_series/kugou-annual-chart-search-2018-2020-2022-2023-review-only/manifest.json) and [candidate_rows.jsonl](../data/derived/annual_revision/provider_series/kugou-annual-chart-search-2018-2020-2022-2023-review-only/candidate_rows.jsonl). It contains 60 explicit-rank rows from eight 2020 whitepaper tables and 15 visual-sequence rows from two 2022 image tables. Nothing was added to the active provider index or catalog.

## Publisher, data source, and market

The 2020 PDF is headed “2020 酷狗音乐白皮书” in its Kugou section; it is hosted on a Tencent CDN and later includes a separately headed Tencent Entertainment Whitepaper section. Only the Kugou-section song tables are represented. Seven tables identify TME UniChart as their data source, with a 2020-12-13 cutoff. “2020歌曲热评 TOP10” instead cites QQ Music and NetEase Cloud Music user comments. Kugou is the report publisher, but these tables do not establish a separate Kugou-only chart. The PDF does not define a geographic listener market for these tables. ([2020 PDF, printed pp. 61–65](https://mat1.gtimg.com/qqcdn/xw/whitePaper/20210110.pdf); see its footnotes around lines 2915, 2937, 3091, and 3115.)

All candidate rows use provider KUGOU_MUSIC and publisher country CN, consistent with Kugou's identification as a China-focused TME music platform; chart_market_code is null. ([TME company profile](https://www.tencentmusic.com/zh-cn/about-us.html).) “华语” describes language/editorial scope and does not establish a mainland-China listener market. The current TME rules page describes current UniChart sources; those rules were not applied retroactively to 2020. ([Current TME UniChart rules](https://www.tencentmusic.com/zh-cn/uni-chart.html).)

The 2022 media article says the complete whitepaper is available in Kugou's app by searching “白皮书,” says it includes TOP5 and TOP10 lists, and credits the images to the organizer. The captured image shows the two lists but no numeric ranks, scores, method, exact period, or market. Its 15 rows retain only visual sequence ordinals and null published_rank. The article's prose calls “孤勇者” the year's playback number one; that secondary claim is not substituted for a numeric rank absent from the graphic. ([New Flower City/Guangzhou Daily report, 2023-01-11](https://huacheng.gz-cmc.com/pages/2023/01/11/787100eac09847ee93e1b2aa1ddbce98.html), [organizer-provided graphic](https://huacheng.gz-cmc.com/upload/news/image/2023/01/11/cdce78c38a014454b875897a4d043654.jpeg).)

For 2023, secondary coverage says the whitepaper has three sections and an annual “Top Ten Gold Songs” selection, naming “可能,” “悬溺,” and “凄美地” as examples. It does not supply the full ordered table. The article also says to search “白皮书” in the Kugou app for full content. Therefore the reported depth is a secondary lead only: zero ordered rows recovered, with all ten rank mappings unresolved. ([China News Publishing report, reposted 2024-01-22](https://www.ccct.net.cn/html/bqzx/2024/0122/4908.html); [newspaper page PDF](https://pic.chinaxwcb.com/files/Resource/xplus/epaper/20240122/pdf/A4.pdf).)

## Year-by-year result

| Year | Evidence surfaced | Reported depth | Recovered | Ties, gaps, unresolved | Qualification |
|---|---|---:|---:|---|---|
| 2018 | No Kugou annual ranking surfaced. Official TOP500 page snapshot dated 2018-12-05 is a dated chart state, not an annual summary. | Unknown | 0 annual ranked rows | Depth and positions unknown. | No qualifying annual product found. |
| 2019 | No first-party annual ranked list or whitepaper table surfaced. | Unknown | 0 | Depth, ranks, ties, gaps, and positions unknown. | No qualifying annual product found. |
| 2020 | Kugou-branded whitepaper has eight explicit song tables; six cite TME UniChart, one QQ/NetEase comments, and one has no separate source footnote. | 60 rank slots across four Top 5 and four Top 10 tables. | 60 rows | One tie at rank 5 in sharing; rank 6 is skipped after that tie. Other printed sequences are continuous; no unresolved row slots. | Review-only; other-platform or cross-platform data. |
| 2022 | Organizer-provided whitepaper graphic republished by media. | Headings state TOP5 and TOP10. | 5 and 10 visual-sequence rows | Numeric ranks absent; tie/gap status unknown; all 5 and 10 rank mappings unresolved. | Review-only visual evidence, not rank rows. |
| 2023 | Secondary coverage describes an annual Top Ten but gives no complete order; full content is said to be inside the Kugou app. | Top 10, secondary report only. | 0 complete ordered rows | All ten rank mappings unresolved. | First-party table not recovered. |

### 2020 table depth and rank semantics

The PDF prints these ranks. Metric values are retained in the packet, but a complete formula for these song metrics is not published. TME UniChart footnotes for song heat, quarterly heat, and sharing tables state a 2020-12-13 cutoff. The sing-along table has no separate source note.

| Table | Published depth | Rows recovered | Published ranks | Tie/gap | Unresolved |
|---|---:|---:|---|---|---:|
| 2020歌曲热评 TOP10 | 10 | 10 | 1–10 | None | 0 |
| 2020新曲热度 TOP10 | 10 | 10 | 1–10 | None | 0 |
| 2020第一季度新曲热度 TOP5 | 5 | 5 | 1–5 | None | 0 |
| 2020第二季度新曲热度 TOP5 | 5 | 5 | 1–5 | None | 0 |
| 2020第三季度新曲热度 TOP5 | 5 | 5 | 1–5 | None | 0 |
| 2020第四季度新曲热度 TOP5 | 5 | 5 | 1–5 | None | 0 |
| 2020新曲分享 TOP10 | 10 | 10 | 1, 2, 3, 4, 5, 5, 7, 8, 9, 10 | Two songs tie at #5 with score 95.72; #6 is skipped after the tie. | 0 |
| 2020新曲传唱 TOP10 | 10 | 10 | 1–10 | None | 0 |

The comment-table footnote says QQ Music and NetEase Cloud Music user comments. New-song heat, quarterly heat, and sharing tables cite TME UniChart. The sing-along table follows within the same section but has no separate source footnote. This is Kugou-published whitepaper material, not an independent Kugou-only annual series. ([2020 whitepaper PDF, printed pp. 61–65](https://mat1.gtimg.com/qqcdn/xw/whitePaper/20210110.pdf).)

## 2018–2019 primary-source search log

On 2026-11-18, first-party domain searches included:

- site:kugou.com 2018 年度 音乐 白皮书 酷狗 年榜 歌曲 TOP100
- site:kugou.com 2019 年度 音乐 白皮书 酷狗 年榜 热歌
- site:mat1.gtimg.com/qqcdn/xw/whitePaper 酷狗音乐白皮书 2019
- site:mat1.gtimg.com/qqcdn/xw/whitePaper "2018 酷狗音乐白皮书"
- site:activity.mobile.kugou.com "2019酷狗音乐白皮书" OR "2019酷狗白皮书"
- site:activity.mobile.kugou.com "2018酷狗音乐白皮书" OR "2018酷狗白皮书"

The searches returned the 2020 whitepaper, unrelated Kugou pages, or no relevant 2018/2019 table. This is a bounded search result, not proof that an unindexed or app-only source never existed. Kugou's official ranking page exposes ongoing chart families such as TOP500 and new-song charts; a 2018-12-05 TOP500 snapshot has numeric ranks but is not labeled year-end. ([Kugou rankings page](https://www.kugou.com/musicrankk7/), [TOP500 snapshot](https://www.kugou.com/yy/rank/home/1-8888-34838.html).)

## Source captures and hashes

Ordinary HTTPS captures returned HTTP 200 on 2026-11-18. Response headers are retained beside the files in the packet source_snapshots/ directory.

| Artifact | Retrieved UTC | Bytes | SHA-256 |
|---|---|---:|---|
| [2020 Kugou whitepaper PDF capture](../data/derived/annual_revision/provider_series/kugou-annual-chart-search-2018-2020-2022-2023-review-only/source_snapshots/kugou-2020-music-whitepaper-plus-tencent-entertainment-section.pdf) | 13:10:45 | 7,095,976 | 19B613FE314FA6D363BC6706CDD8F6DB169E3F88643953C57A41E4089D8E828F |
| [2022 media article HTML capture](../data/derived/annual_revision/provider_series/kugou-annual-chart-search-2018-2020-2022-2023-review-only/source_snapshots/kugou-2022-whitepaper-news-republication.html) | 13:45:50 | 6,224 | B59D0AC59B8CBCADD20349B35B4FA0E0FD54CA571D6E9BCDA76BEFAEFE79C747 |
| [2022 organizer-provided TOP5/TOP10 image capture](../data/derived/annual_revision/provider_series/kugou-annual-chart-search-2018-2020-2022-2023-review-only/source_snapshots/kugou-2022-whitepaper-republication-2.jpg) | 13:42:48 | 199,617 | 5653F430D103D22D931C4986D97B55760883BB90D6892E4B69F7CE059757C301 |

The PDF Last-Modified header is 2021-01-10 03:55:22 UTC. The article and image are media-hosted re-publications, not direct Kugou-hosted table pages. The packet manifest records source URLs, status, bytes, hashes, and retrieval dates. The JSONL row file SHA-256 is 32332B7C23372EE7386221A448122E06BABB03FA7B8AC1EA18855664E6FD7DE7.

## Qualification and next shard

Keep the packet review-only: 2020 tables explicitly rank songs but depend on other-platform or cross-platform sources; 2022 lists have no numeric ranks; 2023/2018/2019 first-party tables were not recovered. Do not import these rows into the active index or catalog.

Next actionable shard: retrieve the 2022 or 2023 full whitepaper through Kugou's app search for “白皮书” and inspect original pages for numeric ranks, market scope, and method. This is the access route named in the media reports. A separate historical TOP500 archive search could then test whether dated snapshots support a bounded 2018/2019 annual derivation; the 2018-12-05 snapshot alone cannot.


