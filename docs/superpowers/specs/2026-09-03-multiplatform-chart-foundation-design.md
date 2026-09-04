# Multiplatform Historical Chart Foundation — Design Specification

**Status:** Proposed for user review  
**Date:** 2026-09-03  
**Research window:** configurable; exploratory target `2021-01-01` through the latest legitimately available date  
**Geography:** BR, US, GB, FR, DE, ES, PT, IT, SE  
**Evidence:** `research/historical_sources_assessment.md` and `research/spotify_official_capabilities_2026-09-03.md`

## 1. Goal and boundary

Build an auditable, reproducible record of ranked music observations by original platform, country, and native chart period. The scientific observation is:

```text
charted item × origin platform × country × native chart period × rank
```

When the charted item can be defensibly resolved to a recording, it also links to a `CanonicalTrack`. A recording is not a composition. Remixes, remasters, live, acoustic, sped-up, slowed, clean/explicit, and rerecorded versions remain distinct when identifiers or evidence indicate different recordings.

This milestone excludes lyrics, NLP, LLMs, thematic classification, sociological interpretation, human content annotation, adjudication, and gold standards.

## 2. Research finding that controls implementation

Official access does not imply permission for scientific analysis. The current evidence does not approve any platform API as a complete historical 2021-present corpus for all nine countries:

- Apple Music Charts is current-state only and its public terms do not grant this research use; Apple Music Feed expressly prohibits analysis.
- YouTube Data API `mostPopular` is current-state, video-centric, not YouTube Music Top Songs, and standard policies constrain retention and derived metrics.
- YouTube Music has the correct music-chart construct but no documented public chart API/export.
- Spotify lacks a documented Charts API and its current policy expressly blocks analysis/derived metrics without written permission.
- Amazon Music is closed beta and its “Top Tracks” is personalized rather than a national chart.
- Soundcharts and Chartmetric expose historical chart interfaces but require authenticated coverage evidence and a research/publication license.
- Luminate is the strongest documented historical candidate, particularly from 2022, but publication and replication require negotiated rights.
- YouTube Researcher Program is a promising academic route for YouTube data, not a retroactive YouTube Music chart archive.

Therefore every operation is fail-closed through a provider-specific rights gate. Adapters may exist and be tested against local fixtures while network execution remains disabled.

## 3. Domain vocabulary

| Term | Meaning |
|---|---|
| Origin platform | Consumer platform whose ranking is represented, such as Apple Music or Spotify |
| Source provider | Party/file/API that supplied the observation, such as Apple, Soundcharts, Chartmetric, Luminate, or a university dataset |
| Charted item | The native ranked entity: catalog song, video, music-video rollup, or another provider-defined object |
| Canonical track | A project-level recording identity independent of platform |
| External identifier claim | A source-attributed assertion connecting an identifier to a canonical track |
| Chart definition | Methodologically distinct ranking series with a platform, provider, country, frequency, depth, and metric |
| Snapshot | Immutable capture of one chart definition for one native period/observation time |
| Entry | One ranked item inside a snapshot |
| Native period | The source's actual daily, weekly, or other period; weekly observations are never expanded into seven days |
| Rights profile | Versioned legal/contractual decision governing allowed operations for one source |

Soundcharts, Chartmetric, and Luminate are source providers, not origin platforms, unless a future chart genuinely originates from their own methodology. A Soundcharts-supplied Spotify chart records `source_provider=SOUNDCHARTS` and `origin_platform=SPOTIFY`.

## 4. Architecture

Use a modular monolith with explicit domain ports:

```text
FastAPI / CLI / Streamlit
        │
Application services
        ├── RightsGate
        ├── ChartIngestionService
        ├── TrackResolutionService
        ├── CoverageService
        ├── MetricsService
        └── ExportService
        │
Domain ports
        ├── ChartSource
        ├── HistoricalChartProvider
        ├── ChartFileImporter
        └── MetadataProvider
        │
Provider adapters
        ├── AppleMusicChartSource
        ├── YouTubeMostPopularSource
        ├── YouTubeMusicChartSource (disabled)
        ├── SpotifyChartSource (disabled)
        ├── SpotifyChartFileImporter
        ├── SpotifyMetadataProvider (disabled)
        ├── AmazonMusicChartSource (disabled)
        ├── SoundchartsHistoricalChartSource (pending license)
        ├── ChartmetricHistoricalChartSource (pending license)
        ├── LuminateHistoricalChartSource (pending license)
        └── ManualChartImporter
        │
PostgreSQL + append-only artifact storage
```

