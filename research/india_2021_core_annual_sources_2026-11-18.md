# India 2021 first-party annual song-chart source review

Reviewed 2026-11-18 for reserved shard IN/2021. Spotify and YouTube evidence is kept provider-specific and each chart/list category is separate. No active index, catalog, selection data, or weekly archive was modified.

## Qualification

**Review-only; no core-complete India 2021 annual song series is verified.** The first-party sources located do not provide a recoverable India annual song rank list with a known period and chart definition. YouTube India published an explicit Top 10 **Music Videos** list, but this is a video list, not a Top Songs aggregation. Spotify’s first-party year-end song rankings captured here are Global and U.S.; Spotify also described data-driven local-market playlists, but no India-ranked list, depth, or rank method was recovered.

## YouTube: India Top 10 Music Videos (review-only)

Google India’s YouTube article dated December 2, 2021 presents content and trends from YouTube in 2021. Its **Top Music Videos** section is an image, not a text table; the official graphic is titled **TOP 10 MUSIC VIDEOS** and visibly labels ranks 1–10. The exact displayed depth is ten, all positions 1–10 are present, and no ties or gaps are indicated. The image does not state a precise measurement window or year-specific ranking method, and its rows have no individual video IDs. Text in the ten image rows is transcribed into the packet as displayed, with line breaks and spacing normalized for JSONL; no song/recording identity normalization is performed. [Official India 2021 year-end article](https://blog.google/intl/en-in/products/youtube-unveils-indias-most-popular-creators-and-videos-of-2021/) · [Official Top Music Videos graphic](https://storage.googleapis.com/gweb-uniblog-publish-prod/images/IN_Top_MV_TOP_10.max-1000x1000.jpg)

This list must remain separate from a song chart. YouTube’s India Charts launch article defines weekly **Top Songs** as an aggregation of organic views across official song versions (including official music videos, official uses in user-generated content, and lyric videos); it separately defines weekly **Top Music Videos** as the most-viewed official videos. That earlier chart description is useful to identify the distinction, but it does not establish that the 2021 year-end graphic used the same calculation or period. [YouTube Charts launch and chart-family descriptions](https://blog.google/intl/en-in/products/platforms/youtube-charts-launch-in-india/)

The article also has separate Top Trending Videos and creator categories. Only the Top Music Videos graphic is represented by the ten-row review file; none of the other lists were blended into it. Because the source ranks videos, these ten rows contribute no core annual song membership. Rows 2 and 7 are image-only Devanagari captions; the source graphic is retained for verification, and those captions should be checked before any title normalization.

## Spotify: no verified India annual song ranks

Spotify’s December 1, 2021 Wrapped article says the hub included **Top Tracks & Artists of 2021** data-driven playlists featuring music from top artists globally and in a listener’s local market. It does not specifically name India, publish an India track list, state playlist depth or ordering methodology, or establish exact dates for an India list. The same article describes **Your Top Songs 2021** as a personalized playlist, which is not a country chart. The official 2021 Wrapped hub link redirected to a generic page that displayed an error, and Spotify’s current playlist search yielded no readable India list. [Spotify Wrapped 2021 announcement](https://newsroom.spotify.com/2021-12-01/the-wait-is-over-your-spotify-2021-wrapped-is-here/)

Spotify’s separate year-end ranking article publishes **Most Streamed Songs Globally** and **Most Streamed Songs in the U.S.**, with positions 1–5 in each list. Both have contiguous displayed ranks, with no ties indicated; the page does not specify an exact start/end date. These are not India ranks, so they are preserved as out-of-market reference rows and excluded from IN. [Spotify 2021 global and U.S. lists](https://newsroom.spotify.com/2021-12-01/what-the-world-streamed-most-in-2021/)

The official 2021 Wrapped media kit contains global/U.S. assets and a general Top Tracks playlist-cover asset; it exposed no India song ranking. [Spotify Wrapped 2021 media kit](https://newsroom.spotify.com/media-kit/spotify-wrapped-2021/)

First-party search attempts and the inaccessible Spotify playlist/hub paths are listed in `search-attempts.jsonl`. Press summaries and reposts were not used to assert India ranks because no Spotify-hosted ranked source or official link to one was verified.

## Do not derive an annual list from the weekly archive

The archived YouTube Top Songs weekly data is not an independent annual chart. The existing audit records all 52 Thursdays from 2021-01-07 through 2021-12-30 for each of 44 chart codes (43 country codes plus Global), but 420 repeated native-key/week groups have conflicting view counts; one group also has conflicting title and artist values. The file’s captured SHA-256 is `503ebb8ae1112d5e83915ba83605cc53d3edfafcf9edfdcb0900cae6eff3e3e4`. No annual totals or positions were derived from it. See the prior [duplicate-key conflict audit](youtube_weekly_2021_duplicate_key_conflicts_2026-11-17.md) and the [weekly archive capture manifest](../data/raw/zenodo-23645386-youtube-audit-20261117/capture-manifest-2021-2026-20261117-v1.json). The repeated observations must remain unresolved until an authoritative correction or justified duplicate-resolution rule is found.

## Reservation, packet, and capture provenance

The immutable reservation is `data/runtime/parallel-extraction/codex-core-india-2021-20261118-01.json`. It records the IN/2021 selection row (500 Spotify positions; status `QUOTA_FILLED_COMPLETE_CALENDAR`) and its SHA-256, plus the selection-manifest and country-years file hashes. The additive review packet is [`data/runtime/core-annual-source-research-IN-2021-20261118-01/`](../data/runtime/core-annual-source-research-IN-2021-20261118-01/). It contains separate YouTube video-list and Spotify out-of-market review manifests, raw page/image captures, extracted review rows, failed-search records, and `SHA256SUMS.txt`.

Six source captures are recorded with requested/effective URL, original UTC retrieval timestamp, HTTP status, content type, byte length, SHA-256, and parser/reference. The 2019 YouTube chart-method snapshot is explicitly marked as reused from the completed IN/2020 packet rather than re-requested. All captures in this packet returned HTTP 200, and hashes are checked in `SHA256SUMS.txt`.

**Conclusion:** retain this shard as review-only. Do not classify the YouTube video list, Spotify global/U.S. rankings, personalized playlists, or unresolved weekly view-sums as the core India 2021 annual song series.