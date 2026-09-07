# Global market coverage

The current global-first inventory exposes more than the former nine-country
configuration: MGD contains 68 markets with non-empty observations, Chartmetric
reports 73 currently accessible Spotify capabilities/market codes, and YouTube
reports 111 official regions. These sets are not interchangeable: they differ
in platform semantics, dates, ranking depth and whether data has actually been
collected.

The detailed dynamic cross-provider table is [market_capabilities.csv](market_capabilities.csv).
The imported MGD date-level coverage table is [global_market_coverage.csv](global_market_coverage.csv).

For a comparable corpus, require explicit minimums for chart family, ranking
depth, temporal continuity and source quality. For a balanced panel, stratify
after geographic enrichment; do not select markets solely by population or
because they have the most rows.
