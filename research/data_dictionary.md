# Data dictionary — Milestone 1A

The scientific unit is a recording. `canonical_track_id` identifies a reviewed recording and is nullable on observations. `platform_item_id` identifies the item ranked by its origin platform; multiple YouTube videos may link to one recording without becoming one ranked item.

`platform_code` is the origin service. `source_code` is the provider or authorized file that supplied the observation. `period_start`, `period_end`, and `native_frequency` preserve the source's native period. `position` is one-based. `metric_type` names the provider unit and `metric_value` remains null when absent.

Coverage values are `AVAILABLE`, `MISSING`, `NOT_SUPPORTED`, `NOT_LICENSED`, `NOT_COLLECTED`, and `SOURCE_UNAVAILABLE`. Rights operations are independently granted; approval for import does not imply redistribution.

The five versioned datasets are `track_master`, `chart_observations`, `track_platform_country_summary`, `cross_platform_presence`, and `coverage_matrix`.

## Source extraction fields

`provider` is the supplying source (`MGD`, `CHARTMETRIC`,
`KAGGLE_DHRUVILDAVE`, `PRO_MUSICA_BRASIL`, or `YOUTUBE_DATA_API`).
`origin_platform` is the platform represented by the chart, and is intentionally
independent of `provider`. `country_code` is the source-reported ISO-like market
code; `GLOBAL` is a global territory and is not treated as a country.
`observation_key` preserves a provider's exact event. `canonical_equivalence_key`
is only a candidate key for later cross-source reconciliation.
