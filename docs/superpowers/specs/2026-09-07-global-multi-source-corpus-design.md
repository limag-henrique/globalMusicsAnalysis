# Global Multi-Source Music Corpus — Design Specification

**Status:** Approved for implementation
**Date:** 2026-09-07
**Scope:** reproducible source inventory and recent-year ranked-artist corpus

## Goal

Build a source-agnostic, global-first corpus whose observations retain the supplying
provider separately from the original platform. The first useful deliverable is a
solid, auditable list of ranked tracks/artists by country and year, ready for a later
probabilistic analysis.

This milestone does not analyze lyrics or infer cultural preference. It ingests broadly,
preserves low-coverage markets, and applies eligibility only in later analysis.

## Architecture

Existing chart, track, artifact, coverage, and rights modules remain the public seams.
New source adapters implement a small source-inventory interface and emit normalized
`SourceObservation` records containing `provider`, `origin_platform`, `country_code`,
`chart_name`, `period`, `rank`, `track`, `artist`, identifiers, and raw provenance.

Large local datasets are scanned in streaming/chunked mode. Raw files stay in
`data/raw`; normalized observations and summaries are written as compact Parquet/CSV
artifacts plus manifests. A source observation is never silently merged with another
source. Cross-source equivalence is represented by a separate key and conflict report.

## Providers

* `MGD` — local Spotify-origin historical charts from `./mgd`.
* `KAGGLE_DHRUVILDAVE` — Spotify-origin `top200` and `viral50`, downloaded lazily and
  cached when the package is available.
* `CHARTMETRIC` — authenticated capability discovery and resumable chart collection;
  unknown account restrictions become explicit statuses.
* `YOUTUBE_DATA_API` — official region/category discovery and video-most-popular
  collection, never mislabeled as YouTube Music.
* `PRO_MUSICA_BRASIL` — public Brazilian multi-platform aggregate discovery and
  parsers, never labeled Spotify.

## Core invariants

1. `CanonicalTrack` is the research identity; provider IDs are external claims only.
2. `provider` and `origin_platform` are mandatory and independent.
3. All raw observations remain available; canonicalization is additive.
4. A canonical equivalence key includes origin platform, country, chart, period, rank,
   and resolved track. Conflicts produce `SOURCE_CONFLICT` with all values.
5. Markets are discovered from source data/API capabilities, never restricted to a
   static whitelist.
6. Null metrics remain null; missing is not zero.
7. Import is idempotent by checksum and source observation key.
8. The invalid Pro-Música interval `2027-11 → 2026-08` is reported as requiring review;
   other providers continue independently.

## Deliverables

* source/artifact/coverage capabilities and inventory records;
* MGD inspection manifest and chunked import;
* Kaggle adapter with chart separation and cache reuse;
* Chartmetric token cache, discovery, retry/resume behavior;
* YouTube region discovery and official API adapter;
* Pro-Música inventory/downloader/parser seams and date-review status;
* `research/global_market_coverage.md` and `.csv`;
* `research/mgd_kaggle_overlap_report.md`;
* `research/source_inventory.md`, `provider_capabilities.md`, and acceptance report;
* CLI commands for inspection/import/discovery/coverage/conflicts;
* Streamlit source and global coverage views;
* unit, contract, integration, and controlled smoke tests.

## External-access policy

Network calls are opt-in, bounded, and never log credentials or raw secrets. Public
content may be discovered/downloaded; CAPTCHA, authentication walls, paywalls, and
private endpoints are not bypassed. Chartmetric uses the configured refresh token only
for a controlled authenticated request and records blocked/unsupported endpoints.
