# Research Browser and Content Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing Streamlit browser with a lazy Corpus v1 overview, searchable observation explorer, track detail, and locally persisted manual classification workbench.

**Architecture:** Keep Streamlit as the presentation layer and move all data selection, aggregation, taxonomy, and persistence into small `chart_observatory.ui` modules with public seams. Polars lazy scans the large MGD Parquet; a JSON repository stores manual classifications atomically; the UI reads the manifest and derived Parquets for completed-artifact status.

**Tech Stack:** Python 3.12, Streamlit, Polars, PyArrow/Parquet, JSON/`pathlib`, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-08-research-browser-classification-design.md`

## Global Constraints

- The dashboard reads `data/derived/corpus_v1_source_manifest.json` as the source of status.
- Corpus v1 is displayed as `FROZEN`/completed with the manifest's 21,257,472 observations, 126,213 tracks, 68 cells, 55 eligible cells, and manifest SHA-256.
- The completed freeze card must not claim that this checkout executed the full PostgreSQL load.
- MGD observations must be queried with Polars `scan_parquet`; display collections are bounded.
- “Sem anotação” is distinct from score `0`; null scores are not rendered or aggregated as zero.
- The nine taxonomy dimensions and exact labels come from one shared definition, not duplicated page literals.
- Manual classification is local JSON in `data/runtime/content_classifications.json`; no PostgreSQL migration is part of this change.
- YouTube remains a separate `NOT_YOUTUBE_MUSIC_TOP_SONGS` video corpus.
- Do not add automatic lyric interpretation, LLM inference, lyric display, or new statistical inference.
- Preserve all existing working-tree changes and do not create a git commit automatically.

---

### Task 1: Add the immutable content taxonomy

**Files:**
- Create: `src/chart_observatory/ui/taxonomy.py`
- Create: `tests/unit/ui/test_taxonomy.py`

**Interfaces:**
- Produces `TAXONOMY_VERSION: str`.
- Produces `ContentDimension` with `code: str`, `label: str`, and `levels: tuple[str, str, str, str]`.
- Produces `CONTENT_TAXONOMY: tuple[ContentDimension, ...]` in the exact order from the spec.
- Produces `taxonomy_codes() -> tuple[str, ...]` and `level_label(code: str, score: int | None) -> str`.
- `level_label` returns `Sem anotação` for `None` and raises `KeyError` for an unknown code.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from chart_observatory.ui.taxonomy import CONTENT_TAXONOMY, level_label, taxonomy_codes


def test_taxonomy_keeps_the_nine_dimensions_and_exact_labels() -> None:
    assert taxonomy_codes() == (
        "sexual_explicitness",
        "objectification",
        "transactional_sex",
        "materialism",
        "drugs",
        "crime",
        "violence",
        "romantic_affection",
        "heartbreak",
    )
    assert CONTENT_TAXONOMY[0].levels == ("ausente", "sugestivo", "explícito", "gráfico")
    assert CONTENT_TAXONOMY[2].levels == ("ausente", "—", "presente", "central")
    assert CONTENT_TAXONOMY[-1].levels == ("ausente", "secundário", "relevante", "central")


def test_taxonomy_distinguishes_unannotated_from_zero() -> None:
    assert level_label("violence", None) == "Sem anotação"
    assert level_label("violence", 0) == "ausente"
    with pytest.raises(ValueError):
        level_label("violence", 4)


def test_taxonomy_rejects_unknown_dimension() -> None:
    with pytest.raises(KeyError):
        level_label("unknown", 0)
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/unit/ui/test_taxonomy.py -v`

Expected: FAIL because `chart_observatory.ui.taxonomy` does not exist.

- [ ] **Step 3: Write the minimal implementation**

Create a frozen dataclass and one tuple containing the nine rows. Validate that `score` is `None` or an integer in `0..3`; map `None` to `Sem anotação`; use the tuple order for `taxonomy_codes()`.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `pytest tests/unit/ui/test_taxonomy.py -v`

Expected: PASS with all exact-label and null/zero assertions green.

---

### Task 2: Implement the local classification repository

**Files:**
- Create: `src/chart_observatory/ui/classifications.py`
- Create: `tests/unit/ui/test_classifications.py`

