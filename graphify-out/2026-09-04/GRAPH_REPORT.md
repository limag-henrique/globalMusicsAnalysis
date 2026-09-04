# Graph Report - Promiscuidade Musical  (2026-09-04)

## Corpus Check
- 166 files · ~32,710 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 828 nodes · 2016 edges · 64 communities (41 shown, 23 thin omitted)
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 407 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `030a0bcf`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Milestone 1A
- Multiplatform Historical Chart Foundation — Design Specification
- Spotify official capabilities and constraints for cross-cultural chart research
- Avaliação de fontes históricas para rankings musicais multinacionais
- Base
- RightsGate
- errors.py
- LocalResearchApplication
- HttpPolicy
- AdapterRegistry
- config.py
- writer.py
- track_summary.py
- overlap.py
- Milestone 1A acceptance report
- RightsOperation
- 0001_reference_entities.py
- 0003_track_identity.py
- 0005_charts.py
- 0007_collection_coverage.py
- build_session_factory
- AppleMusicTokenProvider
- models/charts.py
- TrackRepository
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
- collection_runs.py
- tracks/resolution.py
- Milestone 1B acceptance report
- YouTubeApiKeyProvider
- youtube_data/__init__.py

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
- `NeverTransport` --uses--> `HttpPolicy`  [INFERRED]
  tests/contract/youtube_data/test_most_popular_source.py → src/chart_observatory/adapters/http.py
- `PageTransport` --uses--> `HttpPolicy`  [INFERRED]
  tests/contract/youtube_data/test_most_popular_source.py → src/chart_observatory/adapters/http.py
- `NeverTransport` --uses--> `YouTubeApiError`  [INFERRED]
  tests/contract/youtube_data/test_most_popular_source.py → src/chart_observatory/adapters/youtube_data/most_popular.py
- `PageTransport` --uses--> `YouTubeApiError`  [INFERRED]
  tests/contract/youtube_data/test_most_popular_source.py → src/chart_observatory/adapters/youtube_data/most_popular.py
- `NeverTransport` --uses--> `YouTubeQuotaExceeded`  [INFERRED]
  tests/contract/youtube_data/test_most_popular_source.py → src/chart_observatory/adapters/youtube_data/most_popular.py

## Import Cycles
- None detected.

## Communities (64 total, 23 thin omitted)

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
Cohesion: 0.31
Nodes (11): DeclarativeBase, Base, CreatedAtMixin, UuidPrimaryKeyMixin, AnalysisRun, AuditEvent, SourceArtifact, RightsGrantRow (+3 more)

### Community 5 - "RightsGate"
Cohesion: 0.09
Nodes (37): ImportPreview, ImportRequest, ImportResult, ImportSink, InMemoryImportSink, ManualChartImporter, ManualRow, Path (+29 more)

### Community 6 - "errors.py"
Cohesion: 0.07
Nodes (40): CommonObservationWindow, CoverageRecord, CoverageService, UUID, ChartFrequency, ItemKind, MetricType, PlatformCode (+32 more)

### Community 7 - "LocalResearchApplication"
Cohesion: 0.06
Nodes (35): FastAPI, Request, create_app(), application(), apply(), ApplyRequest, preview(), PreviewRequest (+27 more)

### Community 8 - "HttpPolicy"
Cohesion: 0.06
Nodes (55): RuntimeError, AppleMusicChartSource, AppleRequest, Any, datetime, UUID, map_chart_payload(), datetime (+47 more)

### Community 9 - "AdapterRegistry"
Cohesion: 0.08
Nodes (27): command, NoReturn, DisabledChartSource, ChartIngestionService, IngestionResult, date, datetime, Coordinates authorization before delegating persistence to an injected sink. (+19 more)

### Community 10 - "config.py"
Cohesion: 0.15
Nodes (12): BaseSettings, field_validator, model_validator, CountryConfig, _load_yaml(), Any, BaseModel, Path (+4 more)

### Community 11 - "writer.py"
Cohesion: 0.13
Nodes (14): deterministic_manifest(), Any, manifest_bytes(), manifest_sha256(), ExportManifest, AtomicDatasetWriter, AuthorizedDatasetWriter, DataFrame (+6 more)

