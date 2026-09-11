# Lyrics Recovery and D: Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make lyrics recovery auditable and resumable while moving the project to `D:\PromiscuidadeMusical`.

**Architecture:** Keep the append-only JSONL as the lyric insertion boundary, but define completion only from valid `FOUND` records. Add a streaming audit module that reads the output defensively and a bounded worker loop that never submits the entire catalog at once. The existing PostgreSQL cluster remains a separate D: directory.

**Tech Stack:** Python 3.12, Polars, pytest, JSONL, CSV, PowerShell file verification.

**Spec:** `docs/superpowers/specs/2026-09-11-lyrics-recovery-and-d-storage.md`

## Global Constraints

- Only `FOUND` records with an approved source and non-empty `original_lyrics` may be inserted.
- `MISSING`, errors, malformed JSON, unknown sources, and empty lyrics must not block retries.
- Never create automatic git commits or switch branches.
- Never overwrite `D:\PromiscuidadeMusicalPostgres`.

### Task 1: Lock the valid-record and resume contract with tests

**Files:**
- Create: `tests/unit/lyrics/test_backfill_recovery.py`
- Modify: `src/chart_observatory/lyrics/lyrics_backfill.py`

**Interfaces:**
- Produces `is_valid_lyrics_record(record: Mapping[str, Any]) -> bool`.
- Produces `_load_completed(output_path: Path) -> tuple[set[str], set[tuple[str, str]]]` containing only valid `FOUND` IDs/keys.

- [ ] **Step 1: Write the failing tests**

```python
def test_only_valid_found_records_are_completed(tmp_path):
    output = tmp_path / "lyrics.jsonl"
    output.write_text(
        "\\n".join([
            json.dumps({"song_id": "found", "title": "A", "artist": "B", "lyrics_status": "FOUND", "lyrics_source": "GENIUS", "original_lyrics": "line one\\nline two"}),
            json.dumps({"song_id": "missing", "title": "C", "artist": "D", "lyrics_status": "MISSING"}),
            json.dumps({"song_id": "error", "title": "E", "artist": "F", "lyrics_status": "PROVIDER_ERROR"}),
            "not-json",
        ]) + "\\n",
        encoding="utf-8",
    )
    ids, keys = _load_completed(output)
    assert ids == {"found"}
    assert keys == {_normalize_song_key("A", "B")}


def test_valid_record_rejects_missing_empty_and_unknown_source():
    valid = {"lyrics_status": "FOUND", "lyrics_source": "LETRAS", "original_lyrics": "lyrics"}
    assert is_valid_lyrics_record(valid)
    assert not is_valid_lyrics_record({**valid, "lyrics_source": "UNKNOWN"})
    assert not is_valid_lyrics_record({**valid, "lyrics_status": "MISSING"})
    assert not is_valid_lyrics_record({**valid, "original_lyrics": "   "})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `\.venv\Scripts\python.exe -m pytest tests/unit/lyrics/test_backfill_recovery.py -q`

Expected: FAIL because the validity predicate does not exist and `_load_completed` currently accepts negative rows.

- [ ] **Step 3: Implement the minimal contract**

Add an approved-source constant and make `_load_completed` call `is_valid_lyrics_record` before adding an ID or normalized key. Ignore malformed and non-dictionary JSON rows.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `\.venv\Scripts\python.exe -m pytest tests/unit/lyrics/test_backfill_recovery.py -q`

Expected: PASS.

### Task 2: Write only successful lyrics and bound concurrency

**Files:**
- Modify: `src/chart_observatory/lyrics/lyrics_backfill.py`
- Modify: `tests/unit/lyrics/test_backfill_recovery.py`

**Interfaces:**
- `run_full_automation` remains the CLI entry point.
- A new internal worker scheduler keeps no more than `workers` futures in flight.

- [ ] **Step 1: Write the failing test**

```python
def test_process_result_for_missing_song_is_not_insertable():
    assert is_valid_lyrics_record({"lyrics_status": "MISSING"}) is False
