# Tencent Music UNI Chart annual song rankings (2021–2025)

Date consulted: 2026-11-16. Scope: primary-source research on TME's annual UNI Chart song rankings. Additive source packets were captured for 2021, 2022, 2024, and 2025; the conflicting 2023 records were captured in a review-only packet. No rows were merged into the existing 150,000-position Spotify/YouTube selection or canonical catalog, and no code or existing report was changed.

## Provider and series identity

Tencent Music identifies 腾讯音乐由你榜 as TME UniChart, a sub-chart under TME Chart. Its current official rules describe a chart for Chinese-language songs (华语歌曲) and say it combines data from QQ Music, Kugou, Kuwo, Bodian Music, JOOX, Tencent Video, and Sina Weibo; its score combines listening heat, sales, and recommendations ([official TME UniChart rules](https://www.tencentmusic.com/zh-cn/uni-chart.html)). The official TME Chart archive lists year-end reports for 2021–2025 ([annual-report directory](https://yobang.tencentmusic.com/chart-h5/home)). The rules do not state that listener activity is restricted to mainland China, so `CN` should identify the publisher jurisdiction only; leave the geographic chart market unassigned unless a year-specific primary source defines it. The rules page snapshot is stored at `data/derived/annual_revision/provider_series/tme-uni-provider-rules/source-page.html`, with retrieval metadata and hash in its manifest.

This supports a separate provider-tagged source such as `provider=TME`, `chart_family=TME UniChart`, `publisher_country=CN`, `language_scope=华语`, and `market_scope=not stated`, with the annual sub-chart and native score retained. Keep its positions and score field separate from Spotify, YouTube, or another chart's ranks and metrics.

## Annual scope, depth, and rank semantics

| Ranking year | Official category and sort basis | Period stated by the source | Published depth and ties |
|---|---|---|---|
| 2021 | Annual Songs TOP 10; each song's highest single-week new-song score (最高新歌得分) | The 2021 report states its annual chart-song count covered 2020 issue 52 through 2021 issue 51. The ranking's own note says the basis is the highest new-song score in one chart week while the song was charted. | Ranks 1–10, 10 songs, no ties. |
| 2022 | Annual high-score songs; ranked by each song's highest UNI score. The same report also has a distinct composite Annual Songs list. | Report is labeled 2022 annual; the ranking page does not state exact issue or date boundaries. | 10 entries with published ranks 1, 2, 3, 4, 5, 6, 7, 8, 8, 10; two entries share rank 8 and rank 9 is absent. |
| 2023 | The 2023 annual page contains an Annual High-Score Songs list, separate from the composite Annual Songs list, but its row-level year notes conflict. | Unresolved: rank 1's note says 2023; ranks 2–10 are tagged 2024–2032, respectively. | The page renders 10 rows with positions 1, 2, 2, 4–10, but the cohort cannot be assigned to 2023 without reconciling its row notes. |
| 2024 | Annual high-score songs; official note says rank by highest score in the weekly UNI chart. | The report is labeled 2024 annual; the page does not state exact issue or date boundaries. | Ranks 1–10, 10 songs, no ties. |
| 2025 | Annual high-score songs; the official post publishes the songs under that category with highest-score values in descending order. | The source labels the post 2025 annual; it does not give exact issue or date boundaries. | 10 entries with published ranks 1, 2, 3, 4, 5, 6, 6, 8, 9, 10; two entries share rank 6 and rank 7 is absent. |

The 2021 report gives a shifted 52-issue window rather than a simple Jan–Dec interval. For 2022–2025, the inspected annual sources give the named reporting year but not exact boundaries; do not fill `period_start` or `period_end` with assumed calendar dates. The 2021 source is the [official 2021 Digital Music White Paper](https://yobang.tencentmusic.com/pdf/DigitalMusic2021.pdf) and its [interactive annual-song page](https://yobang.tencentmusic.com/uni-annual-report-2021/song). Other year-specific sources are the [2022 UNI songs and albums page](https://yobang.tencentmusic.com/activity/uni-annual-report-2022-end/uni-chart/uni-song-album), [2023 UNI songs and albums page](https://yobang.tencentmusic.com/activity/uni-annual-report-2023-end/uni-chart/uni-song-album), [2024 UNI annual page](https://yobang.tencentmusic.com/chart-h5/annual-report-2024-end/uni-chart?moduleId=songsAndAlbums), and [2025 TME annual-report portal](https://yobang.tencentmusic.com/chart-h5/annual-report-2025-end/tmeChart).

## Published rankings

Scores below are TME's own score values. Ranks and tie positions are copied as published; ties are not converted into dense ranks.

### 2021 — Annual Songs TOP 10

Source: [2021 Digital Music White Paper](https://yobang.tencentmusic.com/pdf/DigitalMusic2021.pdf), which names the category 年度歌曲 TOP 10, lists positions 1–10, states the 2020 issue 52–2021 issue 51 chart-count window, and says the ranking basis is the song's highest single-week new-song score (最高新歌得分). The source PDF table was visually checked on printed page 69.

| Rank | Song | Artist | Highest single-week score |
|---:|---|---|---:|
| 1 | 白月光与朱砂痣 | 大籽 | 97.95 |
| 2 | 尾号6208 | 严浩翔 | 97.80 |
| 3 | 星辰大海 | 黄霄雲 | 97.75 |
| 4 | 迷 | 蔡徐坤 | 97.54 |
| 5 | 流星也为你落下来了 | 王源 | 97.26 |
| 6 | 大风吹 | 王赫野 | 97.18 |
| 7 | 我喜欢你 | 时代少年团 | 97.15 |
| 8 | 清空 | 王忻辰 / 苏星婕 | 97.04 |
| 9 | 孤勇者 | 陈奕迅 | 96.70 |
| 10 | Baby I Know | 刘雨昕 | 96.66 |

### 2022 — Annual high-score songs

Source: [2022 UNI songs and albums page](https://yobang.tencentmusic.com/activity/uni-annual-report-2022-end/uni-chart/uni-song-album). Its high-score section says the list is ranked by each song's highest UNI score. The page also presents a separate composite Annual Songs list; these are different categories.

| Rank | Song | Artist | Highest score |
|---:|---|---|---:|
| 1 | Hug me (抱我) | 蔡徐坤 | 99.10 |
| 2 | 绝配 | 时代少年团 | 99.09 |
| 3 | 渐暖 | 时代少年团 | 98.93 |
| 4 | 哭泣的游戏 | 时代少年团 | 98.83 |
| 5 | 侠 | 时代少年团 | 98.63 |
| 6 | 寻一个你 | 摩登兄弟刘宇宁 | 98.58 |
| 7 | 最伟大的作品 | 周杰伦 | 98.55 |
| 8 | 余情 | 周深 | 98.49 |
| 8 | 偷 | 马嘉祺 | 98.49 |
| 10 | 百忧戒 | 时代少年团 | 98.39 |

### 2023 — high-score page has conflicting row-year notes

Source: [2023 UNI songs and albums page](https://yobang.tencentmusic.com/activity/uni-annual-report-2023-end/uni-chart/uni-song-album). Its embedded high-score rows show ranks and values, but each row has a remark naming the year of the weekly chart whose highest score is used. The first row says 2023; following rows say 2024 through 2032. I could not reconcile this first-party inconsistency, so these are transcribed as page records with their row-year notes, not treated as a verified 2023 cohort. The page separately publishes a composite Annual Songs list ranked using score, weekly rank, and time on chart; do not relabel that composite list as the high-score ranking.

| Published rank | Song | Artist | Highest UNI score | Row's year note |
|---:|---|---|---:|---|
| 1 | 罗刹海市 | 刀郎 | 98.77 | 2023 |
| 2 | 笼 | 张碧晨 | 98.70 | 2024 |
| 2 | 乌梅子酱 | 李荣浩 | 98.70 | 2025 |
| 4 | 圣诞星 (feat. 杨瑞代) | 周杰伦 | 98.54 | 2026 |
| 5 | 西楼儿女 | 岳云鹏 | 98.44 | 2027 |
| 6 | 烟花升停在星夜 | 宋亚轩 / 刘耀文 | 98.42 | 2028 |
| 7 | 5:23PM | 宋亚轩 | 98.34 | 2029 |
| 8 | 听悲伤的情歌 | 苏星婕 | 98.24 | 2030 |
| 9 | 其实都没有 | 于冬然 | 98.22 | 2031 |
| 10 | Fri Friday | 马嘉祺 | 98.20 | 2032 |

### 2024 — Annual high-score songs

Source: [2024 UNI annual page](https://yobang.tencentmusic.com/chart-h5/annual-report-2024-end/uni-chart?moduleId=songsAndAlbums). The high-score list is explicitly numbered 1–10 and the page note says it ranks each song's highest score on weekly UNI chart releases.

| Rank | Song | Artist | Highest UNI score |
|---:|---|---|---:|
| 1 | 小美满 | 周深 | 98.86 |
| 2 | 体贴 | 宋亚轩 | 98.77 |
| 3 | 失恋循环 | 宋亚轩 | 98.65 |
| 4 | 蜉蝣 | 马嘉祺 | 98.62 |
| 5 | 蜃楼 | 周深 | 98.50 |
| 6 | 我们 | 肖战 | 98.47 |
| 7 | The Beast | 严浩翔 | 98.45 |
| 8 | Afterglow | 蔡徐坤 | 98.43 |
| 9 | 人间半途 | 刘阳阳 | 98.40 |
| 10 | 不要回头 | 肖战 | 98.39 |

### 2025 — Annual high-score songs

The [2025 TME annual-report portal](https://yobang.tencentmusic.com/chart-h5/annual-report-2025-end/tmeChart) is the official report entry point. Rank details are published in a post dated 2025-12-27 from the verified Tencent Music UniChart official account; the post is reproduced by Sina ([post text and all published ranks](https://www.sina.cn/news/detail/5248407829749750.html); [official account profile](https://weibo.com/u/6733257358)). The post has ten entries, with two tied at #6 and no #7 entry. The direct post permalink was not recovered, so its local packet is marked as a mirrored official post.

| Rank | Song | Artist as credited in the post | Highest score |
|---:|---|---|---:|
| 1 | spr. | 宋亚轩 | 99.19 |
| 2 | Kill Night 耀 | 刘耀文 | 98.83 |
| 3 | 冬眠 (In My Mind) | 严浩翔 | 98.80 |
| 4 | Deadman | 蔡徐坤 | 98.70 |
| 5 | 亢奋 (Euphoria) | 严浩翔 | 98.50 |
| 6 | 泥潭 | @我是梓渝_ | 98.25 |
| 6 | 万花镜 | 张真源 | 98.25 |
| 8 | Jasmine | 蔡徐坤 | 98.22 |
| 9 | 残影 | 贺峻霖 | 98.14 |
| 10 | 雨后晴天 | @我是梓渝_ | 98.13 |

## Encoding assessment and limitations

This is a distinct Chinese-language chart provider series and can be represented without folding its observations into Spotify or YouTube annual series. Preserve the source's chart family, annual category, native score name, rank, and source URL. For 2022, 2023, and 2025, retain repeated positions and the source's rank gaps; do not convert ties to dense ranks or infer missing ranks. The local `publisher_country_code=CN` records TME's jurisdiction, while `chart_market_code` remains unset because the rules do not define listener geography. Captured artifacts: `data/derived/annual_revision/provider_series/tme-uni-cn-2021-annual-top10`, `.../tme-uni-cn-2022-high-score`, `.../tme-uni-cn-2023-high-score-review`, `.../tme-uni-cn-2024-high-score`, and `.../tme-uni-cn-2025-high-score`. The 2023 packet is review-only, and the 2025 packet records its syndication provenance; neither is merged into the existing Spotify/YouTube selection.

The source family is not perfectly uniform by title: 2021 calls its top-score list Annual Songs TOP 10, while 2022–2025 expose a high-score category. The 2022–2024 annual pages also publish distinct composite Annual Songs lists; those use a different ordering basis and must not be silently substituted for the high-score lists. Treat the 2023 high-score rows as unresolved because their row notes span 2023–2032. Exact annual issue/date boundaries were verified only for the 2021 report's stated 2020 issue 52–2021 issue 51 window; boundaries for 2022–2025 remain unverified in the inspected primary sources.