**Interfaces:**
- Produces `ContentClassification` with `canonical_track_id`, `taxonomy_version`, `scores`, `reviewer`, `notes`, `review_status`, and timezone-aware `updated_at`.
- Produces `ContentClassification.with_score(code: str, score: int | None) -> ContentClassification`.
- Produces `ClassificationRepository` protocol with `get(track_id: str) -> ContentClassification | None`, `list_all() -> list[ContentClassification]`, and `upsert(record: ContentClassification) -> ContentClassification`.
- Produces `JsonClassificationRepository(path: Path, taxonomy_version: str)` implementing that protocol.
- `ContentClassification.scores` contains every taxonomy code with a nullable integer score.
- `JsonClassificationRepository` raises `ValueError` for invalid JSON structure or invalid score values and never overwrites a corrupt file during a read.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import UTC, datetime

import pytest

from chart_observatory.ui.classifications import (
    ContentClassification,
    JsonClassificationRepository,
)
from chart_observatory.ui.taxonomy import TAXONOMY_VERSION, taxonomy_codes


def _record(track_id: str = "track-1") -> ContentClassification:
    return ContentClassification(
        canonical_track_id=track_id,
        taxonomy_version=TAXONOMY_VERSION,
        scores={code: (0 if code == "violence" else None) for code in taxonomy_codes()},
        reviewer="researcher",
        notes="fixture",
        review_status="REVIEWED",
        updated_at=datetime(2026, 9, 8, tzinfo=UTC),
    )


def test_json_repository_creates_reads_and_upserts_without_duplicates(tmp_path) -> None:
    repository = JsonClassificationRepository(tmp_path / "classifications.json", TAXONOMY_VERSION)
    repository.upsert(_record())
    repository.upsert(_record().with_score("violence", 3))

    loaded = repository.get("track-1")
    assert loaded is not None
    assert loaded.scores["violence"] == 3
    assert len(repository.list_all()) == 1


def test_json_repository_preserves_null_as_unannotated_and_rejects_out_of_range(tmp_path) -> None:
    repository = JsonClassificationRepository(tmp_path / "classifications.json", TAXONOMY_VERSION)
    record = _record()
    assert record.scores["crime"] is None
    with pytest.raises(ValueError):
        repository.upsert(record.with_score("crime", 4))


def test_json_repository_does_not_replace_corrupt_store(tmp_path) -> None:
    path = tmp_path / "classifications.json"
    path.write_text("{not-json", encoding="utf-8")
    repository = JsonClassificationRepository(path, TAXONOMY_VERSION)
    with pytest.raises(ValueError):
        repository.list_all()
    assert path.read_text(encoding="utf-8") == "{not-json"
```

The test fixture assumes `with_score(code, score)` returns a new immutable record; add this public convenience method to keep UI form updates free of in-place mutation.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/unit/ui/test_classifications.py -v`

Expected: FAIL because the record and repository interfaces do not exist.

- [ ] **Step 3: Write the minimal implementation**

Use a JSON object with `schema_version` and `classifications` list. Create the parent directory on the first write. Serialize UTC timestamps with ISO-8601, normalize loaded timestamps to UTC, validate the exact taxonomy key set and `None`/integer `0..3` values, and upsert by `(canonical_track_id, taxonomy_version)`. Write a sibling temporary file and call `os.replace` only after serialization succeeds.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `pytest tests/unit/ui/test_classifications.py -v`

Expected: PASS, including idempotent update and corrupt-file preservation.

---

### Task 3: Add manifest, observation, track-detail, and profile data services

**Files:**
- Create: `src/chart_observatory/ui/data.py`
- Create: `tests/unit/ui/test_research_browser_data.py`

**Interfaces:**
- Produces `ManifestSummary` and `load_manifest_summary(manifest_path: Path) -> ManifestSummary`.
- Produces `manifest_metric_labels(payload: Mapping[str, object]) -> dict[str, str]` for locale-formatted overview cards.
- Produces `ObservationFilters` with `country_code`, `date_start`, `date_end`, `max_rank`, `query`, `classification_state`, and `limit`.
- Produces `filter_mgd_observations(path: Path, filters: ObservationFilters, annotated_track_ids: set[str]) -> pl.DataFrame`.
- Produces `TrackDetail` and `load_track_detail(observations_path, survival_path, genre_claims_path, track_id) -> TrackDetail | None`.
- Produces `build_classification_profile(observations: pl.DataFrame, classifications: Sequence[ContentClassification]) -> pl.DataFrame`.
- Produces `YoutubeSummary` and `load_youtube_summary(path: Path) -> YoutubeSummary`.
- Produces `load_optional_parquet(path: Path) -> tuple[pl.DataFrame, str | None]`, returning an empty frame and explanatory status rather than raising for a missing optional artifact.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date