FastAPI, CLI, and Streamlit call application services rather than adapters directly. No Redis, Kafka, Celery, or microservices are introduced. Scheduled capture can later use an external scheduler invoking the CLI.

## 5. Adapter contracts

```python
class ChartSource(Protocol):
    source_code: str

    def capabilities(self) -> SourceCapabilities: ...
    def discover_charts(self, countries: tuple[str, ...]) -> tuple[DiscoveredChart, ...]: ...
    def fetch_current(self, request: SnapshotRequest) -> RawChartSnapshot: ...


class HistoricalChartProvider(ChartSource, Protocol):
    def available_periods(self, chart: ChartKey, window: DateWindow) -> tuple[ChartPeriod, ...]: ...
    def fetch_period(self, request: HistoricalSnapshotRequest) -> RawChartSnapshot: ...


class ChartFileImporter(Protocol):
    importer_code: str

    def preview(self, artifact: ArtifactInput, schema: SchemaProfile) -> ImportPreview: ...
    def import_file(self, request: FileImportRequest) -> ImportResult: ...


class MetadataProvider(Protocol):
    source_code: str

    def lookup(self, reference: ExternalReference) -> tuple[MetadataCandidate, ...]: ...
```

`SourceCapabilities` declares current/history support, native frequencies, maximum documented depth, supported identifier namespaces, metric types, and whether network execution is enabled. A capability is evidence, not an authorization; `RightsGate` is evaluated separately for every operation.

## 6. Provider strategies

### Apple Music

`AppleMusicChartSource` models `GET /v1/catalog/{storefront}/charts`, `types=songs`, `chart=most-played`, and a requested limit no greater than 200. It maps Apple catalog ID, ISRC when present, title, artists, album, release date and precision where available, content rating/explicit indication where available, genre names as platform metadata, storefront, response order, and raw payload.

The endpoint has no documented historical date parameter. It may capture current observations prospectively only after rights approval. Retrieval time must not be misrepresented as a provider-declared chart period: `observed_at` is required; `effective_period_start/end` stay null unless the provider supplies them.

The adapter is implemented/tested with recorded synthetic fixtures but `network_enabled=false` until a reviewed rights profile authorizes fetch, retention, analysis, and publication.

### YouTube Data API

`YouTubeMostPopularSource` records `chart_family=YOUTUBE_VIDEO_MOST_POPULAR`. It uses region codes and a separately discovered video category; it must never be labeled YouTube Music Top Songs. The ranked unit is a YouTube video. Video ID, title, channel, published time, category, position, statistics when permitted, and the raw response are retained under their applicable rules.

Several videos may link to one `CanonicalTrack`, but each remains a distinct charted item. No automatic summation occurs. Standard network execution remains disabled until retention and derived-metric authorization are documented; the YouTube Researcher Program is evaluated in parallel.

### YouTube Music

`YouTubeMusicChartSource` is a disabled interface only. No scraping, browser automation, or private endpoint replay. An authorized export is ingested through a dedicated schema profile in `ManualChartImporter` or a future `YouTubeMusicChartFileImporter` after rights approval.

### Spotify

`SpotifyChartSource`, `SpotifyChartFileImporter`, and `SpotifyMetadataProvider` remain rights-gated and disabled by default. No Charts scraping, automated login, or private endpoints. Spotify identifiers are ordinary external identifier claims, never canonical identity.

### Amazon Music

`AmazonMusicChartSource` remains disabled. Personalized `/browse/tracks/top` is not implemented as a national chart. The interface is retained for a future approved territorial chart or licensed dataset.

### Historical commercial providers

`SoundchartsHistoricalChartSource`, `ChartmetricHistoricalChartSource`, and `LuminateHistoricalChartSource` implement `HistoricalChartProvider` only after provider selection, coverage extract, data dictionary, sample payload, price approval, and contractual approval of retention, academic analysis, aggregate publication, collaboration, and replication.

Procurement priority is Luminate, Soundcharts, then Chartmetric. This priority is not an authorization or purchase decision.

## 7. ER model

```text
platforms 1──N platform_items
platforms 1──N chart_definitions

data_sources 1──N rights_profiles 1──N rights_grants
data_sources 1──N source_artifacts
data_sources 1──N chart_definitions
data_sources 1──N collection_runs

countries 1──N chart_definitions
chart_definitions 1──N chart_snapshots 1──N chart_entries
chart_definitions 1──N coverage_cells

canonical_tracks N──M artists via track_artists
canonical_tracks 1──N track_external_ids
platform_items N──M canonical_tracks via platform_item_track_links

chart_entries N──1 platform_items
chart_entries N──0..1 canonical_tracks

track_resolution_candidates N──1 platform_items
track_resolution_decisions N──1 platform_items

analysis_runs N──M chart_snapshots via analysis_run_inputs
analysis_runs 1──N exports
audit_log → versioned decisions and administrative actions
```

