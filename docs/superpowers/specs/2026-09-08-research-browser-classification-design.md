# Research Browser and Content Classification Design

**Status:** Approved for implementation planning  
**Date:** 2026-09-08

## Goal

Extend the existing Streamlit research browser so the completed Corpus v1 can be explored visually at track and observation level, while providing a manual, reproducible classification workbench for the nine content dimensions described in `Dados iniciais.txt`.

The interface must make the project's completed artifacts visible without loading the full 21+ million-row observation table into the browser, and must keep “sem anotação” distinct from score `0`.

## Scope

In scope:

- Corpus v1 overview with completed-artifact metrics, date range, freeze status, and manifest SHA-256.
- Lazy/filterable exploration of MGD observations and canonical tracks.
- Track detail with appearances, markets, ranks, persistence, and genre claims.
- Manual classification of the nine supplied dimensions on a `None`/`0`/`1`/`2`/`3` scale.
- Local JSON persistence through a repository abstraction.
- Aggregated classification profile by market and dimension using only saved values.
- Clear methodology boundaries for missing lyrics, YouTube video rankings, and the freeze manifest.

Out of scope:

- Automatic lyric interpretation, LLM classification, or inference from track titles.
- Full lyric display or lyric ingestion without an authorized source.
- PostgreSQL schema changes for classifications in this iteration.
- Fusion of YouTube videos with Spotify/MGD canonical tracks.
- New statistical inference beyond the already-generated analytical datasets.

## Source of truth and status language

The dashboard reads the checked-in/available manifest at `data/derived/corpus_v1_source_manifest.json` as the source of status. It displays Corpus v1 as `FROZEN`/completed, including the manifest hash, 21,257,472 observed rows from the manifest, 126,213 tracks, 68 total cells, and 55 eligible cells. It must not silently replace those values with the alternate 21,255,472 figure from the request.

The interface may show the manifest's `operational_membership_status` in a methodology/detail area as a separate technical note. The completed freeze card refers to the source-artifact freeze recorded by the manifest; it does not claim that this checkout has executed a full PostgreSQL load.

YouTube is shown as a separate current video corpus: 111 regions, 3,037 observations, and 1,678 distinct videos, with the explicit semantic label `NOT_YOUTUBE_MUSIC_TOP_SONGS`.

## Architecture

Keep the existing Streamlit entry point and pages. Add small, public, testable modules rather than putting data transformations directly in Streamlit callbacks:

### `chart_observatory.ui.data`

Provide cached/lazy readers and public operations for:

- manifest summary;
- track master and survival lookup;
- filtered MGD observations;
- track detail aggregation;
- coverage, turnover, genre claims/diversity, and YouTube summary data;
- classification-aware track filtering.

MGD observations must be queried through a Polars `scan_parquet` pipeline. The UI collects only bounded result sets for display. Track IDs are joined using the observed `native_id`/`canonical_track_id` relationship. Stable artifacts can be cached by Streamlit; user-written classifications must never be hidden by a stale cache.

### `chart_observatory.ui.taxonomy`

Define an immutable taxonomy version and the exact nine dimensions and labels:

| Code | 0 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| `sexual_explicitness` | ausente | sugestivo | explícito | gráfico |
| `objectification` | ausente | leve | clara | dominante |
| `transactional_sex` | ausente | — | presente | central |
| `materialism` | ausente | menção | ostentação | central |
| `drugs` | ausente | menção | consumo positivo | glorificação |
| `crime` | ausente | menção | participação | glorificação |
| `violence` | ausente | menção | descrição | celebração |
| `romantic_affection` | ausente | secundária | relevante | central |
| `heartbreak` | ausente | secundário | relevante | central |

The UI must render these labels from the taxonomy definition, not duplicate them in page code.

### `chart_observatory.ui.classifications`

Define a repository interface and a JSON implementation at `data/runtime/content_classifications.json`. A record is keyed by `canonical_track_id` and `taxonomy_version` and contains:

- nine nullable integer scores;
- author/reviewer identifier;
- optional notes;
- `review_status`;
- `updated_at` in UTC;
- taxonomy version.

Writes are atomic (temporary file plus replacement), tolerate a missing file, validate all scores as `None` or integers from `0` through `3`, and upsert without creating duplicate records. This local repository is the first persistence implementation and leaves a stable seam for a future PostgreSQL adapter.

## User experience

### Overview (`ui/app.py`)

Show a concise header and metric cards for Corpus v1, then charts/tables for:

- coverage and eligibility by market;
- turnover/persistence overview;
- genre claims and diversity;
- YouTube current collection;
- freeze manifest status and hash.

Cards must use the manifest and analytical artifacts rather than hardcoded values. Missing optional artifacts should result in an explanatory empty state, not an import error.

### Observations (`ui/pages/observations.py`)

Provide filters for market, date range, maximum rank, title/artist search, and classification state (`Todas`, `Anotadas`, `Sem anotação`). Use a bounded result limit and visible row count. Rows include period, market, rank, track title, artist, native ID, metric value, and classification state.

Selecting a track opens a detail area with canonical ID, appearances, markets, peak/mean rank, survival duration/event, genre claims, and existing classification values. Detail queries remain lazy and scoped to the selected track.

### Classification (`ui/pages/classification.py`)

Offer a track selector constrained by the current searchable corpus. Render one control per taxonomy dimension with an explicit `Sem anotação` option and the four level labels. Saving is explicit, validates before writing, reports success/failure, and reloads the record from the repository. A notes field and reviewer field are included.

Below the workbench, show a classification profile by market/dimension. The profile must expose `classified_track_count`/denominator and exclude null values from numerators and denominators. A score of zero remains a valid observed classification.

Add a short methodology notice: the scale records observed content intensity/centrality in this first version; it does not independently establish framing such as neutral versus glorifying, and no missing lyric is treated as absence.

## Error handling and empty states

- Missing Parquet or manifest: show the expected path and a useful command/action, without crashing the page.
- Invalid/corrupt JSON classification store: show a visible warning and do not overwrite it automatically.
- No matching observations: show filters and a zero-result message.
- No classification for a selected track: show `Sem anotação` for every dimension.
- Optional analytical dataset missing or empty: show `Dados ainda não disponíveis` and preserve the rest of the page.
- Never display a failed load as zero completed records.

## Testing seams

Tests use small in-memory Polars frames and `tmp_path` JSON stores; they do not scan the production-sized Parquet unnecessarily.

Required behavior tests:

1. The taxonomy exposes the nine dimensions in the specified order and exact labels.
2. Manifest summary preserves the frozen status, counts, date range, and 64-character hash.
3. Observation filtering applies market/date/rank/text/classification criteria and bounded limits.
4. Track detail computes appearances, peak rank, mean rank, markets, and survival fields from a known fixture.
5. The JSON repository creates, reads, updates, and validates classification records idempotently.
6. Classification aggregation excludes null values while retaining score zero.
7. Empty/missing optional artifacts produce safe empty-state values.

Verification commands after implementation:

```text
pytest
ruff check src tests
mypy src/chart_observatory
streamlit run src/chart_observatory/ui/app.py
```

No git commit is part of this work. Existing user changes in the working tree must be preserved.

