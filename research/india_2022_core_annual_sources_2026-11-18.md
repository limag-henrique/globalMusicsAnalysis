# India 2022 first-party annual song-chart source review

Reviewed 2026-11-18 for reserved shard IN/2022. Spotify and YouTube evidence is provider-specific. YouTube’s year-end music-video list, Spotify’s partial India retrospective, and Spotify’s Global/U.S. year-end lists are separate records. No active index, catalog, selection data, or 2021 weekly archive was modified.

## Qualification

**Review-only; no complete first-party India 2022 annual song ranking was verified.** Spotify’s official 2023 India retrospective confirms that “Excuses” was the top song within a stated ten-song most-streamed cohort for India in 2022, but it does not publish ranks 2–10, exact measurement dates, full methodology, or tie handling. YouTube’s India year-end page publishes a Top 10 **Music Videos** list based on in-country views of official music videos uploaded in 2022. That is a video category, not an aggregate song chart, and it does not state the exact view-accumulation interval.

## YouTube: India Top 10 Music Videos (review-only)

Google India’s article, published December 5, 2022, separates “Top 10 Trending Videos,” “Top 10 Music Videos,” and “Top 10 Shorts.” The official **Top 10 Music Videos** graphic labels positions 1–10 and its footnote says: “Based on in-country views of official music videos uploaded in 2022.” Thus the publisher-declared and displayed depths are both ten, positions 1–10 are recovered, and no gaps or ties are indicated. Exact view-count dates and a year-specific calculation formula are not stated. The graphic supplies truncated video-title and channel strings, no video IDs, and no song recording IDs. The ten image rows are transcribed in the packet with ellipses and punctuation preserved; no title identity normalization is performed. [Official Google India article](https://blog.google/intl/en-in/products/platforms/what-2022s-top-trending-videos-creators-tell-us-about-pop-culture-in-india/) · [Official Top 10 Music Videos graphic](https://storage.googleapis.com/gweb-uniblog-publish-prod/original_images/IN_Top10_Music_Videos_ijqM0hm.jpg)

YouTube’s 2019 India Charts launch article distinguishes weekly **Top Songs**, an aggregation of organic views across official versions of a song, from weekly **Top Music Videos**, which ranks official music videos. This earlier method description helps keep categories distinct; it does not prove the method or exact period behind the 2022 year-end image. [YouTube Charts launch description](https://blog.google/intl/en-in/products/platforms/youtube-charts-launch-in-india/)

The video list remains separate from Google India’s neighboring Top Trending Videos and Top Shorts categories. It is not admitted as a song-level annual series.

## Spotify: India 2022 partial top-ten evidence

Spotify’s April 26, 2023 article says: “Of the 10 most-streamed songs in India in 2022,” four were Punjabi, and identifies “Excuses” by AP Dhillon, Intense, and Gurinder Gill as taking the top spot. This verifies position 1 and a publisher-described cohort depth of ten. Positions 2–10 are not printed in that source and remain unresolved. The article gives no exact start/end dates, detailed counting formula, or tie treatment. No other ranks were inferred. [Spotify India retrospective](https://newsroom.spotify.com/2023-04-26/punjabi-music-gains-worldwide-recognition/)

The result is stored as one recovered rank row and a review manifest with unresolved ranks enumerated. Because the list is incomplete, it does not qualify as a complete provider series.

## Spotify Global and U.S. references (excluded from India)

Spotify’s November 30, 2022 year-end article contains two separate lists: **Most-Streamed Songs Globally** and **Most-Streamed Songs in the U.S.** Each lists five ordered entries, ranks 1–5, with no gaps or ties indicated. The article does not supply an India song list in these sections or exact measurement boundaries. The two lists are captured under their own market codes in spotify-global-us-review-rows.jsonl; neither contributes India ranks. [Spotify 2022 year-end lists](https://newsroom.spotify.com/2022-11-30/the-top-songs-artists-podcasts-and-listening-trends-of-2022/)

## Do not derive annual ranks from the YouTube weekly archive

The 2021 YouTube Top Songs weekly archive is not an independent annual chart. Its existing audit records 420 repeated native-key/week groups with conflicting view counts. No annual sums or positions were derived, and no duplicate-resolution assumption was applied. The archived CSV SHA-256 is 503ebb8ae1112d5e83915ba83605cc53d3edfafcf9edfdcb0900cae6eff3e3e4; see the prior [duplicate-key conflict audit](youtube_weekly_2021_duplicate_key_conflicts_2026-11-17.md) and [weekly archive capture manifest](../data/raw/zenodo-23645386-youtube-audit-20261117/capture-manifest-2021-2026-20261117-v1.json). These conflicts remain unresolved until an authoritative correction or justified duplicate-resolution rule is found.

## Reservation, packet, and capture provenance

The immutable reservation is data/runtime/parallel-extraction/codex-core-india-2022-20261118-01.json. It records the IN/2022 selection row (500 Spotify positions; QUOTA_FILLED_COMPLETE_CALENDAR), row SHA-256 1219349130c89946c27aafe79da51aceb464e4461fd0228af77497eb3868bbf7, selection-manifest SHA-256 aa179f77532f3f27d507e9d0dbc3b238e09c007f5bd31899801302485dba3785, and country-years SHA-256 95478e7431526a3c2e95fcc81056feb043e47c0ad092127ae6812b58a10c4156.

The additive review packet is [data/runtime/core-annual-source-research-IN-2022-20261118-01/](../data/runtime/core-annual-source-research-IN-2022-20261118-01/). It contains the raw article and graphic captures, the recovered review rows, provider-specific manifests, search attempts, and SHA256SUMS.txt. Each direct capture records requested/effective URL, UTC retrieval, HTTP status, content type, byte length, SHA-256, and parser/reference in source-captures.json. The 2019 YouTube chart-family page is marked as a reused capture from the completed IN/2020 packet, not a new request.

**Conclusion:** retain the shard as review-only. Do not merge the YouTube video rankings or Spotify Global/U.S. rows into an India annual song series, and do not fill Spotify India ranks 2–10 by inference.