### Required tables and invariants

`platforms`: only origin surfaces (`APPLE_MUSIC`, `SPOTIFY`, `YOUTUBE_VIDEO`, `YOUTUBE_MUSIC`, `AMAZON_MUSIC`, future values).

`data_sources`: supplying systems/files (`APPLE_MUSIC_API`, `YOUTUBE_DATA_API`, `SOUNDCHARTS`, `CHARTMETRIC`, `LUMINATE`, `MANUAL_AUTHORIZED_FILE`).

`rights_profiles`: immutable, versioned, effective-dated, source-specific review records. Status is `PENDING`, `APPROVED`, `DENIED`, or `EXPIRED`.

`rights_grants`: normalized allowed/denied operations: `FETCH`, `IMPORT`, `STORE_RAW`, `STORE_NORMALIZED`, `ANALYZE`, `EXPORT_AGGREGATE`, `REDISTRIBUTE_ROWS`, `SHARE_WITH_COLLABORATORS`.

`canonical_tracks`: recording-level title, duration and release evidence; no privileged platform ID.

`track_external_ids`: namespace/value claims with source artifact, provider, confidence, asserted time, and review decision. `(namespace, normalized_value, canonical_track_id)` is unique; `(namespace, normalized_value)` is deliberately non-unique so conflicting claims are surfaced rather than silently merged.

`platform_items`: native charted object with `item_kind` (`CATALOG_TRACK`, `VIDEO`, `MUSIC_VIDEO_ROLLUP`, `OTHER`), origin platform, provider-native ID, raw display metadata, and provenance.

`platform_item_track_links`: versioned mapping of native items to recordings. Multiple YouTube videos may map to one recording.

`chart_definitions`: origin platform, provider, country, name, chart family, native frequency, ranking depth, ranked-item kind, metric type, methodology reference/version, applicable rights profile, and active flag.

`chart_snapshots`: definition, observation time, optional provider effective-period bounds, artifact, parser/collector versions, checksum, entry count, status, and optional `supersedes_snapshot_id`. Updates/deletes are prohibited; corrections create a new snapshot.

`chart_entries`: snapshot, platform item, nullable canonical track, position, raw title/artist, provider item ID, raw ISRC, metric value/type, previous/peak position, time-on-chart, and provider payload. `canonical_track_id` is nullable so unresolved observations are never discarded.

`coverage_cells`: chart definition and native period with exactly one state: `AVAILABLE`, `MISSING`, `NOT_SUPPORTED`, `NOT_LICENSED`, `NOT_COLLECTED`, `SOURCE_UNAVAILABLE`. Attempts are separately retained in `collection_runs`.

## 8. Track resolution

Resolution order:

1. normalized ISRC claim;
2. exact provider/platform identifier already linked;
3. provider-documented cross-platform equivalence;
4. exact normalized artist + title + compatible duration/release evidence;
5. fuzzy candidate generation;
6. explicit review decision.

States are `MATCHED_EXACT`, `MATCHED_HIGH_CONFIDENCE`, `NEEDS_REVIEW`, `REJECTED`, and `UNRESOLVED`.

Fuzzy matching may only create `track_resolution_candidates`. It cannot create a confirmed link. Exact rules record the evidence and algorithm version. Conflicting ISRC claims move to `NEEDS_REVIEW`. Resolution decisions are append-only and never overwrite source evidence.

## 9. Temporal and coverage model

`research_start_date` and `research_end_date` live in configuration; `research_end_date=null` means the latest eligible date. No provider-specific historical start is hardcoded.

Daily and weekly observations retain native period start/end and frequency. Weekly entries are never replicated across days. Cross-source comparisons require a named alignment policy. The initial allowed policies are:

- `SAME_NATIVE_FREQUENCY`: compare only definitions with equal frequency and identical period bounds;
- `INTERVAL_OVERLAP`: compare items whose provider-declared periods overlap, reporting the rule in outputs.

There is no implicit conversion. A common observation window is computed only from `AVAILABLE` cells for the selected chart definitions; it is a recommendation, not automatic filtering.

## 10. Metrics

Per canonical track × origin platform × country × chart definition/native frequency:

