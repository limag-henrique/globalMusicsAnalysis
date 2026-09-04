# Methodology — Milestone 1A

Charts are stored as immutable snapshots with source artifacts addressed by SHA-256. Corrections supersede earlier snapshots. Daily and weekly charts remain in their original periods and are aligned only under an explicit policy.

Recording resolution prioritizes exact ISRC evidence. Conflicting claims and title similarity enter a review queue; fuzzy similarity never confirms a link. Canonical-track analyses exclude unresolved rows and report their numerator and denominator.

Persistence reports appearances, distinct native periods, peak, mean and median rank, and Top-10/20/50/100 counts. Streams, views, units, and creations are aggregated separately. Cross-platform overlap uses resolved canonical tracks at the common observed Top N; correlations report shared sample size and are null when insufficient.

## YouTube video chart — Milestone 1B

`YouTube Video Most Popular` is the territorial, current-state `videos.list?chart=mostPopular` construct. Its ranked unit is an individual video and its chart family is `YOUTUBE_VIDEO_MOST_POPULAR`; it is explicitly marked `NOT_YOUTUBE_MUSIC_TOP_SONGS`. Region codes and assignable video categories are discovered through the public Data API contracts rather than treated as a fixed music-chart archive.

Every fixture snapshot records the selected video category, quota units, optional public statistics, and exact raw response pages. Multiple pages retain deterministic rank order. Multiple videos may resolve to one canonical recording, but remain distinct charted items and their views are not silently summed.

The methodology version `2025-03-31_SHORTS_STARTS_OR_REPLAYS` marks the documented change in how Shorts `viewCount` is counted. Results spanning that boundary must expose it rather than treating the metric as methodologically unchanged.
