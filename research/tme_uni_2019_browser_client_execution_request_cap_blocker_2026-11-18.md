# TME UNI 2019 browser-client execution blocker

This shard was reserved as `codex-tme-uni-2019-browser-client-execution-20261118-01` for an unauthenticated first-party page visit and 2019 tab click, with a 12-request total limit, concurrency 1, and third-party requests blocked. No navigation was performed, and no new network requests were made.

## Why execution stopped

The available CUA browser inventory returned no connected browser surfaces or tabs; Firefox was present in the app inventory but not running. More importantly, the already captured [first-party TME milestone HTML](https://yobang.tencentmusic.com/chart/uni-chart/milestone/) (158,646 bytes, SHA-256 `595A0FF5F8E99D8D3485F3DCF8DB5E1209CB39D14A78374B2BFB5F3777681E6E`) contains **15 script URLs on `tencentmusic.com`**. A cold normal page load therefore needs at least 16 counted first-party requests: one navigation plus those 15 static scripts. This exceeds the reservation's cap of 12 before the requested year-tab click and any `KP`/`S4` data calls. The HTML also references one `tam.cdn-go.cn` script, which is third-party and excluded from that count; no request was made for it.

The prior first-party page chunk shows the `最高由你得分 TOP10` component calling `KP({milestoneType:"2",year:n})` and `S4()` for `uniIndexTopYearList`; the component also invokes its initial calls on mount and invokes `KP` when a tab changes. The new shard reused those captured sources locally, without making additional requests. The browser-use inventory and the full 15-URL count are preserved in [`ui-surface-observation.json`](../data/runtime/tme-uni-2019-browser-client-execution-CN-2019-20261118-01/ui-surface-observation.json) and [`static-asset-inventory.json`](../data/runtime/tme-uni-2019-browser-client-execution-CN-2019-20261118-01/static-asset-inventory.json). Raw reused first-party HTML and chunks are in [`source-snapshots/`](../data/runtime/tme-uni-2019-browser-client-execution-CN-2019-20261118-01/source-snapshots/).

## Disposition

This is a request-budget blocker, not evidence that TME lacks a public 2019 payload. No KP response, S4 year list, rows, or current client behavior were observed in this shard. Published depth, annual scope, period, numeric rank semantics, score formula/order, ties, gaps, unresolved positions, and chart market remain unknown. The packet records zero recovered rows separately from unknown depth and keeps the candidate **review-only**.

For another attempt, the reservation would need to allow more than the 16 first-party requests already listed in the HTML, plus the client data calls, and a normal browser surface or mechanism capable of serial request capture. Do not infer the annual period or positions from the tab label.
