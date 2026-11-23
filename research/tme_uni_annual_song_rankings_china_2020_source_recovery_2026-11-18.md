# TME UNIChart 2020 source recovery

Date: 2026-11-18. This additive research note reconciles the official TME 2020 annual report with every ranked table in the 2020 Kugou whitepaper section. It does not modify the active provider index, catalogs, core selection, or earlier packets.

## Finding

TME’s [official chart archive](https://chart.tencentmusic.com/) lists `2020腾讯音乐榜年度榜单` and links to the [2020 annual report](https://yobang.tencentmusic.com/annual_report/), titled `由你音乐榜2020年度盘点`. Its route chunks expose embedded first-party table JSON. The TME `年度TOP10歌曲` / `default` list has 10 rows at ranks 1–10 and a footnote ranking each song by its highest single-week new-song score in the charting period. Its rows, artists, scores, and ranks exactly match all ten rows in the Kugou whitepaper’s `2020新曲热度 TOP10` table. The first-party TME rows are stored in `data/runtime/tme-uni-annual-source-research-CN-2020-20261118-01/ranked_rows.jsonl`.

This establishes a first-party TME annual song-ranking table. Its exact interval and listener geography are unstated, so leave `period_start`, `period_end`, and `chart_market_code` unset. `publisher_country_code=CN` identifies the publisher’s jurisdiction only.

## Kugou table count reconciliation

There are 19 ranked tables across printed pages 61–70 of the [Kugou 2020 whitepaper](https://mat1.gtimg.com/qqcdn/xw/whitePaper/20210110.pdf), with total depth 170 and 170 visible ranked rows. The “six” count in the prior reservation refers to the six TME-attributed song lists: one annual new-song heat TOP10, four separately ranked quarterly new-song heat TOP5 lists, and one new-song share TOP10. Two additional page-61 digital-album tables are also footnoted to TME UNIChart, bringing the complete TME-footnoted/section-attributed count to eight lists (six song lists plus two album lists). The earlier note’s “seven tables identify TME UniChart” can only be reconciled as a grouped-section count that combines the two page-61 album sublists into one section, plus the six song lists; at ranked-list level the corrected count is eight. The sing-along TOP10 has no dedicated source note and remains unattributed. The comment TOP10 explicitly uses QQ Music and NetEase Cloud Music comments. Nine singer-index tables on pages 66–70 use separate singer/index metrics; the star-index tables are identified as Tencent Entertainment Star Index, not TME UniChart.

Two Kugou tables have ties: digital-album purchase speed at #4 and new-song share at #5. The missing following rank labels (#5 and #6) are competition-rank skips, not unresolved positions. No other table has a tie or rank gap. The TME-attributed quarterly TOP5 sublists each contain ranks 1–5. Only the annual new-song heat list exactly matches a TME SPA table; quarterly, share, album, sing-along, comment, and singer lists have no exact TME table/rank/metric crosswalk.

The PDF was already captured and hash-verified in the prior Kugou packet (HTTP 200, 7,095,976 bytes, SHA-256 `19B613FE314FA6D363BC6706CDD8F6DB169E3F88643953C57A41E4089D8E828F`). The new complete table-level reconciliation and qualification details are in [the source-recovery report](../data/runtime/tme-uni-annual-source-research-CN-2020-20261118-01/report.md). First-party raw TME response hashes and metadata are in `source-captures.json`; the 19-table Kugou crosswalk is in `kugou-whitepaper-table-crosswalk.json`; the 21-table official SPA inventory is in `tme-2020-spa-table-inventory.json`.

## Source / qualification status

The official annual-song list qualifies as an ordered first-party TME table, depth 10, 10 rows, no ties, no rank gaps, and no unresolved positions within the published depth. Its annual boundary and market remain unknown. No rows were merged into the active provider index or catalogs; parent review is still required before any integration decision.
