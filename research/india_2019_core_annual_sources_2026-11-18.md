# India 2019 core annual source check

**Reviewed:** 2026-11-18 UTC  
**Shard:** India / 2019 / first-party Spotify and YouTube annual song rankings  
**Reservation:** `data/runtime/parallel-extraction/codex-core-india-2019-20261118-01.json`  
**Decision:** No core ranking was promoted. Keep this cell provisional and preserve the year-end video-list evidence as review-only.

## Core cell denominator

The v10 selection snapshot row for `IN/2019` has quota 500, 500 selected positions, zero completed-calendar-year positions, and 500 positions still missing a completed annual source. The selected rows are provisional observations; `missing_position_numbers` is empty because the cohort has not assigned these positions to a completed annual chart. That is not evidence of 500 known chart gaps.

## Spotify

Spotify’s 2019 Wrapped article describes personalized listener recaps and personalized top-track playlists. Spotify’s separate 2019 ranked “Top Lists” article explicitly reports global rankings. Neither captured first-party source publishes a market-level India annual song ranking. [Spotify Wrapped 2019](https://newsroom.spotify.com/2019-12-05/spotify-wrapped-2019-reveals-your-streaming-trends-from-2010-to-now/) · [Spotify global Top Lists 2019](https://newsroom.spotify.com/2019-12-03/the-top-songs-artists-playlists-and-podcasts-of-2019-and-the-last-decade/)

Spotify’s February 2020 India article says the company had reached its first 12 months in India and gives a short “past year” listening summary, including the top three tracks. That is a rolling launch-year summary, not a 2019 calendar-year chart or a full ranked list. [Spotify India first-year summary](https://newsroom.spotify.com/2020-02-27/3-major-streaming-trends-from-spotifys-first-year-in-india/)

A secondary December 2019 report lists ten Spotify India songs, but the captured search found no corresponding public first-party Spotify table or asset. I retained it as a discovery lead only; it is not ranking evidence for promotion. [Gadgets 360 report](https://www.gadgets360.com/entertainment/news/spotify-india-top-artists-songs-playlist-2019-global-decade-arijit-kabir-singh-senorita-2142581)

## YouTube

Google’s 2019 India Rewind page is titled “What India watched in 2019.” The captured HTML contains two adjacent India trend labels (“Top Trending Videos in India” and “Top Trending Music Videos in India”) followed by one shared ordered list of 20 linked videos. It does not provide a separate structural boundary or explicit rank reset that lets this capture identify a music-only subset. Its year-end article also does not state a chart formula, exact measurement dates, or published list depth. [YouTube Rewind: India 2019](https://blog.google/intl/en-in/products/platforms/youtuberewind-what-india-watched-in-2019/)

The official YouTube Charts launch article says India’s Top Songs chart was a weekly product: it combined organic views across official versions of a song and updated weekly. It also describes locally available Top 100 charts. That establishes the separate weekly Top Songs product, not the methodology or denominator of the Rewind video list. I did not recast that video list as an annual Top Songs chart. [YouTube Charts launch in India](https://blog.google/intl/en-in/products/platforms/youtube-charts-launch-in-india/)

The 20 Rewind rows are preserved at `data/runtime/core-annual-source-research-IN-2019-20261118-01/youtube-rewind-review-candidates.jsonl`, with each position, source row text, linked video title, video URL/ID, and source hash. Their accounting is:

- Observed ordered video rows: 20, positions 1–20.
- Published depth: unknown; the page does not say that the list is a complete Top 20.
- Printed ties or gaps: none in the observed contiguous sequence.
- Song-chart assignments unresolved: all 20, because the shared list’s category boundary and video-to-recording identity are not established.
- Positions beyond 20: unknown, not counted as known unresolved positions because the published depth is unknown.

Google’s terms identify Google LLC as organized under Delaware law in the United States; the review rows therefore retain publisher country `US` and market `IN` based on the publisher page’s India scope. [Google Terms of Service](https://www.about.google/policies/terms/)

## Result and next work

The India 2019 core selection remains unchanged: 0/500 completed annual positions and 500/500 missing completed annual positions. No rows from this shard were added to the active provider-series index or supplemental song catalog. The 20 video observations remain a review artifact, not 20 qualified song memberships.

Primary-source response bodies, effective URLs, status, UTC capture time, content type, byte count, and SHA-256 values are in `data/runtime/core-annual-source-research-IN-2019-20261118-01/source-captures.json`; raw HTML is in its `source-snapshots/` folder. The review manifest is `youtube-rewind-review-manifest.json`; `extract_rewind_review.py` reproduces the 20-row extraction from the saved HTML. The review manifest and its rows record the source-depth and identity limits above.

The next core shard is India 2020, separately reserved for the Japan research worker in `data/runtime/parallel-extraction/codex-core-india-2020-20261118-01.json`.

## Direct Spotify annual route probe

I attempted the unauthenticated first-party route `https://charts.spotify.com/charts/view/regional-in-annual/2019`. DNS resolution failed in the local runtime before an HTTP request; there is no status or response capture. This is a failed probe, not evidence that the chart or route is absent. The attempt is recorded in `spotify-india-annual-route-attempt-2019.json`; I will not repeat the unchanged probe unless the network/capture condition changes.
