# Nigeria 2025 year-end Top 100: TurnTable Charts

Research note: 2026-11-17. TurnTable’s 2025 year-end list is captured as a separate national-publisher series. It does not fill or modify Spotify/YouTube core positions.

## Primary-source findings

TurnTable’s [2025 Year-End Charts Summary](https://www.turntablecharts.com/news/2042) identifies a “Top 100 Songs” category and states a tracking period of “November 2024 – December 2025.” The two linked official chart images are headed “Official Nigeria Top100,” print ranks 1–100, and display “December 2024 – November 2025.” The period statements conflict; both are preserved and `period_start` / `period_end` remain null.

The images identify the chart method as “Streaming + Airplay.” They do not publish component weights or artist credits. I transcribed the 100 numeric ranks and song titles from the images; the official [Top Ten Songs of 2025 article](https://www.turntablecharts.com/news/1991) supplies supporting artist credits for ranks 1–10. Credits for ranks 11–100 remain blank rather than being inferred from other charts.

At rank 3, the ranked image says “Laho II,” while the numbered Top Ten article lists “Laho.” The same article’s narrative says “Laho II” is credited on the Year-End Charts and describes its points across versions. The ranked-image wording is retained and the title variation remains documented.

## Provider-specific import

Packet [`turntable-charts-ng-2025-year-end-top100`](../data/derived/annual_revision/provider_series/turntable-charts-ng-2025-year-end-top100/manifest.json) contains `TURNTABLE_CHARTS_YEAR_END_SONGS_NG_2025`: 100 observed positions, reported depth 100, chart market NG, publisher TurnTable Charts. The series remains separate from the Spotify/YouTube core. Period bounds remain unresolved because the article and images disagree.

Raw HTTP captures, image response headers, retrieval times, and SHA-256 hashes are in [`source_snapshots`](../data/derived/annual_revision/provider_series/turntable-charts-ng-2025-year-end-top100/source_snapshots/).

- Rankings JSONL: `6ee23363778cc0a1913a12f6930e8338d98414befbfc99952a6ce4b50aa065f2`
- Official summary page: `8bd5088fce11e701c87705fcb6ac431e0b5a6db22fb80e6ac3a32d05ed145c9f`
- Ranked images positions 1–50: `c7a6df297c63461d504c631721cafd28f29e933686403215cb9bd3ddc127c824`
- Ranked images positions 51–100: `93159d17c767eaa91ce6d5d24084667856f39d0b627f3d33542baeea36a0e417`
- Top Ten article: `143903a44788194e9b7c5df0020d5528ecc614ec6ab61f0585387f0629b39f20`

The first image contains ranks 1–25 in its left column and 26–50 in its right column; the second contains ranks 51–75 and 76–100. No external ranking reconstruction was used.
