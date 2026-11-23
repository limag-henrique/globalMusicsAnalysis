# India 2018 national-publisher annual song source review

## Finding and disposition

**Review-only: no eligible first-party annual song ranking from an India-based national publisher was verified within the eight-request limit.** This shard is scoped to India-based publishers, separate from Spotify, YouTube Charts, and Google Rewind. Do not create a provider series from the out-of-scope Apple Music India playlist: Apple is a US publisher, although its localized playlist is for India. That Apple source is included only as an exclusion comparator; its previously existing ranked rows were not copied or re-imported in this packet.

The Apple Music source is “Top 100 Songs 2018: India,” published on Apple’s India storefront. The pre-existing capture reports 99 songs and exposes explicit ranks 1–99, but the publisher country is US and therefore it does not satisfy this India-national-publisher reservation. The title/count discrepancy remains unresolved; the inherited Apple manifest records reported depth as null and missing positions as empty, so rank 100 is not asserted as missing or unresolved. Its source HTML hash is `ac89a2b1f87ce39a71a771934ee05e2b66d44a5c67c0e42ddce7dc17f565db93`; the source URL is [Apple Music India playlist](https://music.apple.com/in/playlist/top-100-songs-2018-india/pl.7df4aa48d58c4689bad274bfe7c54cce). A byte-identical source copy is preserved as out-of-scope evidence only; the existing provider-manifest path and hash are recorded as a reference, not copied.

## Bounded publisher search

Eight public search requests were made serially. Searches targeted Gaana/Times Internet, JioSaavn, and Wynk/Airtel. They did not identify a first-party nationwide 2018 ranked song list from those India-based publishers. Secondary search results described Wynk’s “Your Year in Music 2018” as user-personalized and surfaced regional Punjab, Himachal Pradesh, and Haryana Top 10 lists; neither establishes an eligible first-party national chart. The regional list appeared in a secondary report, [NewZNew’s Wynk Top 10 article](https://www.newznew.com/wynk-music-announces-top-10-songs-of-2018-in-punjab-hp-haryana/). A syndicated/secondary description of the personalized feature appeared at [RadioandMusic](https://radioandmusic.com/press_releases/wynk-music-steps-up-personalization-of-user-experience-with-an-exciting-innovation-your-year-in-music-2018/). These are leads only, not source evidence used to qualify a series. Search queries and outcomes are recorded in `search-attempts.jsonl`.

The request cap is exhausted, so other possible India-based publishers and unindexed first-party archives remain unresolved. This report does not claim that no such 2018 source exists.

## Candidate and position assessment

| Candidate | First-party national annual ranking verified? | Depth / positions / ties / gaps | Disposition |
|---|---|---|---|
| Apple Music “Top 100 Songs 2018: India” | No for this shard: publisher country US, despite India market localization | Existing packet has explicit ranks 1–99; title says Top 100 while count says 99, so depth is unknown. Its manifest records no missing positions; no #100 is asserted as absent or unresolved. | Excluded comparator only; do not import or merge |
| Wynk/Airtel annual candidate | No first-party ranked national source captured | Unknown; search surfaced only personalized/year-trend descriptions and a secondary report of three state-level Top 10s | Review-only lead |
| Gaana / JioSaavn | No first-party 2018 national annual ranking found within this bounded search | Unknown | Search outcome only |

No provider series, numeric positions, ties, or gaps are qualified in this national-publisher shard. There is no verified India-based national publisher chart period, declared depth, or methodology to report. No index, catalog, or core selection was changed.

## Capture and request provenance

The single raw primary-source file in this packet is an inherited Apple Music India storefront page, retained solely to document why that India-market list is out of scope for a reservation limited to India-based publishers. The inherited record says HTTP 200, retrieved `2026-11-17T06:57:18Z`, 713,574 bytes. Its original metadata did not record a separate effective URL or content type; these remain unknown. No new source GET was made. The packet records eight serial public searches and preserves the reservation and source hashes in `manifest.json` and `SHA256SUMS.txt`.

**Conclusion:** keep this reservation review-only. The Apple list is a separate US-publisher/India-market provider series, not the answer to this India-based national-publisher shard. Wynk regional/person-specific leads remain unverified without first-party national ranking evidence.
