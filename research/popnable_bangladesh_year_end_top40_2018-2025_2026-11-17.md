# Popnable Bangladesh Top 40 year-end charts, 2018–2025

**Status: review-only; no active index, catalog, or database import.** The candidate packet contains seven 40-rank series for 2018–2023 and 2025, based on rendered page text. A fresh audit made ordinary HTTP GET requests to both pages for every year 2018–2025. All 16 responses were HTTP 403 challenge pages, not chart bodies; no year was newly verified from raw ranked-page HTML, so no import-ready packet was created. Raw responses and their request metadata are preserved separately.

## Scope and coverage

Popnable’s [Bangladesh Top 40 index](https://popnable.com/bangladesh/charts/top-40) lists year-end charts. The existing rendered captures of first-party pages for [2018](https://popnable.com/bangladesh/charts/top-40/year-2018), [2019](https://popnable.com/bangladesh/charts/top-40/year-2019), [2020](https://popnable.com/bangladesh/charts/top-40/year-2020), [2021](https://popnable.com/bangladesh/charts/top-40/year-2021), [2022](https://popnable.com/bangladesh/charts/top-40/year-2022), [2023](https://popnable.com/bangladesh/charts/top-40/year-2023), and [2025](https://popnable.com/bangladesh/charts/top-40/year-2025) state January 1 through December 31 for the named year. Each title is “Top 40 Songs Bangladesh, Year-End [year]”; the rendered page 1 has ranks 1–20 and page 2 has ranks 21–40. Those snapshots contain no scores.

The review-only candidate packet has **seven separate provider series and 280 rows**: 40 positions each for 2018–2023 and 2025. Its rows retain Popnable’s displayed ranks, titles, and artist credits. They remain based on rendered text snapshots and have not been promoted or merged into Spotify/YouTube rankings.

The 2024 first page has an earlier rendered-text snapshot, but no local raw chart body was available; page 2 had only previous retrieval-status and cross-check records. In this audit, ordinary requests to both 2024 URLs returned challenge pages, so 2024 remains excluded with no ranking rows.

## Fresh first-party HTTP audit

On 2026-11-17, one ordinary GET was made to each listed Popnable page URL. No CAPTCHA was solved and no access control was bypassed. All responses returned HTTP 403 with an HTML body titled “Just a moment...” and challenge markers. Each body was captured as returned. The bodies contained no Bangladesh Top 40 heading, no rank/position text, and no `/bangladesh/song/` links; therefore they provided zero chart rows and could not be compared rank-by-rank with the candidate packet. The existing rendered-text snapshots remain the sole source of its 280 candidate rows.

The request manifest contains the exact requested and final URLs, status, UTC retrieval time, body size, SHA-256, and local path for every response. The table below gives the same body hashes for convenient review.

| Year | Page | Requested URL | HTTP | Retrieved UTC | Bytes | Raw response SHA-256 |
|---:|---:|---|---:|---|---:|---|
| 2018 | [1](https://popnable.com/bangladesh/charts/top-40/year-2018) | 403 | 2026-11-17T14:52:38Z | 5430 | `762f3bd4506dbc4b51aa1585b08d7c84b8b62dfbcfc81948b3ddb4cb2433fe35` |
| 2018 | [2](https://popnable.com/bangladesh/charts/top-40/year-2018?page=2) | 403 | 2026-11-17T14:52:39Z | 5466 | `98f271e8e5a08890c4b160870fc554c733520a9db809647b009675c509e094a9` |
| 2019 | [1](https://popnable.com/bangladesh/charts/top-40/year-2019) | 403 | 2026-11-17T14:52:40Z | 5430 | `dbad1c006e19b507fd8eb3f332b00624e0f668b9eabaee4fed9328de8b956f85` |
| 2019 | [2](https://popnable.com/bangladesh/charts/top-40/year-2019?page=2) | 403 | 2026-11-17T14:52:42Z | 5466 | `97bfbb8afa8e8ae7c219e0ec0b11ce05d1b374e28e03723ccd01d7357d2308ed` |
| 2020 | [1](https://popnable.com/bangladesh/charts/top-40/year-2020) | 403 | 2026-11-17T14:52:43Z | 5430 | `df6bb013eafe67c76ab758430f4b2b0042ee87e284d004d7c213f2407d299784` |
| 2020 | [2](https://popnable.com/bangladesh/charts/top-40/year-2020?page=2) | 403 | 2026-11-17T14:52:44Z | 5466 | `ddb281b55cbd62d1668f8dbe7c90b6fbf4644dc0f4e43d2ef456591acc8cc5f2` |
| 2021 | [1](https://popnable.com/bangladesh/charts/top-40/year-2021) | 403 | 2026-11-17T14:52:45Z | 5430 | `33010662c634e453692fb3ce9b489d2164ae8c8e79138b0b30d1200a5488837f` |
| 2021 | [2](https://popnable.com/bangladesh/charts/top-40/year-2021?page=2) | 403 | 2026-11-17T14:52:47Z | 5466 | `985f470ebf1a8bdee3f52d58ca60dc4e741826876b47ff01132ca5e8f10b4031` |
| 2022 | [1](https://popnable.com/bangladesh/charts/top-40/year-2022) | 403 | 2026-11-17T14:52:48Z | 5430 | `e3f5f9cf7feaf0a1f1dc962eb0ea5cd7ac5cc905f134fadd825511ed6927fd4d` |
| 2022 | [2](https://popnable.com/bangladesh/charts/top-40/year-2022?page=2) | 403 | 2026-11-17T14:52:49Z | 5466 | `fefc3ea9c8882866d158ca10f5e882796d52b4ec3422d62e2d8f408932e9d9f6` |
| 2023 | [1](https://popnable.com/bangladesh/charts/top-40/year-2023) | 403 | 2026-11-17T14:52:51Z | 5430 | `6e9f7e3fb86e0c7a8370f73781d9a6050d632a34fb32e9487751335d9148d234` |
| 2023 | [2](https://popnable.com/bangladesh/charts/top-40/year-2023?page=2) | 403 | 2026-11-17T14:52:52Z | 5466 | `cf3637be31465e3b3da08f02b52e5c599b46e1aae1429ce7bbf79b0c75c09158` |
| 2024 | [1](https://popnable.com/bangladesh/charts/top-40/year-2024) | 403 | 2026-11-17T14:52:53Z | 5430 | `856e24b8ff9f7388f336e329759c6e90dfafa23a08bc64cee97b631f29477173` |
| 2024 | [2](https://popnable.com/bangladesh/charts/top-40/year-2024?page=2) | 403 | 2026-11-17T14:52:54Z | 5466 | `df852275de8393f82cdb5a6e3b835c129dd176330b48609badb12a7317c597a3` |
| 2025 | [1](https://popnable.com/bangladesh/charts/top-40/year-2025) | 403 | 2026-11-17T14:52:56Z | 5430 | `ea3e60b009583b91c80f888f4f5cf03b051982912bb34025f13b782158af6993` |
| 2025 | [2](https://popnable.com/bangladesh/charts/top-40/year-2025?page=2) | 403 | 2026-11-17T14:52:57Z | 5466 | `158de9134f0a7fb3e0a7369135d2b95c068a01c73e1b62974dc4f51b3e83c89a` |

## Methodology, market, and publisher

Popnable’s [About and chart methodology page](https://popnable.com/about) says its Tracking Bot monitors YouTube trends, views, and popularity; it also considers regional influences and trending music. It says AI technologies have been used to analyze and rank songs globally since 2022 and identifies Top 40 Songs as weekly, monthly, and annual charts. It does not give an exact annual weighting formula or song-level scores. Popnable also says an international-channel video can be linked to the artist’s country, while a local-channel video can be linked to the channel’s country. BD is therefore the provider-defined Bangladesh trend market, not evidence of listener geography.

The [Popnable LinkedIn company profile](https://uk.linkedin.com/company/popnable) self-reports headquarters in London and a primary location of London, GB. The candidate packet uses **GB** as profile-reported publisher location; this does not establish legal incorporation or registered jurisdiction. Each ranking remains a separate Popnable/BD provider series.

## Capture and integrity

The candidate’s 14 ranking-page snapshots are web-extractor rendered text, not raw publisher ranking-page bytes. Its existing rankings file contains **280 rows**, **447,532 bytes**, and SHA-256 `7fc82a094a63e4c270a4f0d0a3a898cb9eb053e1f92359e9c391204470808be1`; each included year has positions 1–40 with no duplicates. These hashes verify the rendered text snapshots and ranking file only.

Two independent ordinary-request rounds each preserve all 16 raw response bodies: the first round at 14:52:38–14:52:57Z and the repeat at 14:55:34–14:55:35Z. All 32 responses are HTTP 403 challenge pages with no chart data, so none can supply ranking rows or upgrade any year. The ranking packet remains review-only; no import-ready provider packet was produced. No tests were run, and the active catalog/index and Spotify/YouTube core were not changed.

### Direct HTTP response audit (2026-11-17)

Two fresh ordinary GET rounds were made to each page 1 and page 2 URL for 2018–2025, with cookie handling disabled and no CAPTCHA solving or access-control bypass. The first ran 14:52:38–14:52:57Z; the repeat ran 14:55:34–14:55:35Z. All 32 requests returned HTTP 403 (`text/html; charset=UTF-8`) with a “Just a moment…” challenge page. The preserved response bodies contain no ranked rows, rank/position labels, or song links. These are challenge responses, not chart evidence.

The table below uses the repeat-round response bodies and per-request metadata in `source-snapshots/request-audit-2026-11-17/`; its manifest SHA-256 is `407587f86908333de3a5d574886c586919c2f32368f576518efe6aa310c85d72`. The first-round bodies and `request-manifest.jsonl` are preserved separately in `data/derived/annual_revision/provider_series/popnable-bd-top40-year-end-http-audit-2026-11-17/`; its request-manifest SHA-256 is `18cc87df149a40591318fccb19d9e7f0b124b9c45af98336faea52302d728d0a`. Body hashes below cover the repeat-round response body bytes; both rounds are 403 challenges, not chart data.

| Year | Page | Status | Content type | Bytes | Response body path | SHA-256 |
|---:|---:|---:|---|---:|---|---|
| 2018 | 1 | 403 | `text/html; charset=UTF-8` | 5430 | `source-snapshots/request-audit-2026-11-17/year-2018-page-1.body.bin` | `32aeeb6037120e58818fa26bd28d7649b3043f68864ed264d4cfa525d9bd06c1` |
| 2018 | 2 | 403 | `text/html; charset=UTF-8` | 5466 | `source-snapshots/request-audit-2026-11-17/year-2018-page-2.body.bin` | `c4f471eea202e720ab54d682fb0f32c90551237c3caa556520cd89bbe7b2e6d9` |
| 2019 | 1 | 403 | `text/html; charset=UTF-8` | 5430 | `source-snapshots/request-audit-2026-11-17/year-2019-page-1.body.bin` | `66e1ca9ee113cfc7297ae389852799fb8754da223fd7f2b1cf664b2993b3d04f` |
| 2019 | 2 | 403 | `text/html; charset=UTF-8` | 5466 | `source-snapshots/request-audit-2026-11-17/year-2019-page-2.body.bin` | `a236ab62a951b19c6bf65950fa7bdd06ac6a57aa069a3f18513e4403e22bdbb3` |
| 2020 | 1 | 403 | `text/html; charset=UTF-8` | 5430 | `source-snapshots/request-audit-2026-11-17/year-2020-page-1.body.bin` | `ad083724a68d7ce0d50747a0ffd4cd11cf2ae92e23c94febb2e62c8d63c66539` |
| 2020 | 2 | 403 | `text/html; charset=UTF-8` | 5466 | `source-snapshots/request-audit-2026-11-17/year-2020-page-2.body.bin` | `4efef5d29fa55415770e6d928389f44d3a6be46ed30d4ef13d577d54f9989047` |
| 2021 | 1 | 403 | `text/html; charset=UTF-8` | 5430 | `source-snapshots/request-audit-2026-11-17/year-2021-page-1.body.bin` | `a95de44f50b2ce87fb75556522289f64c6ed89941c6ace60d222d52966daedab` |
| 2021 | 2 | 403 | `text/html; charset=UTF-8` | 5466 | `source-snapshots/request-audit-2026-11-17/year-2021-page-2.body.bin` | `9cfb8da802778acdd3562b1a753501f829fe7afe2fa34cd26bae7def60d236b6` |
| 2022 | 1 | 403 | `text/html; charset=UTF-8` | 5430 | `source-snapshots/request-audit-2026-11-17/year-2022-page-1.body.bin` | `e5ff194ac5f02bc5a3c340b89850f5468f3cc4ed585bd4d370c4411c8266e293` |
| 2022 | 2 | 403 | `text/html; charset=UTF-8` | 5466 | `source-snapshots/request-audit-2026-11-17/year-2022-page-2.body.bin` | `91705130e2f15175960dbeb94708e3a0c6c206ec24e251a4a83c6a1b11ddf3b4` |
| 2023 | 1 | 403 | `text/html; charset=UTF-8` | 5430 | `source-snapshots/request-audit-2026-11-17/year-2023-page-1.body.bin` | `973e6813bb44e4864c943d50d51d6f5b4f3b115c771e21a1427b8a9026f290b2` |
| 2023 | 2 | 403 | `text/html; charset=UTF-8` | 5466 | `source-snapshots/request-audit-2026-11-17/year-2023-page-2.body.bin` | `ab4fdd66201e7aac8f071aa55097031c90f68fb7c47f567ad738d80a9d123af0` |
| 2024 | 1 | 403 | `text/html; charset=UTF-8` | 5430 | `source-snapshots/request-audit-2026-11-17/year-2024-page-1.body.bin` | `0e4e2fb300ef2cbb479fbeb73edbf71a5d07b92f788f70e83b35a687c7d5d7fb` |
| 2024 | 2 | 403 | `text/html; charset=UTF-8` | 5466 | `source-snapshots/request-audit-2026-11-17/year-2024-page-2.body.bin` | `1e37343d91696f663af42b1e35d7fc639771db3ac314321a0579620c74ef6a46` |
| 2025 | 1 | 403 | `text/html; charset=UTF-8` | 5430 | `source-snapshots/request-audit-2026-11-17/year-2025-page-1.body.bin` | `61150f59cf61b6301311149c57e6a661211cb25eb1d667281ea1f55506d6278c` |
| 2025 | 2 | 403 | `text/html; charset=UTF-8` | 5466 | `source-snapshots/request-audit-2026-11-17/year-2025-page-2.body.bin` | `b93d1489cdde11dce78d69f51553684eed030737c3f089863a8ada38d6c2eeca` |


## Files

- Candidate review-only packet: `data/derived/annual_revision/provider_series/popnable-bd-top40-year-end-2018-2025-review-only/`
- Candidate rankings: `data/derived/annual_revision/provider_series/popnable-bd-top40-year-end-2018-2025-review-only/rankings.jsonl`
- Existing rendered source snapshots: `data/derived/annual_revision/provider_series/popnable-bd-top40-year-end-2018-2025-review-only/source-snapshots/`
- First-round raw HTTP challenge bodies and request manifest: `data/derived/annual_revision/provider_series/popnable-bd-top40-year-end-http-audit-2026-11-17/`
- Repeat-round raw challenge bodies and manifest: `data/derived/annual_revision/provider_series/popnable-bd-top40-year-end-2018-2025-review-only/source-snapshots/request-audit-2026-11-17/`
- First-round request metadata: `data/derived/annual_revision/provider_series/popnable-bd-top40-year-end-http-audit-2026-11-17/request-manifest.jsonl`