### Community 12 - "track_summary.py"
Cohesion: 0.11
Nodes (26): map_most_popular_page(), datetime, YouTubePage, MetricObservation, TrackPlatformCountrySummary, presence_summary(), PresenceSummary, UUID (+18 more)

### Community 13 - "overlap.py"
Cohesion: 0.42
Nodes (8): CorrelationResult, _effective_depth(), jaccard_overlap(), OverlapResult, rank_correlations(), RankedItem, test_correlations_are_null_when_shared_sample_is_insufficient(), test_overlap_uses_common_observed_depth_and_reports_items()

### Community 14 - "Milestone 1A acceptance report"
Cohesion: 0.29
Nodes (6): Activation state and review gate, Milestone 1A acceptance report, Outcome, Scientific invariants verified, Synthetic acceptance evidence, Verification record

### Community 15 - "RightsOperation"
Cohesion: 0.10
Nodes (36): RightsOperation, RightsProfileStatus, datetime, UUID, AuthorizationDecision, datetime, RightsGrant, RightsProfile (+28 more)

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
Cohesion: 0.13
Nodes (16): Connection, Mapper, ChartRepository, date, datetime, Decimal, Session, UUID (+8 more)

### Community 23 - "TrackRepository"
Cohesion: 0.17
Nodes (10): ExternalIdClaim, Session, UUID, TrackRepository, test_conflicting_isrc_claims_are_retained(), test_multiple_videos_remain_distinct_for_one_recording(), _session(), test_conflicting_isrc_needs_review() (+2 more)

### Community 24 - "ReferenceRepository"
Cohesion: 0.22
Nodes (8): Country, DataSource, Platform, Session, ReferenceRepository, test_initial_countries_are_seeded_without_europe_aggregate(), test_soundcharts_provider_is_distinct_from_spotify_platform(), test_network_sources_are_seeded_pending_without_grants()

### Community 59 - "collection_runs.py"
Cohesion: 0.24
Nodes (11): CollectionRunRepository, CollectionRunResult, date, datetime, Session, UUID, Append-only persistence for collection attempts and their coverage result., CollectionRun (+3 more)

### Community 60 - "tracks/resolution.py"
Cohesion: 0.28
Nodes (10): ResolutionRecord, CanonicalTrack, ResolutionStatus, Session, UUID, ResolutionCandidate, ResolutionOutcome, TrackResolutionService (+2 more)

### Community 61 - "Milestone 1B acceptance report"
Cohesion: 0.29
Nodes (6): Adapter evidence, Gate after 1B, Milestone 1B acceptance report, Nine-country synthetic acceptance, Outcome, Verification record

## Knowledge Gaps
- **114 isolated node(s):** `chart-observatory`, `ChartObservation`, `ExternalId`, `Global Constraints`, `Scope and execution gates` (+109 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RightsOperation` connect `RightsOperation` to `RightsGate`, `errors.py`, `LocalResearchApplication`, `HttpPolicy`, `AdapterRegistry`, `writer.py`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `RightsGate` connect `RightsGate` to `LocalResearchApplication`, `HttpPolicy`, `AdapterRegistry`, `writer.py`, `RightsOperation`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `LocalResearchApplication` connect `LocalResearchApplication` to `AdapterRegistry`, `writer.py`, `RightsGate`, `RightsOperation`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Are the 39 inferred relationships involving `RightsOperation` (e.g. with `AppleMusicChartSource` and `AppleRequest`) actually correct?**
  _`RightsOperation` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `RightsGate` (e.g. with `AppleMusicChartSource` and `AppleRequest`) actually correct?**
  _`RightsGate` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `HttpPolicy` (e.g. with `AppleMusicChartSource` and `AppleRequest`) actually correct?**
  _`HttpPolicy` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `YouTubeMostPopularSource` (e.g. with `HttpPolicy` and `YouTubeRegion`) actually correct?**
  _`YouTubeMostPopularSource` has 14 INFERRED edges - model-reasoned connections that need verification._