# Limitations — Milestone 1A

Milestone 1A contains an operational authorized-file path and a fixture-tested Apple Music contract. Milestone 1D rights activation has been approved for all listed sources, but technical availability, credentials, quotas, and observed historical coverage remain source-specific. No historical provider coverage has been inferred from current-chart interfaces.

The local application service used for acceptance is process-local; production persistence is represented by the normalized PostgreSQL schema and migrations. Provider activation, credentials, procurement, and authenticated samples require separate human approval. Lyrics and content interpretation are outside scope.

Unresolved identity reduces canonical-track sample sizes. ISRC claims may conflict and are intentionally non-unique. Provider metrics are not comparable across units, and no unified popularity score is produced.

## YouTube-specific limitations

YouTube Data API `mostPopular` is a current video ranking, not a historical YouTube Music song chart. The nine-country fixtures prove mapping and comparison behavior only; they do not establish real territorial availability, historical completeness, collection frequency, or permission to retain production responses.

Standard network execution remains bounded and opt-in. A live run still requires API credentials, retention/refresh handling, derived-metric permission, quota controls, and a concrete market/chart/window. Quota exhaustion is reported separately from ordinary authorization failures. Deleted/private videos and missing statistics remain visible as unavailable/null rather than being converted to zero.

## Global multi-source extraction limitations

The local MGD and Kaggle artifacts are currently materialized as multi-year
archives, but they cover different source windows and chart semantics. Chartmetric
capability discovery and the bounded pilot prove access to a tested endpoint, not
historical completeness. Pro-Música is Brazilian and aggregate by design. The
YouTube region inventory is not a music-chart archive. Do not compare provider
counts as if they were independent musical events until canonical track and source
precedence review is complete.
