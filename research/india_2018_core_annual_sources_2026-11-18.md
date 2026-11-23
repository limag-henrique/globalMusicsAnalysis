# India 2018 first-party annual-source review

Reviewed 2026-11-18 for reserved shard IN/2018. The six source bodies in this packet are byte-identical copies of the earlier immutable capture set; no new public requests were made. Spotify annual rankings, YouTube Charts Top Songs, and the Google India Rewind video list are assessed as separate provider/category evidence. No active index, catalog, or core selection was modified.

## Qualification

**Review-only; no complete first-party numeric India annual song ranking was verified for 2018.** No Spotify India annual song rows or YouTube Charts India Top Songs rows were recovered. Google India’s official 2018 Rewind article does publish a separate **Top Trending Music Videos: India** section containing ten linked titles. It has no numeric rank labels or scores, and is not the same chart family as YouTube Charts Top Songs. Its ten visible entries are preserved as display-order observations only; none are imported as numeric positions or song-chart rows.

## Spotify: India annual songs chart not verified

Spotify’s official newsroom page announces that Spotify is available in India in 2019. That launch evidence postdates the requested 2018 market-year. The captured first-party annual route `https://charts.spotify.com/charts/view/regional-in-annual/2018` returned HTTP 200 with an 8,367-byte generic chart-app HTML shell; it contains no India/year labels or track rows. The response is not a chart. No 2018 India ranks, depth, ties, gaps, exact measurement dates, or method were recovered. [Spotify India launch announcement](https://newsroom.spotify.com/2019-02-26/spotify-launches-in-india/) · [Spotify annual route probe](https://charts.spotify.com/charts/view/regional-in-annual/2018)

## YouTube Charts: Top Songs not verified for India 2018

Google India announced its YouTube Music Charts launch in September 2019. Its later chart documentation distinguishes daily and weekly families; the current Top Songs methodology aggregates views across official music videos, user-made videos using the official song, and lyric videos. Neither that later method nor the 2018 annual route shell supplies a 2018 India year-end row set. The first-party annual route returned HTTP 200 with a 42,416-byte app shell and no chart rows. No Top Songs positions, ties, gaps, published depth, exact boundaries, or 2018-specific method were verified. The separate Rewind list below is not substituted for Top Songs. [Google India Music Charts launch](https://blog.google/intl/en-in/products/platforms/youtube-charts-launch-in-india/) · [YouTube Charts methodology](https://support.google.com/youtube/answer/9014376?hl=en) · [2018 Top Songs route probe](https://charts.youtube.com/charts/TopSongs/in/annual/2018?hl=en)

## Separate category: 2018 Rewind Top Trending Music Videos: India

The Official Google India Blog article dated December 6, 2018 includes the exact heading **Top Trending Music Videos: India** and ten linked video titles. The article describes 2018 top trending videos and top music videos as according to time spent watching, sharing, commenting, liking, and more; it does not specify an exact formula for this list or exact date boundaries. The section publishes no numeric rank labels or per-item scores. Thus the observed list contains ten unique linked titles, while publisher-declared depth and numeric rank positions remain unknown. Display sequence is preserved in [separate review-only item records](../data/runtime/core-annual-source-research-IN-2018-20261118-01/youtube-india-rewind-2018-trending-music-videos-display-review.jsonl), not treated as rank order. The captured HTML contains the same section and same ten video IDs twice; these repeated markup occurrences are deduplicated once and are not a second set of entries. The article section has no pagination. [Official Google India 2018 Rewind article](https://india.googleblog.com/2018/12/youtuberewind-is-here.html)

| Provider/category | Published scope observed | Numeric rank labels | Numeric positions recovered | Period and method |
|---|---|---|---|---|
| Spotify India annual songs | No India chart rows; route returned generic shell | None | 0 | Requested 2018 annual route; local service availability announced in 2019; no 2018 method/period source |
| YouTube Charts India Top Songs | No 2018 rows; route returned generic shell | None | 0 | India Charts launch announced in 2019; no 2018 annual method/period source |
| Google India Rewind: Top Trending Music Videos: India | 10 unique titles; section markup repeated twice; declared depth not stated | None | 0; ten display entries only | 2018 label; exact dates and list-specific formula unstated; page gives broad engagement criteria |

Ties and gaps are not observable where the publisher did not print rank numbers. The 10 Rewind entries must remain a separate video-category series and do not satisfy a numeric annual song-chart series or a 500-position core quota.

## Capture provenance and integrity

The packet reuses six existing official-source captures with their original request URL, effective URL (or recorded limitation), UTC retrieval time, HTTP status, content type, byte count, and SHA-256. The capture manifest traces each copy to its original raw file under `data/runtime/parallel-extraction/codex-india-core-source-20261117-01/captures/`. No new public requests were needed (0 of 6 permitted). `SHA256SUMS.txt` lists packet artifacts and snapshots. The immutable reservation and prior input hashes are recorded in `manifest.json`.

**Conclusion:** retain this shard as review-only. Keep the 2018 Rewind Top Trending Music Videos list distinct from song charts. Do not infer ranks from its displayed sequence or treat later Spotify/YouTube chart families as 2018 annual data.
