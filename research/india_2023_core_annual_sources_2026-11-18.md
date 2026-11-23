# India 2023 first-party annual song-chart source review

Reviewed 2026-11-18 for reserved shard IN/2023. Spotify and YouTube evidence is kept provider-specific; the YouTube Top Music Videos list is not treated as a song chart. No India 2021 weekly sums or India 2022 partial ranks were reused. No active index, catalog, selection data, or YTD series was inspected or modified.

## Qualification

**Review-only; no complete first-party India 2023 annual song series is qualified from these captures.** Google India publishes a complete Top 15 **Music Videos** list with ranks 1–15. It is a video ranking, not a song aggregation, and the source gives no exact measurement interval. Spotify’s 2023 Wrapped Mapped article establishes a local-market “Top Songs” feature starting “since January 1,” but its captured static embed does not safely bind the displayed rank blocks to the India label, and the article states no end date. I therefore assign no Spotify India positions.

## YouTube: India Top 15 Music Videos (review-only)

Google India’s year-end article is dated December 13, 2023 and separates the Top Music Videos image from other annual trending, gaming, Shorts, and creator material. The linked graphic is titled “Top 15 Music Videos,” prints ranks 1–15, and labels itself “2023 • A Year on YouTube.” All 15 positions are recovered with no displayed gaps or ties. The graphic and article do not state exact view-count dates or a detailed ranking formula. Row strings are transcribed from the official image and retain channel labels; no video or recording identity normalization is applied. Rows 1, 5, 8, and 13 contain Devanagari text that should be checked against the preserved image if later normalized. [Official Google India year-end article](https://blog.google/intl/en-in/products/platforms/youtube-content-that-moved-the-nation-in-2023-and-the-creators-behind-it/) · [Official Top 15 Music Videos image](https://storage.googleapis.com/gweb-uniblog-publish-prod/images/2023_IN_EOYT_Top15_Music_List.width-1200.format-webp.webp)

This is a video list, not a Top Songs aggregation. The publisher’s “Top Music Videos” label and the article’s other chart/image categories are kept separate; none of these 15 rows count as India annual song membership.

## Spotify: Wrapped Mapped local-market songs (review-only, no India ranks assigned)

Spotify’s November 29, 2023 “Wrapped Mapped: Top Songs Streamed Around the World” article says it highlights local streaming trends from markets around the world and invites readers to view top songs that “since January 1, have soundtracked 2023.” The article links an interactive map and the embedded page contains an India market label, “Top Songs in India,” alongside 87 five-position text blocks and 87 market/city labels. [Spotify Wrapped Mapped article](https://newsroom.spotify.com/2023-11-29/wrapped-top-songs-worldwide-map/) · [Official interactive map embed](https://newsroom.spotify.com/wp-content/themes/ftr/assets/animations/wrapped2023/WRAPPEDMAPPEDV8/WRAPPEDMAPPEDV8.html)

The static capture places the song blocks and market labels in separate sequences and does not provide a reliable row-to-market identifier. The label at ordinal 64 is “Top Songs in India,” while the rank block at the same ordinal begins “Last Night” by Morgan Wallen; the sequences therefore cannot be paired by ordinal. The visual map’s instructions say to click market boxes, but the captured static HTML does not retain that interactive binding. India’s rank positions, depth, ties, and gaps consequently remain unresolved; no track list is inferred.

The article establishes a start date of January 1, 2023, but no end date. Since the article was published November 29, 2023, complete calendar-year coverage is not confirmed. The map is preserved as an official local-market annual retrospective lead, not as a verified complete calendar-year series.

## Captures, searches, and reservation

The immutable reservation is data/runtime/parallel-extraction/codex-india-2023-core-20261118-01.json. It points to packet root data/runtime/core-annual-source-research-IN-2023-20261118-01. Four first-party response bodies are preserved with requested/effective URL, retrieval time in UTC, HTTP status, content type, bytes, SHA-256, and parser/reference. Spotify’s map embed is stored as the raw gzip response body; a decoded review copy and parser audit are separate derived files. Search attempts and all artifact hashes are recorded in the packet.

**Conclusion:** retain the shard as review-only. Keep YouTube’s 15 video positions outside a song chart. Keep Spotify Wrapped Mapped as an unresolved India source until its interactive list-to-market association and period end are recoverable from a first-party source.
