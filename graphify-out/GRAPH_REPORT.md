# Graph Report - Promiscuidade Musical  (2026-09-04)

## Corpus Check
- 133 files · ~29,129 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 708 nodes · 1610 edges · 58 communities (36 shown, 22 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 303 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d34ab022`
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
- apple_music/charts.py
- errors.py
- config.py
- exports/manifest.py
- track_summary.py
- overlap.py
- Milestone 1A acceptance report
- 0001_reference_entities.py
- 0003_track_identity.py
- 0005_charts.py
- 0007_collection_coverage.py
- build_session_factory
- AppleMusicTokenProvider
- .for_preview
- presence_summary
- test_datasets.py
- build_engine
- data_dictionary.md
- limitations.md
- methodology.md
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

## God Nodes (most connected - your core abstractions)
1. `RightsOperation` - 49 edges
2. `RightsGate` - 45 edges
3. `Base` - 30 edges
4. `UuidPrimaryKeyMixin` - 29 edges
5. `CreatedAtMixin` - 29 edges
6. `LocalResearchApplication` - 28 edges
7. `ArtifactStore` - 24 edges
8. `PlatformItem` - 23 edges
9. `DomainValidationError` - 23 edges
10. `AppleMusicChartSource` - 21 edges

## Surprising Connections (you probably didn't know these)
- `HttpResponse` --uses--> `RightsOperation`  [INFERRED]
  tests/contract/apple_music/test_chart_source.py → src/chart_observatory/domain/enums.py
- `RetryingTransport` --uses--> `RightsOperation`  [INFERRED]
  tests/contract/apple_music/test_chart_source.py → src/chart_observatory/domain/enums.py
- `SpyTransport` --uses--> `RightsOperation`  [INFERRED]
  tests/contract/apple_music/test_chart_source.py → src/chart_observatory/domain/enums.py
- `TokenProvider` --uses--> `RightsOperation`  [INFERRED]
  tests/contract/apple_music/test_chart_source.py → src/chart_observatory/domain/enums.py
- `NeverCalledAdapter` --uses--> `RightsOperation`  [INFERRED]
  tests/unit/charts/test_registry.py → src/chart_observatory/domain/enums.py

## Import Cycles
- None detected.

## Communities (58 total, 22 thin omitted)

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
Cohesion: 0.06
Nodes (59): DeclarativeBase, Session, UUID, SqlArtifactCatalog, ChartRepository, date, datetime, Decimal (+51 more)

### Community 5 - "RightsOperation"
Cohesion: 0.06
Nodes (62): ImportPreview, ImportRequest, ImportResult, ImportSink, InMemoryImportSink, ManualChartImporter, ManualRow, Path (+54 more)

### Community 6 - "enums.py"
Cohesion: 0.08
Nodes (35): CollectionRunResult, CommonObservationWindow, CoverageRecord, CoverageService, UUID, ChartFrequency, CoverageStatus, ItemKind (+27 more)

### Community 7 - "api/app.py"
Cohesion: 0.08
Nodes (29): FastAPI, Request, create_app(), application(), apply(), ApplyRequest, preview(), PreviewRequest (+21 more)

### Community 8 - "apple_music/charts.py"
Cohesion: 0.07
Nodes (39): AppleMusicChartSource, AppleRequest, Any, datetime, UUID, map_chart_payload(), datetime, execute_http() (+31 more)

### Community 9 - "errors.py"
Cohesion: 0.10
Nodes (24): command, Exception, NoReturn, DisabledChartSource, AdapterRegistration, AdapterRegistry, Any, datetime (+16 more)

### Community 10 - "config.py"
Cohesion: 0.15
Nodes (12): BaseSettings, field_validator, model_validator, CountryConfig, _load_yaml(), Any, BaseModel, Path (+4 more)

### Community 11 - "exports/manifest.py"
Cohesion: 0.42
Nodes (6): deterministic_manifest(), Any, manifest_bytes(), manifest_sha256(), ExportManifest, test_manifest_is_deterministic_and_complete()

### Community 12 - "track_summary.py"
Cohesion: 0.47
Nodes (7): MetricObservation, TrackPlatformCountrySummary, Decimal, _sum_type(), summarize(), test_native_period_rank_and_unit_specific_metrics(), test_weekly_period_counts_once()

### Community 13 - "overlap.py"
Cohesion: 0.42
Nodes (8): CorrelationResult, _effective_depth(), jaccard_overlap(), OverlapResult, rank_correlations(), RankedItem, test_correlations_are_null_when_shared_sample_is_insufficient(), test_overlap_uses_common_observed_depth_and_reports_items()

### Community 14 - "Milestone 1A acceptance report"
Cohesion: 0.29
Nodes (6): Activation state and review gate, Milestone 1A acceptance report, Outcome, Scientific invariants verified, Synthetic acceptance evidence, Verification record

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

### Community 22 - ".for_preview"
Cohesion: 0.60
Nodes (3): test_invalid_and_duplicate_ranks_are_reported(), test_preview_is_read_only_and_preserves_unknown_columns(), test_weekly_period_is_not_expanded_and_null_metric_is_preserved()

### Community 23 - "presence_summary"
Cohesion: 0.60
Nodes (4): presence_summary(), PresenceSummary, UUID, Observations are (country, platform, platform_item_id); item multiplicity is…

## Knowledge Gaps
- **109 isolated node(s):** `chart-observatory`, `ChartObservation`, `ExternalId`, `Global Constraints`, `Scope and execution gates` (+104 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RightsOperation` connect `RightsOperation` to `apple_music/charts.py`, `errors.py`, `enums.py`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Why does `RightsGate` connect `RightsOperation` to `apple_music/charts.py`, `errors.py`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Why does `LocalResearchApplication` connect `RightsOperation` to `errors.py`, `api/app.py`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `RightsOperation` (e.g. with `AppleMusicChartSource` and `AppleRequest`) actually correct?**
  _`RightsOperation` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `RightsGate` (e.g. with `AppleMusicChartSource` and `AppleRequest`) actually correct?**
  _`RightsGate` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `Base` (e.g. with `AnalysisRun` and `AuditEvent`) actually correct?**
  _`Base` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `UuidPrimaryKeyMixin` (e.g. with `AnalysisRun` and `AuditEvent`) actually correct?**
  _`UuidPrimaryKeyMixin` has 19 INFERRED edges - model-reasoned connections that need verification._