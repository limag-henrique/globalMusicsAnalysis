# Kugou 2025 Chinese Pop TOP100 playlist: source audit

Date consulted: 2026-11-17. Scope: first-party source claims and public-page exposure only. A separate provider packet was captured after this source audit; the canonical 150,000-position Spotify/YouTube selection was not changed.

## Kugou page

The [Kugou playlist page](https://www.kugou.com/yy/special/single/9180602.html) gives the title `2025年度华语流行TOP100｜全年顶流都在这`, creator `酷狗音乐官方歌单`, and update date `2025-12-15`. Its description calls this an annual TOP100 playlist and says it contains `100首金曲` (“100 hit songs”). This establishes Kugou's stated playlist depth, not recovery of 100 public rows.

The public page numbers entries **01–30**; row 30 is `BEYOND - 海阔天空`. It then says `查看更多内容，请下载客户端` (“download the client to see more”). A direct fetch of the same first-party page's inline `data` array also contained 30 song records. Rows 31–100 were not exposed in the page response inspected on the consultation date.

The page places the item under `精选辑` and calls it a `歌单` (playlist). It provides no ranking or selection methodology, data basis, exact annual period, or listener geography. `华语` identifies the playlist's Chinese-language/editorial scope; it does not specify where listeners are located. The numbered order is visible, but its basis is unstated.

## Project capture

The packet at [`kugou-2025-chinese-pop-top100-sparse-web`](../data/derived/annual_revision/provider_series/kugou-2025-chinese-pop-top100-sparse-web/manifest.json) preserves the 30 visible positions as a sparse, official editorial-playlist series. It records the stated depth as 100, leaves `chart_market_code` unset, and treats ranks 31–100 as unobserved. The active [provider-series index](../data/derived/annual_revision/provider_series/provider-series-index.json) includes this separate series; it does not fill China’s missing Spotify/YouTube annual cell or join the 150,000-position cohort.

## Official TME context and limits

TME's [About Us page](https://www.tencentmusic.com/zh-cn/about-us.html) lists Kugou among TME's four major mobile music products. TME separately documents [TME UniChart rules](https://www.tencentmusic.com/zh-cn/uni-chart.html): that chart uses data from seven named platforms and computes a score from listening popularity, sales, and recommendations. The Kugou playlist page does not identify this playlist as TME UniChart, so those rules do **not** establish the TOP100 playlist's method or audience geography.

## Source URLs

- Kugou playlist: https://www.kugou.com/yy/special/single/9180602.html
- TME About Us: https://www.tencentmusic.com/zh-cn/about-us.html
- TME UniChart rules (separate chart): https://www.tencentmusic.com/zh-cn/uni-chart.html
