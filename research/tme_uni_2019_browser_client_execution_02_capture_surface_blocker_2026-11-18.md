# TME UNI 2019 browser-client execution: capture-surface blocker

This retry was reserved as `codex-tme-uni-2019-browser-client-execution-02-20261118-01`, with a 24-request cap, concurrency 1, and third-party requests blocked. The page was **not** opened and the 2019 tab was not clicked because no suitable browser request-capture surface was available.

## Exact blocker

The current CUA inventory returned an empty browser list and no tabs. Firefox is installed in the app inventory but was not running. CUA can inspect and interact with a page, but its available browser interface has no request interception or serial network capture. The Node REPL could not load either `playwright` or `playwright-core`; both imports returned: `SyntaxError: The requested module './index.js' does not provide an export named 'default'`. No browser was launched, no page request was made, and no request budget was consumed.

The 24-request cap itself was not the blocker. The already captured [first-party milestone page](https://yobang.tencentmusic.com/chart/uni-chart/milestone/) contains 15 script URLs on `tencentmusic.com`; navigation plus these scripts alone implies at least 16 first-party requests on a cold load, before additional assets and `KP`/`S4` data calls. The full URL inventory is in [`static-asset-inventory.json`](../data/runtime/tme-uni-2019-browser-client-execution-02-CN-2019-20261118-01/static-asset-inventory.json).

The reused [first-party milestone page chunk](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/pages/uni-chart/milestone-244421f21dc9ee9e.js), SHA-256 `97000BC5593869AED0D42C58E8046C24624AA7AE1C10C594E779EEDB9DCD8E19`, calls `KP({milestoneType:"2",year:n})` and `S4()` for `uniIndexTopYearList`. The reused [UI chunk](https://cdn-chart.tencentmusic.com/fe/uni-h5/chart-static/base/_next/static/chunks/252-32f2a236d9436a2e.js), SHA-256 `33746289847B531812E8A9A209A626692664EB3D893A589815FE4960EDC723FE`, maps score type 1 to `由你得分`. These earlier captures were copied locally; they do not count as new requests.

## Disposition

This is a tooling blocker, **not** a no-data finding. No current `KP` response, `S4` year list, rows, or browser behavior was observed. The candidate remains review-only: annual scope, period, published depth, numeric rank semantics, score formula/order, ties, gaps, unresolved positions, and chart market remain unknown. `ranked_rows.jsonl` is empty and `coverage.json` records the unknowns as null.

The next attempt needs a connected browser or browser automation runtime that can capture response bodies and headers while serializing or reliably recording every first-party request. The reservation's 24-request limit is available for that retry; do not make hidden or speculative endpoint requests.
