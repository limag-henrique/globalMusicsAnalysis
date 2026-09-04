# Milestone 1B acceptance report

Date: 2026-09-04  
Scope: Tasks 17–18 only, building on accepted Milestone 1A

## Outcome

Milestone 1B adds a fixture-tested `YouTubeMostPopularSource` for the public, video-centric current chart contract. It is labeled `YouTube Video Most Popular`, uses `chart_family=YOUTUBE_VIDEO_MOST_POPULAR`, ranks `VIDEO` items, and carries `semantic_equivalence=NOT_YOUTUBE_MUSIC_TOP_SONGS`.

No live YouTube request, API key, provider login, purchase, browser automation, scraping, Git commit, or branch change occurred.

## Adapter evidence

- Builds `i18nRegions.list`, `videoCategories.list`, and paginated `videos.list?chart=mostPopular` requests.
- Enforces page sizes from 1 through 50 and records one quota unit per list request.
- Preserves every raw response page byte-for-byte inside a deterministic base64 envelope.
- Maps video ID, title, channel, publication time, category, rank, optional statistics, and availability state; it never invents ISRC.
- Distinguishes quota exhaustion from ordinary authorization failure.
- Exercises 400, 401, 403, ordinary 429, quota-exhausted 403, timeout, retry exhaustion, malformed JSON, empty charts, deleted/private records, missing statistics, and category changes.
- Network execution fails before transport unless the adapter, source-specific rights grant, and credential provider are all active.

## Nine-country synthetic acceptance

Fixtures cover BR, US, GB, FR, DE, ES, PT, IT, and SE. They validate mapping and UI methodology only; they are not evidence of production or historical coverage.

| Invariant | Result |
|---|---|
| Chart label | `YouTube Video Most Popular` in all nine country views |
| Semantic marker | `NOT_YOUTUBE_MUSIC_TOP_SONGS` |
| Ranked unit | Individual YouTube video |
| Video category | Exposed as `video_category_id` |
| Metric boundary | `2025-03-31_SHORTS_STARTS_OR_REPLAYS` |
| Two videos linked to one recording | Two charted items retained |
| Views and streams | Separate aggregates; no popularity score |

## Gate after 1B

Production YouTube collection remains disabled pending an approved retention/derivatives route and explicit activation. Milestone 1C is a commercial-provider procurement decision and was not started because it requires contracts, samples, pricing, and a human provider selection rather than additional speculative adapter code.

## Verification record

- Non-live tests: 84 passed.
- Ruff: passed.
- Mypy strict: passed for 94 source files.
- Python compileall: passed.
- Docker Compose configuration validation: passed.
- Collection history is append-only and ordered by attempt time, so an outage cannot overwrite earlier available coverage.
- Track/platform/country summaries retain unresolved observations in the denominator while excluding observations resolved to other tracks.
- Snapshot and entry mutation is rejected by SQLAlchemy in every supported test database and by PostgreSQL triggers for direct database writes.
- The shared chart-source payload contract is exercised by the synthetic adapter test.
