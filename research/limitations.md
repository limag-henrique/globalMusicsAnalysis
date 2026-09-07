# Limitations — Milestone 1A

Milestone 1A contains an operational authorized-file path and a fixture-tested Apple Music contract. Apple, Spotify, YouTube, YouTube Music, Amazon, and commercial-provider network access remain disabled. No historical provider coverage has been inferred from current-chart interfaces.

The local application service used for acceptance is process-local; production persistence is represented by the normalized PostgreSQL schema and migrations. Provider activation, credentials, procurement, and authenticated samples require separate human approval. Lyrics and content interpretation are outside scope.

Unresolved identity reduces canonical-track sample sizes. ISRC claims may conflict and are intentionally non-unique. Provider metrics are not comparable across units, and no unified popularity score is produced.

## YouTube-specific limitations

YouTube Data API `mostPopular` is a current video ranking, not a historical YouTube Music song chart. The nine-country fixtures prove mapping and comparison behavior only; they do not establish real territorial availability, historical completeness, collection frequency, or permission to retain production responses.

Standard network execution remains disabled. A live run still requires a source-specific approved rights profile, API credentials, retention/refresh handling, derived-metric permission, quota controls, and an explicit activation decision. Quota exhaustion is reported separately from ordinary authorization failures. Deleted/private videos and missing statistics remain visible as unavailable/null rather than being converted to zero.

## Global multi-source extraction limitations

The local MGD corpus is the only source currently materialized as a multi-year
all-market archive. Chartmetric capability discovery proves current access, not
historical availability. Pro-Música is Brazilian and aggregate by design. The
YouTube region inventory is not a music-chart archive. Kaggle is adapter-ready
but not locally acquired in this environment. Do not compare provider counts as
if they were independent musical events until canonical track and source
precedence review is complete.
