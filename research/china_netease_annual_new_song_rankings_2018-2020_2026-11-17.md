# NetEase Cloud Music annual new-song rankings, 2018–2020

Date consulted: 2026-11-17. Scope: first-party NetEase Cloud Music annual song lists outside the Tencent Music audit. This began as a source review only; the later packet and catalog integration is recorded at the end of this note.

## Finding

NetEase Cloud Music's own playlist account (user ID 1, display name 网易云音乐) published a ranked annual **new-song** list for each year in scope. The first-party playlist detail API returns the ordered track-ID sequence and a description giving the year period and selection method. The source order is a usable publisher-specific ranking sequence, separate from Spotify/YouTube and from TME/QQ Music. NetEase is a China-based publisher; the source describes platform data, but does not state that eligible listening is limited to mainland listeners. Record publisher jurisdiction as CN and leave chart market unspecified.

| Year | Official list / advertised depth | Period and stated method | Current first-party payload | Source |
|---:|---|---|---|---|
| 2018 | `2018年度最热新歌TOP100` (“2018 hottest new songs TOP100”) | 2018-01-01–2018-12-26. Description says it considers the average daily plays and favorites of all songs first uploaded to NetEase Cloud Music in that period; it excludes some tracks that were already online before 2018 but were later included on newly released formal albums. | The description promises 100 songs, but the current `trackCount` and `trackIds` array expose 98. The unavailable two items and their original positions are not identified. | [Playlist](https://music.163.com/#/playlist?id=2578068117) · [official detail API](https://music.163.com/api/v6/playlist/detail?id=2578068117&n=1000) |
| 2019 | `2019年度最热新歌TOP50` (“2019 hottest new songs TOP50”) | 2019-01-01–2019-12-31. Description says it references platform user listening data (plays, favorites, searches, etc.) and combines playback behavior to calculate artist influence and fan stickiness; it excludes some previously online songs later included on new formal albums. | The description promises 50 songs, but the current `trackCount` and `trackIds` array expose 49. The unavailable item and its original position are not identified. | [Playlist](https://music.163.com/#/playlist?id=3172849329) · [official detail API](https://music.163.com/api/v6/playlist/detail?id=3172849329&n=1000) |
| 2020 | `2020年度最热新歌TOP50` (“2020 hottest new songs TOP50”) | 2020-01-01–2020-12-31. Description uses the same stated inputs and method as 2019. | All 50 advertised entries are currently exposed in `trackCount` and `trackIds`. | [Playlist](https://music.163.com/#/playlist?id=5434589326) · [official detail API](https://music.163.com/api/v6/playlist/detail?id=5434589326&n=1000) |

The playlist API contains an ordered `trackIds` array but no numeric rank or score field. The `TOP100`/`TOP50` titles, “hottest” descriptions, and returned sequence support treating playlist sequence as the publisher's order. The API's separate `ordered` flag is `true` for 2018 and 2019 and `false` for 2020; its meaning is not documented in the response, so I do not use it to assert or reject ranking. No tie rule or score values are stated. The positions below mean **current API sequence positions**, not a claim that NetEase exposes a separate numeric rank field. Since 2018 and 2019 now return fewer entries than their descriptions promise, do not fill the missing rows or claim complete historical rank coverage; removals could have shifted the visible current positions, and the original positions of missing tracks cannot be recovered from this payload.

## First ten entries observed

These are a spot-check of the current first-party sequence, with track names and artists resolved through NetEase's first-party song-detail endpoint. Full currently exposed sequences are retained in the raw API captures linked below.

| Current sequence | 2018 | 2019 | 2020 |
|---:|---|---|---|
| 1 | 天份 — 薛之谦 | 我曾 — 隔壁老樊 | 天外来物 — 薛之谦 |
| 2 | 年少有为 — 李荣浩 | 世间美好与你环环相扣 — 柏松 | 会不会（吉他版） — 刘大壮 |
| 3 | 盗将行 — 花粥 / 马雨阳 | 芒种 — 音阙诗听 / 赵方婧 | 经济舱 (Live) — KAFE.HU胡懿 |
| 4 | 不染 — 毛不易 | 心如止水 — Ice Paper | 夏天的风 — 火羊瞌睡了 |
| 5 | 往后余生 — 王贰浪 | 起风了 — 吴青峰 | 海底 — 一支榴莲 |
| 6 | 可能否 — 木小雅 | 野狼disco — 宝石Gem | 丢了你 — 井胧 |
| 7 | 我们 — 陈奕迅 | 好想爱这个世界啊 — 华晨宇 | 大眠 (完整版) — 小乐哥（王唯乐） |
| 8 | 起风了 — 冯沁苑（买辣椒也用券） | 我和我的祖国 — 王菲 | 他只是经过 — h3R3 / 高旭 |
| 9 | 星球坠落 (Live) — 艾热 AIR / 李佳隆 | 你的答案 — 阿冗 | 与我无关 — 阿冗 |
| 10 | Everything I Need (Film Version) — Skylar Grey | 麻雀 — 李荣浩 | 好想爱这个世界啊 (Live) — 华晨宇 |

## Interpretation and limits

- **Separate provider series:** These are NetEase editorial annual new-song rankings. Their rank lists should remain tagged to NetEase Cloud Music and should not be merged into another provider's order or treated as the project's Spotify/YouTube core chart.
- **Scope:** Each description says the inputs are NetEase platform or user listening data. None specifies listener-country eligibility, so these pages do not establish a mainland-only chart market even though NetEase is a Chinese publisher. [NetEase's corporate profile](https://ir.netease.com/zh-hans/company-overview/corporate-profile) identifies NetEase Cloud Music as its online music platform subsidiary; the playlist API identifies the creator as 网易云音乐 (user ID 1).
- **Coverage:** These rank *newly uploaded songs* meeting each description's year and catalog rules, not an unrestricted all-song annual chart. The 2018/2019 sources are partial at retrieval; the 2020 source is complete to its stated Top 50 depth, not a 500-row market ranking.
- **Tie and ranking detail:** Scores, formula weights, and tie handling are not published in the playlist payload. Only the ordered sequence is available. Treat a sequence position as the publisher's order, and do not infer score distances or a tie-break rule.

## Other publisher checks

The official [Kugou rankings index](https://www.kugou.com/musicrankk7/) was reviewed as an additional candidate publisher. It currently presents chart categories but did not expose an ordered 2018–2020 annual song list in the pages reviewed. Kugou's accessible [2017 music white paper](https://activity.mobile.kugou.com/activity/whitePaper2017/index.html) demonstrates an earlier annual-ranking publication, but it is outside the target years and cannot establish any 2018–2020 ranks. This is a bounded search result, not proof that Kugou has no qualifying archived chart.

NetEase's separate [2018 vote page](https://music.163.com/m/at/Yearendvoting) and [2019 vote page](https://music.163.com/m/at/Yearendvoting2019) describe user-vote awards where each award is decided by the highest vote count. They are not the play-data new-song ranking above. Ordinary desktop GET currently returns an app-opening fallback (“please open on mobile”), while the embedded campaign rules remain present in the saved HTML. No rows from those poll pages were used here.

## Capture and reproducibility

Unauthenticated GET captures were taken on 2026-11-17 at 21:18 UTC from `music.163.com`, using ordinary HTTPS. Playlist metadata requests and song-detail requests returned HTTP 200. Captures include each playlist response and song-detail response batches sufficient to resolve all currently exposed track IDs, plus the two voting-page HTML responses. The playlist response returns the complete ordered `trackIds`; its expanded song objects include only the first ten, which is why song-detail calls were captured separately.

The capture manifest records retrieval time, full request URL, status, content type, byte length, and SHA-256 for each file: [`capture_manifest.json`](../data/raw/national_charts/netease_cn_annual_new_songs_2018-2020_2026-11-17/capture_manifest.json). The primary playlist response fingerprints are:

| Year | Capture | Bytes | SHA-256 |
|---:|---|---:|---|
| 2018 | [`playlist_detail_2018.json`](../data/raw/national_charts/netease_cn_annual_new_songs_2018-2020_2026-11-17/playlist_detail_2018.json) | 40,457 | `cd6cda6c5bf0719d22b75592a57cbf86a39e8c87c058519074ca3fb31b00e297` |
| 2019 | [`playlist_detail_2019.json`](../data/raw/national_charts/netease_cn_annual_new_songs_2018-2020_2026-11-17/playlist_detail_2019.json) | 33,730 | `514394948e82ce6b752e3938551374b4020948b634364ffd5e2515e17a7d9e6a` |
| 2020 | [`playlist_detail_2020.json`](../data/raw/national_charts/netease_cn_annual_new_songs_2018-2020_2026-11-17/playlist_detail_2020.json) | 33,218 | `4653512fa2ad9f98578f4f2fb970b79aed4660d703ab6e668cba0f5c5f7b81bc` |

For the phrase-level year scope and method claims, use each linked playlist's own description field in the captured first-party API response. At the time of initial capture, no playlist rows had yet been added to project packets or catalogs; subsequent integration is recorded below.

## Follow-up packet integration (2026-11-17)

The 2020 playlist was reconciled to all 50 captured first-party song-detail records and imported as [`netease-cn-2020-annual-new-songs-top50`](../data/derived/annual_revision/provider_series/netease-cn-2020-annual-new-songs-top50/manifest.json). Its ranking file SHA-256 is `0cc61a138d6be34e0b481d12d51c1ca83285193d6d318c88abceb8428a9fc555`; the captured playlist response SHA-256 is `4653512fa2ad9f98578f4f2fb970b79aed4660d703ab6e668cba0f5c5f7b81bc`.

The 50 positions preserve the current first-party API `trackIds` sequence as ordinals (`published_rank=playlist_order:<n>`), because the response has no numeric rank labels or scores. The first ten IDs match the API's expanded playlist tracks, and all 50 match the separate song-detail responses. The response's `ordered=false` flag is retained, but its semantics are undocumented; the packet does not interpret it as proof of randomization or of a particular rank rule. The playlist title and description identify this as the 2020 hottest-new-song TOP50, so this series remains a NetEase new-song ranking, not an all-song chart. Publisher jurisdiction is CN, while `chart_market_code` remains unset because listener geography is unspecified.

The v39 supplemental catalog now contains 357 separate provider series and 43,548 ranked memberships, an additive delta of one series and 50 positions from v38. The v39 index records `core_selection_changed=false`; this NetEase series was not merged into the Spotify/YouTube cohort. The exact database, denominator report, index, import output, and appended packet order are preserved in the [v39 snapshot](../data/runtime/supplemental-provider-snapshot-history-20261117-v39/snapshot-manifest.json). The 2018 and 2019 lists remain unimported: their current API captures expose 98/100 and 49/50 entries, with missing original items and positions unidentified.
