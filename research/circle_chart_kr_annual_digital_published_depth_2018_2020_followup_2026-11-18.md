# Circle Chart Korea annual Digital Chart depth, 2018–2020

Follow-up completed 2026-11-18 under reservation `codex-circle-chart-kr-2018-2020-published-depth-followup-20261118-01`. The question was whether first-party Circle Chart sources explicitly call the annual Digital Chart a Top-N list or state an exhaustive end. I made five serialized unauthenticated public GETs to `circlechart.kr` and reused the already captured annual rows, API responses, and official chart-page HTML.

## Finding

**No explicit Top-N or exhaustive published depth was found in the checked first-party sources. Keep exact published depth unknown for all three years.** The year-query pages expose the Circle Chart Digital Chart interface and a “Yearly” period control, but their server-rendered visible text is identical across `targetTime=2018`, `2019`, and `2020`; each still displays the default “Digital Chart 2025” heading and contains no Top 100/Top 200 or exhaustive-end declaration. The normalized visible text has the same SHA-256 for all three responses: `AAE57DB721014FF80DAF7711C7E72169C79A7E10E89BEA0BAC26BD3607EEFA08`.

The official FAQ explains Circle Chart ranking methodology and a general annual aggregation period (January 1 at noon through January 1 of the following year at 11:59), but does not state the number of annual positions published. The Circle Report archive route returned only the report title and search controls in its captured HTML; it did not expose year-specific article entries. This limited archive response is not treated as evidence that no such article exists.

The prior first-party API packets establish recovered rank rows, not publisher-declared depth. In particular, the 2018 API's observed 100-row cap and the 2019/2020 response lengths of 200 are not used as Top-N evidence.

## Separate depth and position accounting

| Year | Published depth | Recovered positions | Recovered rows | Ties in recovered ranks | Gaps within recovered span | Unresolved positions |
|---:|---:|---:|---:|---:|---:|---|
| 2018 | Unknown | 1–100 | 100 | 0 | 0 | Unknown; cannot compute without published depth |
| 2019 | Unknown | 1–200 | 200 | 0 | 0 | Unknown; cannot compute without published depth |
| 2020 | Unknown | 1–200 | 200 | 0 | 0 | Unknown; cannot compute without published depth |

The recovered rows are continuous within each observed span, with one row per position. No publisher-stated rank gaps appeared in the reviewed page/FAQ source set. Positions beyond the highest recovered rank remain unresolved because no exact published depth was found. Keep all three `reported_depth` values null/unknown; do not promote 100 or 200 from the recovered-row counts.

## First-party source evidence

The official [Digital Chart annual page for 2018](https://circlechart.kr/page_chart/onoff.circle?serviceGbn=ALL&termGbn=year&yearTime=3&targetTime=2018), [2019](https://circlechart.kr/page_chart/onoff.circle?serviceGbn=ALL&termGbn=year&yearTime=3&targetTime=2019), and [2020](https://circlechart.kr/page_chart/onoff.circle?serviceGbn=ALL&termGbn=year&yearTime=3&targetTime=2020) each returned HTTP 200 (53,237 bytes). Their respective response-body SHA-256 values are `B886567BFFF94FE1A0413BED0A5B782CA14AEDEF0B94BD4BDCF41B66FB8EEE9C`, `A3FFA963B2136EA423B84B9602AD75B618EC76A0EAEA03D9635CCF0D9A2CC7ED`, and `2E1C8EF32A05A8FA319FA5BD734239041506021D6369190C2987A3441CEDDBB2`. Visible-text normalization removes scripts/styles and HTML markup; the same normalized visible-text hash across these responses confirms the page shell did not render a year-specific rank table or depth statement.

The official [Circle Chart FAQ](https://circlechart.kr/page_community/faq.circle) returned HTTP 200, 86,501 bytes, SHA-256 `577317677513B3AD0DFEEC5791427D1158A2F56668298A36AFCFEEC4DEA04DCB`. Its ranking-method answer describes how the Digital Chart aggregates platform counts; its annual-period answer does not declare Top-N or exhaustive depth. The first-party [Circle Report index](https://circlechart.kr/page_article/list.circle?sgenre=report) returned HTTP 200, 32,060 bytes, SHA-256 `7EF54E865C2947AB88EC20B33D44612A32E01A86492B4839E64FF0DB29AF8C73`; the captured server body contains only the index/search shell, so it adds no depth statement.

The previously captured official chart page used by the annual packets is 53,187 bytes, SHA-256 `67E0F8FBDC045FAE05D893B83B94F72D246D44C0D8B2D450CD0E3F8129C1BD55`. The reused verified annual position packets and API response bodies are copied under [`reused-packets/`](../data/runtime/circle-chart-kr-2018-2020-published-depth-followup-20261118-01/reused-packets/) and [`source-snapshots/`](../data/runtime/circle-chart-kr-2018-2020-published-depth-followup-20261118-01/source-snapshots/). The detailed request timestamps, response headers, sizes, hashes, and reused-capture provenance are in [`source-captures.json`](../data/runtime/circle-chart-kr-2018-2020-published-depth-followup-20261118-01/source-captures.json) and [`request-log.json`](../data/runtime/circle-chart-kr-2018-2020-published-depth-followup-20261118-01/request-log.json). The year-by-year fields are in [`depth-assessment.json`](../data/runtime/circle-chart-kr-2018-2020-published-depth-followup-20261118-01/depth-assessment.json) and [`coverage.json`](../data/runtime/circle-chart-kr-2018-2020-published-depth-followup-20261118-01/coverage.json).

## Recommendation

Leave exact Circle Chart annual Digital Chart published depth unknown for KR 2018–2020. Reconsider only if Circle Chart publishes a year-specific statement explicitly giving a Top-N limit or saying the annual table is exhaustive. No active provider index, catalog, denominator, or core-selection file was edited.