```text
chart_appearances
distinct_chart_periods
first_chart_date
last_chart_date
peak_rank
mean_rank
median_rank
top_10_periods
top_20_periods
top_50_periods
top_100_periods
stream_sum / mean_streams when metric_type=STREAMS
view_sum / mean_views when metric_type=VIEWS
```

Cross-dimensional outputs include country presence, platform presence, platform-country presence, and period overlap. Metrics never sum different units. No unified popularity score is created.

Top-N overlap uses `effective_top_n = min(requested_top_n, observed depths)` for both definitions. Jaccard is calculated on the resolved canonical-track sets and reports unresolved counts. Spearman/Kendall operate only on shared resolved recordings, report sample size, and never imply causal or methodological equivalence.

A “local hit” is not nationality. If exposed, it means presence in exactly one selected country during an explicitly selected window.

## 11. Import, provenance, and idempotency

Every file/API response is first persisted as a source artifact with SHA-256, byte length, media type, provider, rights profile, acquisition method, retrieval time, requested parameters, collector version, and schema version. Raw artifacts are append-only.

Idempotency uses artifact checksum plus chart definition and native period. Reprocessing the same artifact may produce a new parser run but never duplicate the accepted observation set. Raw and normalized values coexist.

Manual imports support versioned schema profiles, preview, type/date/country validation, row-level errors, duplicate detection, and an explicit confirmation step. They do not infer legal permission: an approved rights profile is required.

## 12. UI and exports

Streamlit filters: country, origin platform, source provider, chart, date range, native frequency, Top N, resolution state.

Views:

- ranking and provenance;
- track/platform-item history;
- Most Frequent Songs;
- By Platform;
- Cross-platform Tracks;
- International Tracks;
- Coverage matrix;
- rights/source status;
- unresolved/review queue.

Exports, each with a manifest:

1. `track_master` — one row per canonical recording;
2. `chart_observations` — one row per native chart entry, retaining unresolved entries;
3. `track_platform_country_summary`;
4. `cross_platform_presence`;
5. `coverage_matrix`.

The rights gate evaluates export type. Row-level redistribution is denied unless explicitly granted.

## 13. Milestone sequence

### Milestone 0 — provider rights and coverage

Maintain provider-specific decisions. No source blocks unrelated approved sources. Network/data operations fail closed.

### Milestone 1A — domain and first ingestion path

Implement domain model, database, rights gate, provenance, manual importer, coverage, core metrics/exports, minimal dashboard, and Apple adapter contract/fixture tests. Manual authorized files are the first operational path. Apple network execution remains disabled until written approval.

### Milestone 1B — YouTube video chart

Implement `YouTubeMostPopularSource` with the video-ranked construct and fixture tests. Live collection requires an approved YouTube rights route, ideally Researcher Program/audited permission.

### Milestone 1C — licensed history

Obtain coverage extracts and contract proposals from Luminate, Soundcharts, and Chartmetric. After human selection and legal approval, create a provider-specific implementation plan and adapter.

### Milestone 1D — Spotify and other later sources

Integrate only licensed/authorized Spotify, YouTube Music, Amazon Music, or institutional files through existing ports. No domain migration should be required solely to add a provider.

## 14. Acceptance criteria

- Removing every Spotify adapter does not break tracks, artists, charts, metrics, UI, exports, or international analysis.
- Provider and origin platform are independently queryable for every observation.
- A YouTube video remains a distinct ranked item after track resolution and is not automatically summed with sibling videos.
- Unresolved entries survive ingestion and appear in coverage/quality reports.
- Raw artifacts and snapshots reject update/delete operations.
- Missing numeric fields remain null.
- Reimporting the same file is idempotent.
- Native weekly observations are never expanded into daily rows.
- Every metric/export lists input snapshots, definition/methodology versions, resolution version, rights profile, parameters, software revision, and checksum.
- The system answers frequency, persistence, Top-N, cross-platform, international, overlap, correlation, coverage, and provenance questions without reading lyrics.
- Unit tests do not call live APIs; contract/integration tests are separately marked and disabled unless credentials and rights are present.

## 15. Deferred decisions and explicit gates

- No purchase or provider signup is authorized by this specification.
- No Apple or YouTube live collection is authorized by “official API” status alone.
- The 2021 start remains exploratory until a verified coverage extract supports it; 2022 may become the balanced start if Luminate is selected.
- Provider selection for 1C requires a separate user decision.
- Any raw-data publication or replication package requires an explicit grant.
- Lyrics/content analysis remains outside this plan.

