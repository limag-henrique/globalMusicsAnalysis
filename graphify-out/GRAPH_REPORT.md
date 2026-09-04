# Graph Report - Promiscuidade Musical  (2026-09-04)

## Corpus Check
- 172 files · ~37,045 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 884 nodes · 2090 edges · 73 communities (49 shown, 24 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 408 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `822f0bb5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Milestone 1A
- Multiplatform Historical Chart Foundation — Design Specification
- Spotify official capabilities and constraints for cross-cultural chart research
- Avaliação de fontes históricas para rankings musicais multinacionais
- Base
- RightsOperation
- enums.py
- api/app.py
- YouTubeMostPopularSource
- AdapterRegistry
- config.py
- exports/manifest.py
- track_summary.py
- overlap.py
- Milestone 1A acceptance report
- test_most_popular_source.py
- 0001_reference_entities.py
- 0003_track_identity.py
- 0005_charts.py
- 0007_collection_coverage.py
- build_session_factory
- AppleMusicTokenProvider
- models/charts.py
- PlatformItem
- ReferenceRepository
- build_engine
- data_dictionary.md
- Limitations — Milestone 1A
- Methodology — Milestone 1A
- apple_music/__init__.py
- files/__init__.py
- adapters/__init__.py
- artifacts/__init__.py
- charts/__init__.py
- charts/models.py
- db/__init__.py
- repositories/__init__.py
- domain/__init__.py
- exports/__init__.py
- chart_observatory/__init__.py
- metrics/__init__.py
- rights/__init__.py
- tracks/__init__.py
- tracks/models.py
- ui/__init__.py
- chart-observatory
- cli.py
- tracks/resolution.py
- Milestone 1B acceptance report
- YouTubeApiKeyProvider
- youtube_data/__init__.py
- ChartPayload
- HttpPolicy
- ChartEntryDTO
- Diligência de provedores — Milestone 1C
- AppleMusicChartSource
- Milestone 1C historical-provider decision record
- Milestone 1C procurement packet
- .for_preview
- .__init__

## God Nodes (most connected - your core abstractions)
1. `RightsOperation` - 58 edges
2. `RightsGate` - 56 edges
3. `HttpPolicy` - 31 edges
4. `YouTubeMostPopularSource` - 30 edges
5. `LocalResearchApplication` - 30 edges
6. `ChartPayload` - 30 edges
7. `Base` - 30 edges
8. `SourceDisabled` - 30 edges
9. `UuidPrimaryKeyMixin` - 29 edges
10. `CreatedAtMixin` - 29 edges

## Surprising Connections (you probably didn't know these)
- `HttpResponse` --uses--> `HttpPolicy`  [INFERRED]
  tests/contract/apple_music/test_chart_source.py → src/chart_observatory/adapters/http.py
- `RetryingTransport` --uses--> `HttpPolicy`  [INFERRED]
  tests/contract/apple_music/test_chart_source.py → src/chart_observatory/adapters/http.py
- `SpyTransport` --uses--> `HttpPolicy`  [INFERRED]
  tests/contract/apple_music/test_chart_source.py → src/chart_observatory/adapters/http.py
- `TokenProvider` --uses--> `HttpPolicy`  [INFERRED]
  tests/contract/apple_music/test_chart_source.py → src/chart_observatory/adapters/http.py
- `KeyProvider` --uses--> `HttpPolicy`  [INFERRED]
  tests/contract/youtube_data/test_most_popular_source.py → src/chart_observatory/adapters/http.py

## Import Cycles
- None detected.

## Communities (73 total, 24 thin omitted)

### Community 0 - "Milestone 1A"
Cohesion: 0.07
Nodes (28): Evidence-driven provider and coverage baseline, Final acceptance criteria for Milestone 1, Global Constraints, Milestone 1A, Milestone 1B — requires a new approval after 1A, Milestone 1C — historical provider decision gate, Milestone 1D — later authorized sources, Multiplatform Historical Chart Foundation Implementation Plan (+20 more)

### Community 1 - "Multiplatform Historical Chart Foundation — Design Specification"
Cohesion: 0.07
Nodes (28): 10. Metrics, 11. Import, provenance, and idempotency, 12. UI and exports, 13. Milestone sequence, 14. Acceptance criteria, 15. Deferred decisions and explicit gates, 1. Goal and boundary, 2. Research finding that controls implementation (+20 more)

### Community 2 - "Spotify official capabilities and constraints for cross-cultural chart research"
Cohesion: 0.07
Nodes (28): 1. Spotify Charts: what is officially documented, 2. Spotify Web API: current resolution/enrichment capability, 3. Rate limits, quotas, and Development Mode constraints, 4. Policy restrictions material to this research design, 5. Capability matrix for the proposed platform, 6. Recommended architecture boundary, 7. Decisions requiring approval before implementation, 8. Minimum acceptance criteria for a legally viable data foundation (+20 more)

### Community 3 - "Avaliação de fontes históricas para rankings musicais multinacionais"
Cohesion: 0.06
Nodes (30): 1. Apple Music API Charts e Apple Music Feed, 1. Luminate — primeiro contato, 2. Soundcharts — segundo contato, 2. YouTube Data API — `videos.list?chart=mostPopular`, 3. Chartmetric — terceiro contato, 3. YouTube Music Charts, 4. Spotify Charts e Web API, 4. YouTube Researcher Program — trilha paralela (+22 more)

### Community 4 - "Base"
Cohesion: 0.22
Nodes (15): DeclarativeBase, UUID, SqlArtifactCatalog, Base, CreatedAtMixin, UuidPrimaryKeyMixin, AnalysisRun, AuditEvent (+7 more)

### Community 5 - "RightsOperation"
Cohesion: 0.06
Nodes (58): ImportPreview, ImportRequest, ImportResult, ImportSink, InMemoryImportSink, ManualChartImporter, ManualRow, Path (+50 more)

### Community 6 - "enums.py"
Cohesion: 0.06
Nodes (48): CollectionRunRepository, CollectionRunResult, date, datetime, Session, UUID, Append-only persistence for collection attempts and their coverage result., CommonObservationWindow (+40 more)

### Community 7 - "api/app.py"
Cohesion: 0.07
Nodes (31): FastAPI, Request, create_app(), application(), apply(), ApplyRequest, preview(), PreviewRequest (+23 more)

### Community 8 - "YouTubeMostPopularSource"
Cohesion: 0.16
Nodes (22): map_categories(), map_regions(), YouTubeRegion, YouTubeVideoCategory, Any, datetime, UUID, YouTubeApiError (+14 more)

### Community 9 - "AdapterRegistry"
Cohesion: 0.14
Nodes (10): NoReturn, DisabledChartSource, AdapterRegistration, AdapterRegistry, Any, datetime, NeverCalledAdapter, test_all_network_adapters_start_disabled() (+2 more)

### Community 10 - "config.py"
Cohesion: 0.15
Nodes (12): BaseSettings, field_validator, model_validator, CountryConfig, _load_yaml(), Any, BaseModel, Path (+4 more)

### Community 11 - "exports/manifest.py"
Cohesion: 0.24
Nodes (7): DataFrame, deterministic_manifest(), Any, manifest_bytes(), manifest_sha256(), ExportManifest, test_manifest_is_deterministic_and_complete()

### Community 12 - "track_summary.py"
Cohesion: 0.17
Nodes (18): MetricObservation, TrackPlatformCountrySummary, presence_summary(), PresenceSummary, UUID, Observations are (country, platform, platform_item_id); item multiplicity is…, Decimal, Session (+10 more)

### Community 13 - "overlap.py"
Cohesion: 0.42
Nodes (8): CorrelationResult, _effective_depth(), jaccard_overlap(), OverlapResult, rank_correlations(), RankedItem, test_correlations_are_null_when_shared_sample_is_insufficient(), test_overlap_uses_common_observed_depth_and_reports_items()

### Community 14 - "Milestone 1A acceptance report"
Cohesion: 0.29
Nodes (6): Activation state and review gate, Milestone 1A acceptance report, Outcome, Scientific invariants verified, Synthetic acceptance evidence, Verification record

### Community 15 - "test_most_popular_source.py"
Cohesion: 0.32
Nodes (10): _enabled_source(), PageTransport, Exception, parametrize, test_bad_request_retry_exhaustion_and_malformed_json_fail_explicitly(), test_ordinary_rate_limit_and_timeout_are_retried(), test_paginated_fetch_preserves_raw_pages_and_accounts_for_quota(), test_permanent_authorization_errors_are_not_retried() (+2 more)

### Community 16 - "0001_reference_entities.py"
Cohesion: 0.60
Nodes (3): Column, _reference_columns(), upgrade()

### Community 17 - "0003_track_identity.py"
Cohesion: 0.60
Nodes (3): _audit_columns(), Column, upgrade()

### Community 18 - "0005_charts.py"
Cohesion: 0.60
Nodes (3): _audit(), Column, upgrade()

### Community 19 - "0007_collection_coverage.py"
Cohesion: 0.60
Nodes (3): _audit(), Column, upgrade()

### Community 20 - "build_session_factory"
Cohesion: 0.40
Nodes (4): sessionmaker, build_session_factory(), Engine, Session

### Community 21 - "AppleMusicTokenProvider"
Cohesion: 0.40
Nodes (3): AppleMusicTokenProvider, Protocol, Secret-backed provider; concrete credential loading stays outside the adapter.

### Community 22 - "models/charts.py"
Cohesion: 0.12
Nodes (17): Connection, Mapper, ChartRepository, date, datetime, Decimal, Session, UUID (+9 more)

### Community 23 - "PlatformItem"
Cohesion: 0.23
Nodes (8): ExternalIdClaim, PlatformItem, PlatformItemTrackLink, Session, UUID, TrackRepository, test_conflicting_isrc_claims_are_retained(), test_multiple_videos_remain_distinct_for_one_recording()

### Community 24 - "ReferenceRepository"
Cohesion: 0.14
Nodes (12): Country, DataSource, Platform, Session, ReferenceRepository, Protocol, Session, RightsRepository (+4 more)

### Community 59 - "cli.py"
Cohesion: 0.12
Nodes (27): command, collect_current(), coverage_show(), export_create(), import_apply(), import_preview(), metrics_summarize(), procurement_profile_sample() (+19 more)

### Community 60 - "tracks/resolution.py"
Cohesion: 0.20
Nodes (14): ResolutionRecord, CanonicalTrack, ResolutionStatus, Session, UUID, ResolutionCandidate, ResolutionOutcome, TrackResolutionService (+6 more)

### Community 61 - "Milestone 1B acceptance report"
Cohesion: 0.29
Nodes (6): Adapter evidence, Gate after 1B, Milestone 1B acceptance report, Nine-country synthetic acceptance, Outcome, Verification record

### Community 64 - "ChartPayload"
Cohesion: 0.17
Nodes (15): ChartPayload, ChartIngestionService, IngestionResult, IngestionSink, date, datetime, Protocol, Coordinates authorization before delegating persistence to an injected sink. (+7 more)

### Community 65 - "HttpPolicy"
Cohesion: 0.15
Nodes (15): RuntimeError, AppleRequest, Any, datetime, UUID, execute_http(), HttpPolicy, Any (+7 more)

### Community 66 - "ChartEntryDTO"
Cohesion: 0.19
Nodes (14): map_chart_payload(), datetime, map_most_popular_page(), datetime, YouTubePage, ChartEntryDTO, build_youtube_video_chart_view(), YouTubeVideoChartView (+6 more)

### Community 67 - "Diligência de provedores — Milestone 1C"
Cohesion: 0.12
Nodes (15): 1. Luminate — CONNECT, Music API e Music Data Share, 2. Soundcharts API e Enterprise Data Dump/Data Feed, 3. Chartmetric REST API e Data Shares, Cobertura, metodologia e lacunas, Cobertura, metodologia e lacunas, Cobertura, método e identificadores, Comercial, limites e direitos, Decisão provisória (+7 more)

### Community 68 - "AppleMusicChartSource"
Cohesion: 0.26
Nodes (9): AppleMusicChartSource, HttpResponse, RetryingTransport, SpyTransport, test_apple_request_is_current_songs_chart(), test_common_chart_source_entrypoint_is_also_disabled_before_transport(), test_disabled_fetch_fails_before_transport(), test_enabled_fixture_fetch_uses_bounded_http_policy() (+1 more)

### Community 69 - "Milestone 1C historical-provider decision record"
Cohesion: 0.22
Nodes (8): Activation rule, Coverage decision, Current candidate disposition, Decision boundary, Exit-evidence register, Milestone 1C historical-provider decision record, Required approvals, Selection rationale

### Community 70 - "Milestone 1C procurement packet"
Cohesion: 0.25
Nodes (7): Human actions required before sending, Milestone 1C procurement packet, Outreach template, Provider-specific emphasis, Questions that must be answered in the contract, Requested response package, Sample handling procedure

### Community 71 - ".for_preview"
Cohesion: 0.60
Nodes (3): test_invalid_and_duplicate_ranks_are_reported(), test_preview_is_read_only_and_preserves_unknown_columns(), test_weekly_period_is_not_expanded_and_null_metric_is_preserved()

## Knowledge Gaps
- **138 isolated node(s):** `chart-observatory`, `ChartObservation`, `ExternalId`, `Global Constraints`, `Scope and execution gates` (+133 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RightsOperation` connect `RightsOperation` to `ChartPayload`, `HttpPolicy`, `AppleMusicChartSource`, `enums.py`, `YouTubeMostPopularSource`, `AdapterRegistry`, `test_most_popular_source.py`, `ReferenceRepository`, `cli.py`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `RightsGate` connect `RightsOperation` to `HttpPolicy`, `AppleMusicChartSource`, `YouTubeMostPopularSource`, `AdapterRegistry`, `test_most_popular_source.py`, `ReferenceRepository`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `LocalResearchApplication` connect `RightsOperation` to `cli.py`, `exports/manifest.py`, `api/app.py`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 39 inferred relationships involving `RightsOperation` (e.g. with `AppleMusicChartSource` and `AppleRequest`) actually correct?**
  _`RightsOperation` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `RightsGate` (e.g. with `AppleMusicChartSource` and `AppleRequest`) actually correct?**
  _`RightsGate` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `HttpPolicy` (e.g. with `AppleMusicChartSource` and `AppleRequest`) actually correct?**
  _`HttpPolicy` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `YouTubeMostPopularSource` (e.g. with `HttpPolicy` and `YouTubeRegion`) actually correct?**
  _`YouTubeMostPopularSource` has 14 INFERRED edges - model-reasoned connections that need verification._