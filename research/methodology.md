# Methodology — Milestone 1A

Charts are stored as immutable snapshots with source artifacts addressed by SHA-256. Corrections supersede earlier snapshots. Daily and weekly charts remain in their original periods and are aligned only under an explicit policy.

Recording resolution prioritizes exact ISRC evidence. Conflicting claims and title similarity enter a review queue; fuzzy similarity never confirms a link. Canonical-track analyses exclude unresolved rows and report their numerator and denominator.

Persistence reports appearances, distinct native periods, peak, mean and median rank, and Top-10/20/50/100 counts. Streams, views, units, and creations are aggregated separately. Cross-platform overlap uses resolved canonical tracks at the common observed Top N; correlations report shared sample size and are null when insufficient.

## YouTube video chart — Milestone 1B

`YouTube Video Most Popular` is the territorial, current-state `videos.list?chart=mostPopular` construct. Its ranked unit is an individual video and its chart family is `YOUTUBE_VIDEO_MOST_POPULAR`; it is explicitly marked `NOT_YOUTUBE_MUSIC_TOP_SONGS`. Region codes and assignable video categories are discovered through the public Data API contracts rather than treated as a fixed music-chart archive.

Every fixture snapshot records the selected video category, quota units, optional public statistics, and exact raw response pages. Multiple pages retain deterministic rank order. Multiple videos may resolve to one canonical recording, but remain distinct charted items and their views are not silently summed.

The methodology version `2025-03-31_SHORTS_STARTS_OR_REPLAYS` marks the documented change in how Shorts `viewCount` is counted. Results spanning that boundary must expose it rather than treating the metric as methodologically unchanged.

## Global multi-source corpus

Milestone 1D rights activation covers all providers listed in the project. The source
inventory still reports technical capability and collection status separately, so an
approved source with no credential or unsupported endpoint remains explicitly absent
from observed coverage rather than being treated as complete.

Source observations retain `provider`, `origin_platform`, market, chart, native
period, rank, metric and raw provenance. `CanonicalTrack` remains the research
identity; provider-native IDs are claims or evidence, never the central key.
Equivalent MGD, Kaggle and Chartmetric observations are not deleted. A later
canonical chart-entry layer must apply an explicit precedence rule and emit a
`SOURCE_CONFLICT` review record when values disagree.

Markets are discovered per source. The global corpus is the union of legitimate
source capabilities; comparable and balanced corpora are derived subsets with
documented thresholds, not hardcoded country lists.

## Article analytics

Persistence is measured in native chart periods per resolved recording and also
reports the occupied calendar span from the first period start to the last period
end. Market "anxiety" is operationalized as period-to-period Top-N turnover:
new entries, exits, retained tracks, Jaccard similarity, turnover rate, and mean
rank displacement. Genre variation uses distinct resolved tracks by market/year;
Jensen–Shannon distance compares the resulting distributions.

Virality is kept at the video/platform-item level. Linked videos are counted
individually; feature exports use the best rank, maximum views, and median views,
not an unqualified sum across videos. Content prevalence excludes unannotated
track/category cells from its denominator while retaining score zero as observed
absence. No causal explanation of a market is inferred from these descriptive
outputs alone; country, genre, year, rank, and virality interactions are modelled
as associations and require authorized lyrics/annotations.

### Procedimento realizado até 2026-09-11

The current article section reports the procedure and status below. The scientific
unit is a recording: `canonical_track_id` identifies a resolved recording, while
each chart observation retains its provider, origin platform, market, chart, native
period, rank, metric, and raw provenance. A YouTube video remains a distinct ranked
item even when it is linked to a recording.

1. **Source inventory and acquisition.** Source capabilities and rights were
   inventoried before ingestion. MGD was normalized as historical Spotify Top 200
   data from 2017-01-01 to 2022-03-13: 68 markets and 21,257,472 observations.
   Kaggle Spotify Charts was imported separately for validation: 70 regions and
   26,173,514 observations. Pro-Música Brasil has an inventory of 6 items and a
   current public capture of 50 rows. YouTube Data API has a current snapshot for
   111 regions: 3,037 video observations and 1,678 distinct videos. Chartmetric
   historical access is still a bounded pilot, not a completed longitudinal
   backfill.
2. **Identity and reconciliation.** Exact Spotify ID/ISRC evidence is preferred;
   title and artist similarity cannot confirm an identity by itself. The current
   `track_master` contains 126,213 canonical tracks. The unified catalog preserves
   47,434,073 source observations (47,431,036 track rows and 3,037 video rows).
   This is not a final sum of deduplicated sources: complete cross-source
   deduplication remains pending, so equivalent observations are retained and
   traceable rather than deleted.
3. **Eligibility.** The comparable corpus requires at least 95% coverage, three
   years, and a median chart depth of 100. Fifty-five of 68 cells passed these
   thresholds. Unresolved observations are excluded from canonical-track analyses,
   with numerator and denominator rules documented.
4. **Article datasets.** Persistence counts native periods and calendar span.
   Market renewal/“anxiety” is Top-N turnover with entries, exits, retention,
   Jaccard similarity, turnover rate, and rank displacement. Genre variation is
   measured by market/year distributions and Jensen–Shannon distance. Viral reach
   remains at the video level. Content prevalence excludes unannotated cells from
   its denominator and treats scores as observed classifications, not causal
   explanations.
5. **Lyrics and Gemini.** Lyrics are collected through the configured cascade,
   with source, text version, status, and audit information retained; ambiguous
   matches are rejected. Gemini receives the complete lyric with numbered lines and
   returns structured JSON containing language, English translation, semantic
   dimensions, evidence, and quality flags. The append-only process is resumable:
   completed tracks are skipped and provider/model failures are recorded separately.
   ADC is configured for Google Cloud project `project-bae72195-c4bf-4177-bca`,
   while the current client also supports the configured `GEMINI` environment key.

Current limitations are explicit: the 126,213 tracks are not the fully deduplicated
union of every source; YouTube is a current video snapshot rather than YouTube Music
history; Chartmetric historical coverage is incomplete; and lyrics/annotations
depend on source coverage and authorization. `GLOBAL` is not a country. Article
tables must report source, period, denominator, missingness, and artifact version.
