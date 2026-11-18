# Kugou annual music list audit, 2018–2024

Consulted: 2026-11-18. Scope: a bounded first-party search for Kugou-owned annual song rankings for completed years 2018–2024. Existing 2025 Kugou evidence was excluded to avoid duplication; 2026 YTD was out of scope. The existing China TME UNI/QQ Music/CAVCA audit remains separate.

## Result

No defensible Kugou annual **ranked chart** series was recovered for 2018–2024. Two official Kugou editorial playlists did yield recoverable rows: 2021 (99 API rows against a 100-song description) and 2024 (50 API rows). Both remain review-only because their pages describe curated/year-end playlists and publish no numeric chart ranking method. Their ordered content is kept as playlist evidence, not chart ranks, and neither packet was added to the active provider-series index.

The 2021 and 2024 evidence packets are [the 2021 review-only packet](../data/derived/annual_revision/provider_series/kugou-2021-chinese-annual-playlist-top100-review-only/manifest.json) and [the 2024 review-only packet](../data/derived/annual_revision/provider_series/kugou-2024-year-end-dominating-songs-top50-review-only/manifest.json).

## Publisher and market

Tencent Music Entertainment identifies Kugou as one of its four major Chinese mobile music products. That establishes publisher context, not the listener geography for a particular list. Accordingly, these packets use publisher country `CN` and leave `chart_market_code` unset. In 2021, “华语” describes the language/editorial scope; in 2024, the page gives no audience geography. Neither phrase establishes a mainland-China listening market. ([TME company profile](https://www.tencentmusic.com/zh-cn/about-us.html))

Neither source provides numeric chart ranks, a scoring method, or a precise reporting interval. The 2021 page explicitly numbers only its first 30 playlist entries; the 2024 page identifies a 50-song list. API ordering and API `sort` keys are preserved separately from any published chart rank. No ties or rank gaps are attributed to either list.

## Year-by-year findings

| Year | First-party evidence found | Captured or visible depth | Qualification |
|---|---|---:|---|
| 2018 | Search surfaced “我的2018年度歌单”, created by user 小姜禾, rather than a Kugou publisher ranking. ([page](https://www.kugou.com/yy/special/single/collection_3_587661579_11_0.html)) | 25 visible rows | Excluded: user playlist; no official chart claim. |
| 2019 | “年终盘点～2019全年最火的华语歌曲” is attributed to creator 唯一 and was updated 2022-06-09. ([page](https://www.kugou.com/yy/special/single/collection_3_1379269573_13_0.html)) | 30 visible rows | Excluded: user playlist; no official chart claim. |
| 2020 | “酷狗音乐新人星曜计划·2020年” is attributed to user 胖胖谢景行, says it is a continuously updated program-song playlist, and was updated 2020-08-07. ([page](https://www.kugou.com/yy/special/single/2879343.html)) | 30 visible rows | Excluded: user-assembled program playlist, not a year-end ranking. |
| 2021 | Official “2021年度华语精选盘点” by 酷狗音乐编辑部; its description says 100 Chinese-language songs were selected with annual on-platform play data. ([page](https://www.kugou.com/yy/special/single/4596476.html), [first-party song API](https://pc.service.kugou.com/yueku/v9/special/song/getData.js?cdn=cdn&sid=4596476)) | 30 numbered public HTML rows; API `total=99`, 99 recovered rows | Review-only editorial selection; one source-sort key missing against stated playlist count; no chart ranks or method. |
| 2022 | “我的2022年度歌单” is attributed to user 诺克咋喽 and updated 2023-01-06. ([page](https://www.kugou.com/yy/special/single/collection_3_1143463453_111_0.html)) | 10 visible rows | Excluded: user playlist; no official chart claim. |
| 2023 | “2023全网最火的流行热歌丨首首动听” is attributed to user 沈世爱 and updated 2023-01-09. ([page](https://www.kugou.com/yy/special/single/collection_3_1187850214_856_0.html)) | 30 visible rows | Excluded: user playlist; not a completed-year publisher ranking. |
| 2024 | “2024年度霸榜热歌，你听过几首？” by 酷狗星曜榜; the first-party listing shows 50 songs and update date 2025-01-07. ([Kugou listing](https://www2.kugou.kugou.com/yueku/v9/special/single/8250229-3-1084.html), [captured first-party page endpoint](https://pc.service.kugou.com/yueku/v9/special/single/8250229-3-1084.html), [first-party song API](https://pc.service.kugou.com/yueku/v9/special/song/getData.js?cdn=cdn&sid=8250229)) | Listing/API count 50; 50 API rows | Review-only editorial playlist; no rank formula, score, exact period, or listener market. |

These are the relevant first-party pages returned in this bounded search, not proof that Kugou never published other historical lists. No rows were inferred from user-made playlists or secondary reporting.

## Captured rows, depth, and gaps

### 2021

The official page calls the item a selection of 100 Chinese-language songs based on annual on-platform play data, names 酷狗音乐编辑部 as creator, and labels the page “精选辑”/歌单. Its public HTML displays entries 01–30 and then asks users to download the client for more. The first-party API returns `total=99` and 99 song records. Its raw `sort` keys range from 0 through 99 with key 33 absent; keys 0–29 align with the page’s numbered first 30 entries. Thus the stated playlist count is 100, visible HTML depth is 30, API-recovered depth is 99, and the API source-sort-key gap is 33 (candidate playlist ordinal 34). The missing row’s title and artist remain unknown. This is an unresolved playlist slot, not a chart rank gap. ([official page](https://www.kugou.com/yy/special/single/4596476.html), [official API](https://pc.service.kugou.com/yueku/v9/special/song/getData.js?cdn=cdn&sid=4596476))

The packet assigns `playlist_order_ordinal` from the API `sort` value plus one, retaining `source_sort_key`, and leaves `published_rank` null. This ordinal interpretation is supported by alignment with the page’s first 30 numbered entries; the list is still a curated editorial selection, not a qualified chart.

### 2024

The official Kugou Star Chart page is titled “2024年度霸榜热歌，你听过几首？” and lists 50 songs; it shows creator 酷狗星曜榜 and update date 2025-01-07. The first-party API reports `total=50` and returns 50 rows. The API `sort` keys range from 0 through 50 with key 13 absent. The page’s available web rendering does not publish numbered ranks, and no first-party documentation found in this search defines `sort` as a public rank. The packet therefore preserves API response sequence and raw sort key, but leaves `playlist_order_ordinal` and `published_rank` null. The missing sort key is an unresolved source-field anomaly, not a published rank gap or a proven missing song. ([Kugou listing](https://www2.kugou.kugou.com/yueku/v9/special/single/8250229-3-1084.html), [captured page endpoint](https://pc.service.kugou.com/yueku/v9/special/single/8250229-3-1084.html), [official API](https://pc.service.kugou.com/yueku/v9/special/song/getData.js?cdn=cdn&sid=8250229))

### Ties and gaps

Neither official page publishes numeric chart ranks or ties. The packet fields `ties_or_gaps_as_published` and `positions` are empty because there are no published chart ranks to encode. The 2021 missing row and 2024 `sort=13` are recorded in their own unresolved-source fields; they are not converted into chart gaps. The 2024 API count matches the listed 50-song count, but the ambiguous `sort` key prevents claiming that every original playlist ordinal has been resolved.

## Retrieval and hashes

The following ordinary HTTPS captures returned HTTP 200 on 2026-11-18. SHA-256 values are over the downloaded body bytes saved in the packet `source_snapshots/` directories.

| Year | Artifact | Retrieved (UTC) | Bytes | SHA-256 |
|---|---|---|---:|---|
| 2021 | [Official playlist HTML](../data/derived/annual_revision/provider_series/kugou-2021-chinese-annual-playlist-top100-review-only/source_snapshots/annual-playlist.html) | 13:23:16 | 154,573 | `1642F5609F6407764EDD4DFABA5868261FD4C6DC3010047B8CE2904BE9D279B9` |
| 2021 | [Official song API JSON](../data/derived/annual_revision/provider_series/kugou-2021-chinese-annual-playlist-top100-review-only/source_snapshots/annual-playlist-api.json) | 13:23:21 | 340,537 | `6F86A8DCB5F4A3287317472BF179D2A86FB07DE3486DFC37BBEA41134B7ADEA9` |
| 2024 | [Official playlist page endpoint HTML](../data/derived/annual_revision/provider_series/kugou-2024-year-end-dominating-songs-top50-review-only/source_snapshots/annual-playlist.html) | 13:23:22 | 206,318 | `9C7B3094AF5F95FBB2C757E756538C6522FC93A9A8CEC4C1283A5F82B2C516C3` |
| 2024 | [Official song API JSON](../data/derived/annual_revision/provider_series/kugou-2024-year-end-dominating-songs-top50-review-only/source_snapshots/annual-playlist-api.json) | 13:23:23 | 185,943 | `AC3A8CED94ADC6136E9B0B14D082553E30F042D9305C3E00B377A893967686FC` |

The saved `.headers.txt` files preserve response headers. The 2024 listing page was also checked through Kugou’s first-party indexed view, which displayed “歌曲(50首)”; the separately captured `pc.service.kugou.com` page endpoint supplied the title, creator, and update metadata, while the accessible API supplied the 50 song rows. The `www2` listing host timed out in the web opener and had a TLS hostname mismatch under direct command-line retrieval, so no hash is claimed for that host response.

## Qualification and next work

Both recovered sets remain separate provider-tagged review material. They are not imported into the core Spotify/YouTube selection, do not establish a China listener market, and were not added to `provider-series-index.json`. Existing 2025 Kugou work remains the separate [2025 review note](kugou_2025_chinese_pop_top100_playlist_2026-11-17.md); no 2025 rows were duplicated here.

The bounded Kugou shard is complete. Any follow-up seeking a formal non-Tencent historical series should target a different publisher or locate a Kugou chart product with explicit rank semantics and recoverable first-party year-end data.