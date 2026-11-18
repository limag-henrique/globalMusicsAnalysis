# Billboard JAPAN year-end JAPAN Hot 100, 2018–2024

## Finding

Billboard JAPAN’s first-party `YEAR END (JAPAN)` pages expose rank-ordered `JAPAN Hot 100` tables for reporting years 2018 through 2024. Each table contains ranks 1–100, with no missing or duplicate rank labels. This yields seven separate provider-year series and 700 observed ranked memberships.

These are additive, provider-specific national chart records. Their positions remain separate from Spotify, YouTube, Apple Music, and other publishers; they do not add membership to or reduce gaps in the project’s 150,000-position Spotify/YouTube selection.

The official annual index says the year-end tables use annual total points and gives the following month-level coverage spans. The pages do not provide exact day boundaries, so `period_start` and `period_end` are null in the packet. A reporting year here is not a January–December calendar year.

## Publisher and chart market

- Each chart page identifies `JAPAN Hot 100` and `YEAR END (JAPAN)`. This supports `chart_market_code=JP`.
- The page footer says the site is published by Hanshin Contents Link Corporation under license from Billboard Media, LLC. Hanshin Contents Link’s [official company profile](https://hcl-c.com/english/company-info.html) lists its headquarters in Osaka, Japan, supporting `publisher_country_code=JP`.
- Publisher jurisdiction and chart market are represented independently, even though both are Japan in this series.

## Captured rankings

| Reporting year | Coverage stated by Billboard JAPAN | Rows | Ranks | Rank 1 | Rank 100 |
|---:|---|---:|---|---|---|
| 2018 | 2017年12月–2018年11月 | 100 | 1–100 | Lemon — 米津玄師 | J.S.B. HAPPINESS — 三代目 J Soul Brothers from EXILE TRIBE |
| 2019 | 2018年12月–2019年11月 | 100 | 1–100 | Lemon — 米津玄師 | Pop Virus — 星野源 |
| 2020 | 2019年12月–2020年11月 | 100 | 1–100 | 夜に駆ける — YOASOBI | Crazy F-R-E-S-H Beat — Snow Man |
| 2021 | 2020年12月–2021年11月 | 100 | 1–100 | ドライフラワー — 優里 | 怪獣の花唄 — Vaundy |
| 2022 | 2021年12月–2022年11月 | 100 | 1–100 | 残響散歌 — Aimer(エメ) | それを愛と呼ぶなら — Uru |
| 2023 | 2022年12月–2023年11月 | 100 | 1–100 | アイドル — YOASOBI | 踊 — Ado |
| 2024 | 2023年12月–2024年11月 | 100 | 1–100 | Bling-Bang-Bang-Born — Creepy Nuts | Habit — SEKAI NO OWARI |

The coverage labels are transcribed from the corresponding official year-end index page. The index does not state the exact first and last day within those months. The rank tables display song title and artist alongside each integer position. They do not display point totals; no scores were reconstructed.

## First-party sources and capture evidence

For each year, the rank table is at the official Billboard JAPAN `charts/detail?a=hot100_year&year=YYYY` page; the coverage statement is on `charts/year_end?year=YYYY`:

- [2018 rank table](https://www.billboard-japan.com/charts/detail?a=hot100_year&year=2018) · [2018 year-end index](https://www.billboard-japan.com/charts/year_end?year=2018)
- [2019 rank table](https://www.billboard-japan.com/charts/detail?a=hot100_year&year=2019) · [2019 year-end index](https://www.billboard-japan.com/charts/year_end?year=2019)
- [2020 rank table](https://www.billboard-japan.com/charts/detail?a=hot100_year&year=2020) · [2020 year-end index](https://www.billboard-japan.com/charts/year_end?year=2020)
- [2021 rank table](https://www.billboard-japan.com/charts/detail?a=hot100_year&year=2021) · [2021 year-end index](https://www.billboard-japan.com/charts/year_end?year=2021)
- [2022 rank table](https://www.billboard-japan.com/charts/detail?a=hot100_year&year=2022) · [2022 year-end index](https://www.billboard-japan.com/charts/year_end?year=2022)
- [2023 rank table](https://www.billboard-japan.com/charts/detail?a=hot100_year&year=2023) · [2023 year-end index](https://www.billboard-japan.com/charts/year_end?year=2023)
- [2024 rank table](https://www.billboard-japan.com/charts/detail?a=hot100_year&year=2024) · [2024 year-end index](https://www.billboard-japan.com/charts/year_end?year=2024)
- [Hanshin Contents Link official company profile](https://hcl-c.com/english/company-info.html)

The packet preserves 15 source-page bodies (seven rank tables, seven year-end index pages, and the company profile). Their source URLs, UTC retrieval timestamps, byte counts, SHA-256 digests, and local snapshot paths are recorded in the packet manifest. All fetched chart/index/profile pages returned HTTP 200; each saved snapshot’s SHA-256 matched its manifest digest.

## Capture and validation

The rank, title, and artist fields were parsed from the official HTML table cells (`td.rank_td`, `p.musuc_title`, and `p.artist_name`). The capture process required the official year-end and Japan chart labels, the footer publisher statement, and the year’s coverage span before writing the packet. For every year, it required exactly 100 rows and the sequential rank list 1–100, plus nonempty title and artist fields. A separate packet check confirmed 700 rows, seven series, no duplicate `(series_id, position)` pairs, a matching ranking-file SHA-256, and matching hashes for all 15 source snapshots.

The annual index describes the ranking basis as annual total points. It does not expose per-song point totals or exact date boundaries in these pages. This capture verifies the published page rows and their source lineage; it does not adjudicate song identity across publishers, verify lyrics, or establish core Spotify/YouTube cohort membership.

## Packet

The additive packet is `data/derived/annual_revision/provider_series/billboard-japan-hot100-year-end-2018-2024/`. It contains `rankings.jsonl` with 700 rows, one provider-specific series per reporting year in `manifest.json`, and the 15 hashed source snapshots. The packet explicitly marks `merged_into_150k_spotify_youtube_selection=false`.