```

- [ ] **Step 2: Run the focused test**

Run: `\.venv\Scripts\python.exe -m pytest tests/unit/lyrics/test_backfill_recovery.py -q`

Expected: PASS after Task 1; this is the guard for the write boundary.

- [ ] **Step 3: Implement the write boundary and scheduler**

Change the per-track result to return `None` when no approved source yields non-empty lyrics. Do not serialize `MISSING` or exception records. Replace the all-at-once `future_to_track` dictionary with a bounded refill loop using `wait(..., return_when=FIRST_COMPLETED)`. Keep errors in counters/terminal summaries only so failed songs remain eligible on the next run.

- [ ] **Step 4: Run the full lyrics unit suite**

Run: `\.venv\Scripts\python.exe -m pytest tests/unit/lyrics -q`

Expected: PASS.

### Task 3: Add the lyrics audit command

**Files:**
- Create: `src/chart_observatory/lyrics/lyrics_audit.py`
- Create: `tests/unit/lyrics/test_lyrics_audit.py`

**Interfaces:**
- `analyze_lyrics_output(catalog_path: Path, output_path: Path, report_path: Path, include_all: bool = True) -> AuditSummary`.
- CLI: `python -m chart_observatory.lyrics.lyrics_audit --catalog ... --output ... --report ...`.

- [ ] **Step 1: Write the failing test**

```python
def test_audit_classifies_valid_pending_duplicate_and_malformed_rows(tmp_path):
    summary = analyze_lyrics_output(catalog, output, report)
    assert summary.valid_found == 1
    assert summary.pending == 1
    assert summary.malformed_lines == 1
    assert "FOUND_VALID" in report.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `\.venv\Scripts\python.exe -m pytest tests/unit/lyrics/test_lyrics_audit.py -q`

Expected: FAIL because the audit module does not exist.

- [ ] **Step 3: Implement the streaming audit**

Read JSONL line by line, classify only approved/non-empty `FOUND` rows as valid, count malformed and duplicate records, compare catalog IDs to valid IDs, and write a UTF-8 CSV report with `song_id`, title, artist, classification, valid source, valid row count, and invalid row count.

- [ ] **Step 4: Run the audit tests and command on current data**

Run: `\.venv\Scripts\python.exe -m pytest tests/unit/lyrics/test_lyrics_audit.py -q`

Run: `\.venv\Scripts\python.exe -m chart_observatory.lyrics.lyrics_audit --catalog data/derived/track_master.parquet --output data/derived/lyrics/gemini_annotations.jsonl --report data/derived/lyrics/lyrics_audit.csv --master-only`

Expected: PASS and a report that identifies the existing malformed line and duplicate IDs without changing the source JSONL.

### Task 4: Validate and copy the project to D:

**Files:**
- Create during migration: `D:\PromiscuidadeMusical\` (verified copy of the project)
- Preserve: `D:\PromiscuidadeMusicalPostgres\` (existing PostgreSQL cluster)

**Interfaces:**
- The D: copy has the same relative project files and matching sizes for all copied files.

- [ ] **Step 1: Run all tests from the source project**

Run: `\.venv\Scripts\python.exe -m pytest -q`

Expected: PASS.

- [ ] **Step 2: Create the D: destination without touching the PostgreSQL directory**

Copy the project tree to `D:\PromiscuidadeMusical`, excluding transient `.venv`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, and `graphify-out`; copy `.git` and `.env` so the working project remains complete. Do not use `D:\PromiscuidadeMusicalPostgres` as a destination or source for this copy.

- [ ] **Step 3: Verify the copy**

Compare relative file lists and byte sizes between the source and D: copy. Verify `data/derived/lyrics/gemini_annotations.jsonl`, the audit CSV, `pyproject.toml`, migrations, and tests exist on D:.

- [ ] **Step 4: Run the focused tests from D:**

Run: `D:\PromiscuidadeMusical\.venv\Scripts\python.exe -m pytest tests/unit/lyrics -q` if the copied environment is available; otherwise use the source `.venv` with `D:\PromiscuidadeMusical` as the working directory.

Expected: PASS and no changes to the PostgreSQL cluster.
