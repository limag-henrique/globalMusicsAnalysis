# Spotify India 2022 Top 10 lower-rank follow-up

## Finding

**No new first-party Spotify evidence recovered positions 2–10.** Preserve the existing partial series unchanged: Spotify establishes a ten-song India 2022 cohort and names *Excuses* by AP Dhillon, Intense, and Gurinder Gill as the top spot. Ranks 2–10 remain unresolved; no lower song position was inferred or added.

## Source and cohort accounting

The immutable first-party source is Spotify’s [“Punjabi Music Gains Worldwide Recognition”](https://newsroom.spotify.com/2023-04-26/punjabi-music-gains-worldwide-recognition/), published in April 2023. It says four of the ten most-streamed songs in India in 2022 were Punjabi and identifies *Excuses* as the most-streamed song/top spot. The existing HTML capture is at `data/runtime/core-annual-source-research-IN-2022-20261118-01/source-snapshots/spotify-india-top10-2022-retrospective.html` (160,256 bytes; SHA-256 `bf01c9c9c6fa96d0977e4f56b6a10503dd6b36b20fed1b178f1f2268484aa31e`). This follow-up reused the capture without requesting its URL again.

The v46 partial packet is an immutable input: published depth 10, observed rank 1, unresolved positions 2–10. Its manifest and ranking file hashes are recorded in `source-reuse.json`. The six new serial public searches found no other first-party Spotify India source that resolves any lower positions. Search results that repeated the April 2023 source were not treated as new evidence. Results about Global/U.S. year-end charts, personalized Wrapped features, secondary reports, or non-annual playlists do not resolve this India cohort.

## Positions, ties, period, and method

| Field | Verified state |
|---|---|
| Published depth | 10 songs, per the existing official source statement |
| Recovered positions | #1 only: *Excuses* — AP Dhillon, Intense, Gurinder Gill |
| Unresolved positions | #2–#10 |
| Publisher-stated gaps | None stated; absent positions are unresolved, not declared gaps |
| Ties | Tie handling and any ties are unstated |
| Period | Reporting year 2022; exact start/end dates unstated |
| Method | “Most-streamed” songs; detailed counting method, eligibility rules, cutoff, and numeric scores unstated |

No positions were recovered in this follow-up (`additional-positions.jsonl` is empty). The underlying ranking remains a partial provider series, not a complete ten-row rank list.

## Search log and scope

Six serial unauthenticated public searches were used; the exact queries and result summaries are in `request-log.jsonl`. One surfaced the already captured source again, and no new source URL was fetched. No authentication or paid API call was used. The active provider index, supplemental denominators/catalog, canonical catalog, core selection, and 2021 YouTube weekly archive were not modified.

**Coordinator recommendation:** retain v46 rank 1 and the ten-song published-depth claim as-is; keep positions 2–10 unresolved. Do not import secondary rankings or infer from playlists or daily/weekly charts.
