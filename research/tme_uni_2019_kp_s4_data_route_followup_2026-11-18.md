# TME UNI 2019 KP/S4 data-route follow-up

Completed 2026-11-18 under reservation `codex-tme-uni-2019-kp-s4-data-20261118-01`. This shard followed the first-party `最高由你得分 TOP10` 2019 year-tab lead. Its six-public-GET limit was used serially; no authentication, private API, or access-control bypass was used.

## Finding

The [first-party milestone page chunk](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/pages/uni-chart/milestone-244421f21dc9ee9e.js), reused from the immediately preceding shard (35,147 bytes; SHA-256 `97000BC5593869AED0D42C58E8046C24624AA7AE1C10C594E779EEDB9DCD8E19`), calls `KP({milestoneType:"2",year:n})` for the score module and `S4()` for `uniIndexTopYearList`. A separate first-party UI chunk maps `scoreType:1` to `由你得分`. Those calls show a client-side year-filtered score component; they do not establish that a tab is annual or define a calendar period, numeric ranks, or score formula.

This shard did **not** recover the `KP`/`S4` endpoint or a response for the 2019 tab. The first-party [build manifest](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/2ULIz42kiDF35uGW-fSRV/_buildManifest.js) confirms the ordinary `/uni-chart/milestone` page chunk set. The public [_app bundle](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/pages/_app-6e380dbba77d4bc0.js) and [Webpack runtime](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/webpack-c267f9c6b891e8e8.js) were captured; the tested public [utils source-map URL](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/utils-68c78bcd6eca2ebe.js.map) and [milestone source-map URL](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/pages/uni-chart/milestone-244421f21dc9ee9e.js.map) returned HTTP 404 `NoSuchKey`. The previously captured 1,267,792-byte `utils` bundle (SHA-256 `B317CDC8F5C91A32B1CE2BD99095B106CB6B03B5F7EABE3DE2D43ADE56FB1BA1`) is Tencent Chaos VM-virtualized. This shard did not decode it or resolve the API method from it.

The final public GET requested the [milestone route with `milestoneType=2&year=2019`](https://yobang.tencentmusic.com/chart/uni-chart/milestone/?milestoneType=2&year=2019). It returned HTTP 200 and a 158,646-byte body with SHA-256 `595A0FF5F8E99D8D3485F3DCF8DB5E1209CB39D14A78374B2BFB5F3777681E6E`, exactly the hash of the earlier unfiltered SSR body. That response therefore supplied no new server-rendered 2019 year-tab rows. No API/XHR endpoint URL was found in this shard, so no direct data request was made.

**Disposition: review-only unresolved client-side data route; no annual series qualified.** This is a retrieval limitation within the six-GET shard, not evidence that no public 2019 data exists.

## Coverage

| Field | Result |
|---|---|
| Candidate provider | TME UNIChart; publisher country code `CN` |
| Candidate year | 2019, from the earlier search-index lead; the `S4` year-list response was not captured |
| Published depth | Unknown; `TOP10` is a module label only |
| Recovered rows / explicit ranks | 0 / 0 |
| Rank basis | Category label `由你得分`; score formula, ordering rule, and numeric rank semantics unknown |
| Annual scope and period | Unverified; start/end dates unknown |
| Chart market | Unknown; publisher jurisdiction does not identify listener geography |
| Ties, gaps, unresolved positions | Unknown because no ranked payload or verified depth was recovered |

The packet keeps zero recovered rows separate from unknown published depth. `ranked_rows.jsonl` is intentionally empty; `coverage.json` records nulls for the unknown dimensions.

## Public requests and response evidence

The `start` and `end` values below are the UTC times immediately before and after each serialized GET. Response `Date` values, raw body bytes, and raw headers are preserved in the packet. The local body-file modification time is recorded separately and is not used as a request timestamp.

| # | First-party GET | Status | Bytes | Response `Date` (GMT) | SHA-256 |
|---:|---|---:|---:|---|---|
| 1 | [Next build manifest](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/2ULIz42kiDF35uGW-fSRV/_buildManifest.js) — 19:08:28.3232610–19:08:30.1567939Z | 200 | 7,571 | 2026-11-12 08:59:36 | `43EB46D6C1987EDEBD8C621D05AAA1DD7AB5C2BFA47A4CAC74AC2AB3DD6AFEC1` |
| 2 | [_app chunk](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/pages/_app-6e380dbba77d4bc0.js) — 19:08:54.2818552–19:08:55.1938975Z | 200 | 667,506 | 2026-11-12 08:59:35 | `46C05CE47FCDA900C5C963E8709A6FC7CDDF4AC0C755597F5CD77A79391D3735` |
| 3 | [utils source map](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/utils-68c78bcd6eca2ebe.js.map) — 19:09:37.8142874–19:09:40.5653797Z | 404 | 499 | 2026-11-18 19:09:40 | `13F5D3F4DD814E48E29BB814DB08FF9AAA571E0819734281B27F04E07DC34321` |
| 4 | [milestone source map](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/pages/uni-chart/milestone-244421f21dc9ee9e.js.map) — 19:09:52.8971492–19:09:53.8674392Z | 404 | 515 | 2026-11-18 19:09:54 | `2D39F5B90DE56E0E185E5F65061DF3D2385BD3C2B588C73D187900AB93AF832A` |
| 5 | [Webpack runtime](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/webpack-c267f9c6b891e8e8.js) — 19:10:12.5823582–19:10:12.9951826Z | 200 | 7,163 | 2026-11-12 08:59:33 | `7EC03187DDFD62CAD09CBB2E2D9817387DF3D643DE62280C720E133FE03552A3` |
| 6 | [Milestone page with 2019 query](https://yobang.tencentmusic.com/chart/uni-chart/milestone/?milestoneType=2&year=2019) — 19:12:03.9997416–19:12:09.4807167Z | 200 | 158,646 | 2026-11-18 19:12:08 | `595A0FF5F8E99D8D3485F3DCF8DB5E1209CB39D14A78374B2BFB5F3777681E6E` |

Body and header files are under [`source-snapshots/`](../data/runtime/tme-uni-2019-kp-s4-data-followup-CN-2019-20261118-01/source-snapshots/). Structured request metadata is in [`source-captures.json`](../data/runtime/tme-uni-2019-kp-s4-data-followup-CN-2019-20261118-01/source-captures.json) and [`request-log.json`](../data/runtime/tme-uni-2019-kp-s4-data-followup-CN-2019-20261118-01/request-log.json); route observations are in [`data-route-evidence.json`](../data/runtime/tme-uni-2019-kp-s4-data-followup-CN-2019-20261118-01/data-route-evidence.json).

## Next actionable retrieval

If this lead remains a priority, the next shard should permit one normal public page execution with the `KP` and `S4` requests captured from the browser’s ordinary client flow, counting all page-resource and data requests against its limit. Any returned list still needs first-party evidence of annual scope, date window, rank basis, and full depth before it can be treated as an annual provider series.