import polars as pl

from chart_observatory.ui.classifications import ContentClassification
from chart_observatory.ui.data import (
    ObservationFilters,
    build_classification_profile,
    filter_mgd_observations,
    load_manifest_summary,
    load_track_detail,
)
from chart_observatory.ui.taxonomy import TAXONOMY_VERSION, taxonomy_codes


def test_manifest_summary_reads_frozen_counts_and_hash(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"status":"FROZEN","manifest_sha256":"' + "a" * 64
        + '","date_start":"2017-01-01","date_end":"2022-03-13",'
        '"observations":{"rows":12},"total_cells":2,"eligible_cells":1,'
        '"analytical_datasets":[{"path":"track_master.parquet","rows":3}]}',
        encoding="utf-8",
    )
    summary = load_manifest_summary(manifest)
    assert summary.status == "FROZEN"
    assert summary.observations == 12
    assert summary.manifest_sha256 == "a" * 64


def test_observation_filter_is_lazy_in_shape_and_respects_rank_market_query(tmp_path) -> None:
    path = tmp_path / "observations.parquet"
    pl.DataFrame(
        {
            "country_code": ["BR", "US", "BR"],
            "period_start": [date(2020, 1, 1)] * 3,
            "period_end": [date(2020, 1, 1)] * 3,
            "rank": [1, 1, 4],
            "track_title": ["Love Song", "Love Song", "Other"],
            "artist": ["Artist", "Artist", "Artist"],
            "native_id": ["track-1", "track-1", "track-2"],
            "metric_value": [100, 90, 80],
        }
    ).write_parquet(path)
    result = filter_mgd_observations(
        path,
        ObservationFilters(country_code="BR", max_rank=3, query="love", limit=10),
        annotated_track_ids={"track-1"},
    )
    assert result.select("native_id").to_series().to_list() == ["track-1"]
    assert result.select("classification_state").item() == "ANNOTATED"


def test_track_detail_aggregates_markets_ranks_survival_and_genres(tmp_path) -> None:
    observations = tmp_path / "observations.parquet"
    pl.DataFrame(
        {
            "country_code": ["BR", "US", "BR"],
            "period_start": [date(2020, 1, 1), date(2020, 1, 8), date(2020, 1, 15)],
            "rank": [4, 2, 8],
            "track_title": ["Song"] * 3,
            "artist": ["Artist"] * 3,
            "native_id": ["track-1"] * 3,
            "metric_value": [100, 90, 80],
        }
    ).write_parquet(observations)
    survival = tmp_path / "survival.parquet"
    pl.DataFrame({"track_id": ["track-1"], "duration": [3], "event": [1]}).write_parquet(survival)
    genres = tmp_path / "genres.parquet"
    pl.DataFrame({"canonical_track_id": ["track-1"], "normalized_genre": ["pop"]}).write_parquet(genres)

    detail = load_track_detail(observations, survival, genres, "track-1")
    assert detail is not None
    assert detail.appearances == 3
    assert detail.peak_rank == 2
    assert detail.mean_rank == 14 / 3
    assert detail.markets == ("BR", "US")
    assert detail.duration == 3
    assert detail.genres == ("pop",)


def test_classification_profile_excludes_null_but_counts_zero(tmp_path) -> None:
    observations = pl.DataFrame({"country_code": ["BR", "BR"], "native_id": ["track-1", "track-2"]})
    scores = {code: None for code in taxonomy_codes()}
    scores["violence"] = 0
    first = ContentClassification.for_test("track-1", TAXONOMY_VERSION, scores)
    profile = build_classification_profile(observations, [first])
    violence = profile.filter((pl.col("country_code") == "BR") & (pl.col("category") == "violence"))
    assert violence["classified_track_count"][0] == 1
    assert violence["prevalence"][0] == 0.0
```

Test helpers such as `ContentClassification.for_test` may be a test-only factory in the test module; production interfaces must not depend on test helpers.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/unit/ui/test_research_browser_data.py -v`

Expected: FAIL because `chart_observatory.ui.data` and its public operations do not exist.

- [ ] **Step 3: Write the minimal implementation**

