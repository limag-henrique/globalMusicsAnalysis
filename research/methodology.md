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
