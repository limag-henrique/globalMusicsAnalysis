# Billboard JAPAN Hot Animation year-end series, 2018–2025

Evidence reviewed: 2026-11-18. This note records the official Billboard JAPAN Hot Animation year-end series as its own provider and chart-category series. It does not alter the JAPAN Hot 100 or Apple Music packets, the active provider-series index, catalog, selection data, or lyric outputs.

## Qualification

Each annual rank page is labelled Hot Animation under YEAR END (JAPAN). The paired year-end index lists Hot Animation among Japan’s annual charts and describes annual total points for the reporting period. Billboard JAPAN’s [current chart guide](https://www.billboard-japan.com/common/about/) describes Hot Animation as an anime-song ranking extracted from JAPAN Hot 100, using TV/movie anime tie-in songs and songs by anime voice actors. That category scope makes it distinct from JAPAN Hot 100’s general-song list and from Billboard’s separate Streaming Songs chart.

The series uses provider BILLBOARD_JAPAN, publisher country JP, chart market JP, chart family Hot Animation, category anime_songs, and a different series ID for each reporting year. Each row records the official published rank. These are provider-specific category records, not Spotify or YouTube annual rankings.

## Depth and recovered positions

The official pages show tabs for ranks 1–10 and 11–20. I parsed the official rank, title, and artist cells from each annual page. In every year, published depth is 20 and recovered rows are 20, with the sequential rank labels 1–20.

| Reporting year | Billboard’s year-end index coverage label | Official rank page / annual index | Published depth | Recovered rows and positions | Rank 1 → rank 20 | Ties / gaps / unresolved positions |
|---:|---|---|---:|---|---|---|
| 2018 | 2017年12月～2018年11月 | [rank page](https://www.billboard-japan.com/charts/detail?a=anime_year&year=2018) · [index](https://www.billboard-japan.com/charts/year_end?year=2018) | 20 | 20; 1–20 | 打上花火 — DAOKO × 米津玄師 → 進化理論 — BOYS AND MEN | none / none / 0 |
| 2019 | 2018年12月～2019年11月 | [rank page](https://www.billboard-japan.com/charts/detail?a=anime_year&year=2019) · [index](https://www.billboard-japan.com/charts/year_end?year=2019) | 20 | 20; 1–20 | ハルノヒ — あいみょん → ADAMAS — LiSA | none / none / 0 |
| 2020 | 2019年12月～2020年11月 | [rank page](https://www.billboard-japan.com/charts/detail?a=anime_year&year=2020) · [index](https://www.billboard-japan.com/charts/year_end?year=2020) | 20 | 20; 1–20 | 紅蓮華 — LiSA → SPARK-AGAIN — Aimer(エメ) | none / none / 0 |
| 2021 | 2020年12月～2021年11月 | [rank page](https://www.billboard-japan.com/charts/detail?a=anime_year&year=2021) · [index](https://www.billboard-japan.com/charts/year_end?year=2021) | 20 | 20; 1–20 | 炎 — LiSA → NEW ERA — SixTONES | none / none / 0 |
| 2022 | 2021年12月～2022年11月 | [rank page](https://www.billboard-japan.com/charts/detail?a=anime_year&year=2022) · [index](https://www.billboard-japan.com/charts/year_end?year=2022) | 20 | 20; 1–20 | 残響散歌 — Aimer(エメ) → 明け星 — LiSA | none / none / 0 |
| 2023 | 2022年12月～2023年11月 | [rank page](https://www.billboard-japan.com/charts/detail?a=anime_year&year=2023) · [index](https://www.billboard-japan.com/charts/year_end?year=2023) | 20 | 20; 1–20 | アイドル — YOASOBI → 逆光 (ウタ from ONE PIECE FILM RED) — Ado | none / none / 0 |
| 2024 | 2023年12月～2024年11月; exact dates 2023-11-27 to 2024-11-24 | [rank page](https://www.billboard-japan.com/charts/detail?a=anime_year&year=2024) · [index](https://www.billboard-japan.com/charts/year_end?year=2024) · [annual chart article](https://www.billboard-japan.com/d_news/detail/144171/2) | 20 | 20; 1–20 | Bling-Bang-Bang-Born — Creepy Nuts → カーテンコール — 優里 | none / none / 0 |
| 2025 | 2024年12月～2025年11月; exact dates 2024-11-25 to 2025-11-23 | [rank page](https://www.billboard-japan.com/charts/detail?a=anime_year&year=2025) · [index](https://www.billboard-japan.com/charts/year_end?year=2025) · [annual chart announcement](https://www.billboard-japan.com/special/detail/5050) | 20 | 20; 1–20 | ライラック — Mrs.GREEN APPLE → 太陽が昇らない世界 — Aimer(エメ) | none / none / 0 |

For 2018–2023, the year-end index supplies month-level coverage labels; the rank-table/index captures do not state exact day boundaries. The official 2024 annual report page gives the exact period 2023-11-27 through 2024-11-24, and the 2025 annual report gives 2024-11-25 through 2025-11-23. Those dates are stored only for the years with that explicit evidence. Point totals are not shown in the captured rank tables and remain null.

## Ties, gaps, and unresolved positions

- Eight qualified series, one per reporting year, with published depth 20 each.
- 160 ranked memberships total. This is a category-specific count, not a count of unique songs across other Billboard charts.
- All 160 rank labels are recovered as published, from 1 through 20 for each year.
- No duplicated rank labels, tied positions, missing rank labels, or unresolved positions were found.
- The source pages publish the ordered table, not the annual point totals. For 2018–2023, exact day boundaries remain unresolved from the captured rank/index pages.

## Review-only boundaries

- Hot Animation is an anime-song category. Its official guide describes extraction from JAPAN Hot 100 based on anime tie-ins and anime voice-actor songs. Do not treat it as an unrestricted Japan all-songs ranking or merge it with the separate JAPAN Hot 100 category.
- The year-end index lists other distinct categories, including Streaming Songs, Hot Albums, and artist charts. None is substituted into this packet.
- Billboard’s World year-end pages are outside this Japan market series.
- Official annual summary articles for 2024 and 2025 corroborate the category and exact periods; ranking rows are transcribed from the official annual Hot Animation rank pages.
- No review-only rank positions were promoted into the packet.

## Packet and hashes

The additive packet is data/derived/annual_revision/provider_series/billboard-japan-hot-animation-year-end-2018-2025/. It contains:

- manifest.json with eight distinct annual series, published depth, positions, period/source metadata, and source inventory.
- rankings.jsonl with 160 rows. Published ranks are preserved without inference.
- source_snapshots/ with the eight official Hot Animation rank pages, eight annual index pages, the official chart-methodology page, publisher profile, and official 2024/2025 annual-report cross-checks.

The rankings.jsonl SHA-256 is 5ad6efb7de8da476ea11ed7f2d5f65890c135c3fab7cd70c0515d3315e4dadf0. All 20 source snapshot hashes in the manifest were recomputed and matched. Publisher attribution follows the Billboard JAPAN footer naming Hanshin Contents Link Corporation under license from Billboard Media, LLC; the official [company profile](https://hcl-c.com/english/company-info.html) lists its headquarters in Osaka, Japan.