Implement manifest parsing from nested `observations.rows`, `total_cells`, `eligible_cells`, `date_start`, `date_end`, `manifest_sha256`, and optional freeze fields. Use `pl.scan_parquet(path)` for MGD filtering, apply predicates before `limit`, then collect only the bounded result. Add `classification_state` from the annotated ID set. For track detail, scan only rows matching `native_id`, aggregate distinct markets/counts/ranks, and join the two small derived Parquets by ID. For the profile, deduplicate `(country_code, native_id)` before joining scores; for each category, count non-null scores as the denominator and positive scores as the numerator, retaining score `0` in the denominator.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `pytest tests/unit/ui/test_research_browser_data.py -v`

Expected: PASS without reading the entire fixture through an eager `read_parquet` path in the filtering implementation.

---

### Task 4: Replace the skeletal home page with the completed Corpus v1 overview

**Files:**
- Modify: `src/chart_observatory/ui/app.py`
- Create: `tests/unit/ui/test_overview_data.py`

**Interfaces:**
- Consumes `load_manifest_summary`, optional Parquet loading, and the existing `load_capabilities`/`load_manifests` helpers.
- Produces a Streamlit page that renders Corpus v1 status and analytical artifact summaries without performing data transformations inline that belong in `ui.data`.

- [ ] **Step 1: Write the failing test**

```python
from chart_observatory.ui.data import manifest_metric_labels


def test_manifest_metric_labels_expose_completed_corpus_v1_numbers() -> None:
    labels = manifest_metric_labels(
        {
            "status": "FROZEN",
            "observations": {"rows": 21257472},
            "total_cells": 68,
            "eligible_cells": 55,
            "manifest_sha256": "b" * 64,
            "analytical_datasets": [
                {"path": "track_master.parquet", "rows": 126213},
            ],
        }
    )
    assert labels["observations"] == "21.257.472"
    assert labels["tracks"] == "126.213"
    assert labels["markets"] == "55/68 elegíveis"
    assert labels["freeze"] == "FROZEN"
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/unit/ui/test_overview_data.py -v`

Expected: FAIL because the summary label function does not exist.

- [ ] **Step 3: Write the minimal implementation**

Add `manifest_metric_labels(payload: Mapping[str, object]) -> dict[str, str]` to `ui.data` for locale-style display formatting. Rework `app.py` to show the header, metric cards, coverage/elegibility table/chart, turnover summary, genre claims/diversity summaries, YouTube count cards, and freeze/hash detail. Keep source inventory in a secondary tab or section. Use `st.warning`/`st.info` for missing optional artifacts and show the manifest path/status instead of converting load failures to zero.

- [ ] **Step 4: Run focused tests and import verification**

Run: `pytest tests/unit/ui/test_overview_data.py -v; .venv\Scripts\python.exe -c "import chart_observatory.ui.app"`

Expected: PASS and a successful module import without requiring PostgreSQL.

---

### Task 5: Build the observations explorer and track detail page

**Files:**
- Create: `src/chart_observatory/ui/pages/observations.py`
- Create: `tests/unit/ui/test_observations_page_helpers.py`

**Interfaces:**
- Consumes `ObservationFilters`, `filter_mgd_observations`, `load_track_detail`, `JsonClassificationRepository`, and manifest paths from the existing project layout.
- Produces a bounded, filterable Streamlit page titled `Observações` with market/date/rank/text/classification controls and a selected-track detail area.

- [ ] **Step 1: Write the failing test**

```python
from chart_observatory.ui.pages.observations import format_observation_rows


def test_observation_rows_show_human_classification_state() -> None:
    rows = format_observation_rows(
        [{"track_title": "Song", "artist": "Artist", "rank": 1, "classification_state": "UNANNOTATED"}]
    )
    assert rows[0]["Classificação"] == "Sem anotação"
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/unit/ui/test_observations_page_helpers.py -v`

Expected: FAIL because the page helper does not exist.

- [ ] **Step 3: Write the minimal implementation**

Create a small formatting helper and page flow: load repository safely, collect filter controls, call the lazy data service with a visible limit (default 200, configurable up to 1,000), format rows, and use `st.dataframe`/`st.selectbox` to select a canonical ID. Render selected-track detail metrics and compact tables for markets/genres/classification; display an explanatory empty state when the Parquet is missing or no rows match. Do not eagerly read all observations.

