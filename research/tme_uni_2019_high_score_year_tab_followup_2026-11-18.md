# TME UNIChart 2019 high-score year-tab follow-up

Follow-up completed 2026-11-18 under reservation `codex-tme-uni-2019-year-tab-20261118-01`. This bounded check targeted the first-party `最高由你得分 TOP10` / 2019 year-tab lead recorded in the earlier [TME 2019 source-search report](../data/runtime/tme-uni-annual-source-research-CN-2019-20261118-01/report.md). The earlier report identified that year tab only through public search-index discovery; it did not contain the tab payload.

## Finding and disposition

The first-party page JavaScript confirms a year-filtered score module. In the captured page chunk, the `最高由你得分 TOP10` component calls `KP({milestoneType:"2",year:n})`; a separate `S4()` call supplies `uniIndexTopYearList`. The captured UI chunk maps `scoreType:1` to `由你得分` and the other score labels. These are component and category facts, not proof that a selected year represents a calendar-year annual ranking. The source body and byte offsets are recorded in `year-tab-evidence.json` and `source-captures.json`.

The public 2019 tab value and its rows were not recovered. The six-request cap was used serially on public first-party JavaScript assets to trace the client calls; none contained the `KP`/`S4` implementation, and no direct data request was made. The `S4()` response that would establish the available year-tab values was also not captured. The prior search-index mention remains discovery evidence only, not a source response.

| Coverage field | Verified result |
|---|---|
| Publisher | Tencent Music / TME UNIChart; publisher country code `CN` |
| Candidate module | `最高由你得分 TOP10` |
| 2019 year-tab value | Lead from prior search-index discovery; not verified in captured first-party payload |
| Published depth | Unknown. “TOP10” is a module label; no year-specific response was recovered |
| Recovered ranked rows | 0 |
| Rank basis | Category label `由你得分` is visible; formula, ordering rule, and numeric position semantics are unverified |
| Period | Unknown; no annual scope or start/end dates established |
| Chart market | Unknown; publisher jurisdiction does not establish audience geography |
| Ties, rank gaps, unresolved positions | Unknown; no ranked response or verified depth |
| Disposition | **Review-only, unresolved lead. Do not import as an annual series.** |

The packet preserves zero recovered rows separately from unknown published depth. It does not encode an empty chart or infer ten positions from the title. `ranked_rows.jsonl` is empty; `coverage.json` carries nulls for unresolved depth, ties, gaps, period, and market.

## First-party source captures

Six public GETs were made serially, with no authentication or access-control bypass. All returned HTTP 200. The HTTP `Date` header is preserved for each response; `body_file_last_write_utc` in the capture metadata is a local file timestamp, not a claimed network request-start time.

| Captured asset | Source URL | Bytes | HTTP `Date` | SHA-256 |
|---|---|---:|---|---|
| Chunk `2218-11d7b564aefdf2d0.js` | [TME CDN](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/2218-11d7b564aefdf2d0.js) | 7,042 | 2026-11-03 10:55:02 GMT | `663DF5FDA82BA693381C09B8270B6C2CDBC7F48ADD8BAA78CCB0FE4455C07AC3` |
| Chunk `1463-cba4114405ab2fb9.js` | [TME CDN](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/1463-cba4114405ab2fb9.js) | 53,361 | 2026-11-06 12:06:17 GMT | `A811D5838BE3CDBD31F7206ECE65915AE5CC690728AFADEA6170FDC15B01600D` |
| Chunk `9072-bca76e38cfe6cc37.js` | [TME CDN](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/9072-bca76e38cfe6cc37.js) | 6,263 | 2026-11-04 03:16:07 GMT | `3D29AD1E39CE505C7FCDA9F3041BA31422B7F5BCAA21C1243ABF72E5FA9B8873` |
| Chunk `252-32f2a236d9436a2e.js` | [TME CDN](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/252-32f2a236d9436a2e.js) | 11,360 | 2026-11-18 18:52:28 GMT | `33746289847B531812E8A9A209A626692664EB3D893A589815FE4960EDC723FE` |
| Chunk `utils-68c78bcd6eca2ebe.js` | [TME CDN](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/utils-68c78bcd6eca2ebe.js) | 1,267,792 | 2026-11-12 09:03:29 GMT | `B317CDC8F5C91A32B1CE2BD99095B106CB6B03B5F7EABE3DE2D43ADE56FB1BA1` |
| Chunk `main-736f35d1edab06f8.js` | [TME CDN](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/main-736f35d1edab06f8.js) | 143,239 | 2026-10-28 08:40:58 GMT | `553A3384C2BADC37876145B192B7EBAB7B336ACD2CA51FAACC9044E2B5FD4407` |

The page-component call is in the reused first-party milestone chunk at byte offset 16,138 (`KP`) and offset 16,326 (`S4`); its SHA-256 is `97000BC5593869AED0D42C58E8046C24624AA7AE1C10C594E779EEDB9DCD8E19`. The score-label mapping appears in the new `252` chunk at byte offset 7,241; its hash is listed above. The first-party milestone HTML and generic detail-route HTML were also reused from the earlier shard (hashes `595A0FF5F8E99D8D3485F3DCF8DB5E1209CB39D14A78374B2BFB5F3777681E6E` and `B2E0837DC22D353869A84D53F590C2E0F4CBA27B63B6C225A8F75A810EA06B50`, respectively); neither contains 2019 year-tab rows.

All response bodies and headers are preserved under [`source-snapshots/`](../data/runtime/tme-uni-2019-year-tab-followup-CN-2019-20261118-01/source-snapshots/). The request inventory, including status, URL, size, response date, local body timestamp, and hash, is in [`source-captures.json`](../data/runtime/tme-uni-2019-year-tab-followup-CN-2019-20261118-01/source-captures.json); the six-request limit and serial request order are in [`request-log.json`](../data/runtime/tme-uni-2019-year-tab-followup-CN-2019-20261118-01/request-log.json). The structured assessment is in [`year-tab-evidence.json`](../data/runtime/tme-uni-2019-year-tab-followup-CN-2019-20261118-01/year-tab-evidence.json) and [`coverage.json`](../data/runtime/tme-uni-2019-year-tab-followup-CN-2019-20261118-01/coverage.json).

## Next retrieval that could change the disposition

A separately reserved public retrieval can first locate the ordinary site asset containing the `KP`/`S4` implementations, then request the year-list and 2019 payload through the same public client surface if available. Qualification still requires source evidence that the rows are annual, a stated ranking basis and period, and the complete returned depth so ties, gaps, and unresolved positions can be represented. If the client surface does not provide those facts, keep this lead review-only.
