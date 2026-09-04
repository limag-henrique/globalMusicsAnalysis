# Graph Report - Promiscuidade Musical  (2026-09-03)

## Corpus Check
- 4 files · ~16,163 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 118 nodes · 114 edges · 11 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5ee94c5d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Milestone 1A
- Multiplatform Historical Chart Foundation — Design Specification
- Spotify official capabilities and constraints for cross-cultural chart research
- Avaliação de fontes históricas para rankings musicais multinacionais
- Multiplatform Historical Chart Foundation Implementation Plan
- Avaliação detalhada por fonte
- 4. Policy restrictions material to this research design
- 6. Provider strategies
- 13. Milestone sequence
- Shortlist e estratégia de aquisição
- 2. Spotify Web API: current resolution/enrichment capability

## God Nodes (most connected - your core abstractions)
1. `Milestone 1A` - 17 edges
2. `Multiplatform Historical Chart Foundation — Design Specification` - 16 edges
3. `Spotify official capabilities and constraints for cross-cultural chart research` - 12 edges
4. `Avaliação de fontes históricas para rankings musicais multinacionais` - 11 edges
5. `Multiplatform Historical Chart Foundation Implementation Plan` - 10 edges
6. `Avaliação detalhada por fonte` - 10 edges
7. `4. Policy restrictions material to this research design` - 8 edges
8. `6. Provider strategies` - 7 edges
9. `13. Milestone sequence` - 6 edges
10. `Shortlist e estratégia de aquisição` - 6 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Communities (11 total, 0 thin omitted)

### Community 0 - "Milestone 1A"
Cohesion: 0.12
Nodes (17): Milestone 1A, Task 10: Define adapter ports, registry, and conformance suite, Task 11: Build the schema-configurable manual importer, Task 12: Implement the disabled Apple Music chart adapter against fixtures, Task 13: Calculate native-period persistence and rank metrics, Task 14: Implement presence, Top-N overlap, and rank correlation, Task 15: Build versioned exports and analysis-run manifests, Task 16: Expose CLI, FastAPI, Streamlit, and complete the 1A acceptance pass (+9 more)

### Community 1 - "Multiplatform Historical Chart Foundation — Design Specification"
Cohesion: 0.12
Nodes (15): 10. Metrics, 11. Import, provenance, and idempotency, 12. UI and exports, 14. Acceptance criteria, 15. Deferred decisions and explicit gates, 1. Goal and boundary, 2. Research finding that controls implementation, 3. Domain vocabulary (+7 more)

### Community 2 - "Spotify official capabilities and constraints for cross-cultural chart research"
Cohesion: 0.12
Nodes (15): 1. Spotify Charts: what is officially documented, 3. Rate limits, quotas, and Development Mode constraints, 5. Capability matrix for the proposed platform, 6. Recommended architecture boundary, 7. Decisions requiring approval before implementation, 8. Minimum acceptance criteria for a legally viable data foundation, CSV/export status and access constraints, Documented facts (+7 more)

### Community 3 - "Avaliação de fontes históricas para rankings musicais multinacionais"
Cohesion: 0.13
Nodes (14): Agregadores/licenciadores, Amazon, Apple, Avaliação de fontes históricas para rankings musicais multinacionais, Como ler esta avaliação, Comparação normalizada, Critério de aprovação de uma fonte, Direitos, retenção e publicabilidade (+6 more)

### Community 4 - "Multiplatform Historical Chart Foundation Implementation Plan"
Cohesion: 0.17
Nodes (11): Evidence-driven provider and coverage baseline, Final acceptance criteria for Milestone 1, Global Constraints, Milestone 1B — requires a new approval after 1A, Milestone 1C — historical provider decision gate, Milestone 1D — later authorized sources, Multiplatform Historical Chart Foundation Implementation Plan, Planned file map (+3 more)

### Community 5 - "Avaliação detalhada por fonte"
Cohesion: 0.20
Nodes (10): 1. Apple Music API Charts e Apple Music Feed, 2. YouTube Data API — `videos.list?chart=mostPopular`, 3. YouTube Music Charts, 4. Spotify Charts e Web API, 5. Amazon Music Web API, 6. Soundcharts, 7. Chartmetric, 8. Luminate CONNECT, Music API e Data Share (+2 more)

### Community 6 - "4. Policy restrictions material to this research design"
Cohesion: 0.25
Nodes (8): 4. Policy restrictions material to this research design, Analysis and derived metrics — critical blocker, Lyrics and copyright, Metadata, artwork, audio, and attribution, ML/AI and deterministic classification, Research/publication and redistribution, Scraping, private endpoints, and login automation, Storage, databases, caching, and historical reproducibility

### Community 7 - "6. Provider strategies"
Cohesion: 0.29
Nodes (7): 6. Provider strategies, Amazon Music, Apple Music, Historical commercial providers, Spotify, YouTube Data API, YouTube Music

### Community 8 - "13. Milestone sequence"
Cohesion: 0.33
Nodes (6): 13. Milestone sequence, Milestone 0 — provider rights and coverage, Milestone 1A — domain and first ingestion path, Milestone 1B — YouTube video chart, Milestone 1C — licensed history, Milestone 1D — Spotify and other later sources

### Community 9 - "Shortlist e estratégia de aquisição"
Cohesion: 0.33
Nodes (6): 1. Luminate — primeiro contato, 2. Soundcharts — segundo contato, 3. Chartmetric — terceiro contato, 4. YouTube Researcher Program — trilha paralela, Não priorizar, Shortlist e estratégia de aquisição

### Community 10 - "2. Spotify Web API: current resolution/enrichment capability"
Cohesion: 0.40
Nodes (5): 2. Spotify Web API: current resolution/enrichment capability, Authentication, Endpoints useful for track identity, Fields/capabilities that must not be relied upon in Development Mode, Fields currently usable for a single track

## Knowledge Gaps
- **98 isolated node(s):** `Global Constraints`, `Scope and execution gates`, `Evidence-driven provider and coverage baseline`, `Planned file map`, `Task 1: Bootstrap the project and configuration` (+93 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Avaliação de fontes históricas para rankings musicais multinacionais` connect `Avaliação de fontes históricas para rankings musicais multinacionais` to `Shortlist e estratégia de aquisição`, `Avaliação detalhada por fonte`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `Multiplatform Historical Chart Foundation — Design Specification` connect `Multiplatform Historical Chart Foundation — Design Specification` to `13. Milestone sequence`, `6. Provider strategies`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `Spotify official capabilities and constraints for cross-cultural chart research` connect `Spotify official capabilities and constraints for cross-cultural chart research` to `2. Spotify Web API: current resolution/enrichment capability`, `4. Policy restrictions material to this research design`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **What connects `Global Constraints`, `Scope and execution gates`, `Evidence-driven provider and coverage baseline` to the rest of the system?**
  _98 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Milestone 1A` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._
- **Should `Multiplatform Historical Chart Foundation — Design Specification` be split into smaller, more focused modules?**
  _Cohesion score 0.125 - nodes in this community are weakly interconnected._
- **Should `Spotify official capabilities and constraints for cross-cultural chart research` be split into smaller, more focused modules?**
  _Cohesion score 0.125 - nodes in this community are weakly interconnected._