- [ ] **Step 4: Run focused tests and a Streamlit syntax/import check**

Run: `pytest tests/unit/ui/test_observations_page_helpers.py -v; .venv\Scripts\python.exe -m py_compile src/chart_observatory/ui/pages/observations.py`

Expected: PASS and no syntax error.

---

### Task 6: Build the manual classification workbench and aggregate profile

**Files:**
- Create: `src/chart_observatory/ui/pages/classification.py`
- Create: `tests/unit/ui/test_classification_profile_helpers.py`

**Interfaces:**
- Consumes `CONTENT_TAXONOMY`, `ContentClassification`, `JsonClassificationRepository`, `filter_mgd_observations`, and `build_classification_profile`.
- Produces a Streamlit page titled `Classificação` with track selector, nine `Sem anotação`/0–3 controls, reviewer/notes fields, explicit save, and market/dimension profile.
- Produces `classification_form_values(record: ContentClassification | None) -> dict[str, int | None]` and `profile_display_rows(frame: pl.DataFrame) -> list[dict[str, object]]` for testable formatting.

- [ ] **Step 1: Write the failing tests**

```python
import polars as pl

from chart_observatory.ui.pages.classification import (
    classification_form_values,
    profile_display_rows,
)


def test_empty_classification_form_uses_none_for_every_dimension() -> None:
    values = classification_form_values(None)
    assert len(values) == 9
    assert set(values.values()) == {None}


def test_profile_display_rows_preserve_zero_and_denominator() -> None:
    rows = profile_display_rows(
        pl.DataFrame(
            {
                "country_code": ["BR"],
                "category": ["violence"],
                "classified_track_count": [4],
                "prevalence": [0.0],
                "mean_score": [0.0],
            }
        )
    )
    assert rows == [{"Mercado": "BR", "Dimensão": "violence", "Tracks classificadas": 4, "Prevalência": "0,0%", "Média": "0,00/3"}]
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/unit/ui/test_classification_profile_helpers.py -v`

Expected: FAIL because the page helpers do not exist.

- [ ] **Step 3: Write the minimal implementation**

Build the track selector from a bounded title/artist catalog. For each taxonomy dimension render a `st.selectbox` whose first option is `Sem anotação` and whose other options are the exact level labels. Convert the selected label to `None` or `0..3`, create a new immutable record, and call repository `upsert` only when the save button is pressed. Catch a corrupt-store `ValueError` and show a warning without overwriting it. Render profile rows from `build_classification_profile` with visible classified-track denominators, plus the methodology notice about intensity/centrality and framing.

- [ ] **Step 4: Run focused tests and a syntax check**

Run: `pytest tests/unit/ui/test_classification_profile_helpers.py -v; .venv\Scripts\python.exe -m py_compile src/chart_observatory/ui/pages/classification.py`

Expected: PASS and no syntax error.

---

### Task 7: Complete regression verification and refresh Graphify output

**Files:**
- Modify only files required by formatter/linter fixes discovered during verification.
- Refresh: `graphify-out/` through the repository's Graphify command when available.

**Interfaces:**
- Consumes every completed UI/data seam from Tasks 1–6.
- Produces a verified Streamlit browser with the existing pages still importable.

- [ ] **Step 1: Run all automated tests**

Run: `pytest`

Expected: all existing and new tests pass; no PostgreSQL service is required for unit tests.

- [ ] **Step 2: Run static checks**

Run: `ruff check src tests; mypy src/chart_observatory`

Expected: both commands pass without introducing ignores for the new modules.

- [ ] **Step 3: Run a bounded Streamlit smoke check**

Run: `streamlit run src/chart_observatory/ui/app.py --server.headless true --server.port 8501`

Open the local page and verify the overview cards, Observações page, and Classificação page render; stop the process after the smoke check. Verify that missing/corrupt optional artifacts produce warnings/empty states rather than a traceback.

- [ ] **Step 4: Update the local graph if Graphify is available**

From the repository root, run `graphify update .` when the command is available or when `graphify-out/` instructions require it. Inspect `git status --short` afterward and leave Graphify output as a local working artifact; do not commit it.

- [ ] **Step 5: Review the final diff**

Run: `git diff --check; git status --short`

Expected: only the intended UI modules, tests, specification/plan files, and any required local Graphify refresh are present; no existing user changes are reverted and no commit is created.
