# Data dictionary — Milestone 1A

The scientific unit is a recording. `canonical_track_id` identifies a reviewed recording and is nullable on observations. `platform_item_id` identifies the item ranked by its origin platform; multiple YouTube videos may link to one recording without becoming one ranked item.

`platform_code` is the origin service. `source_code` is the provider or authorized file that supplied the observation. `period_start`, `period_end`, and `native_frequency` preserve the source's native period. `position` is one-based. `metric_type` names the provider unit and `metric_value` remains null when absent.

Coverage values are `AVAILABLE`, `MISSING`, `NOT_SUPPORTED`, `NOT_LICENSED`, `NOT_COLLECTED`, and `SOURCE_UNAVAILABLE`. Rights operations are independently granted; approval for import does not imply redistribution.

The five versioned datasets are `track_master`, `chart_observations`, `track_platform_country_summary`, `cross_platform_presence`, and `coverage_matrix`.
