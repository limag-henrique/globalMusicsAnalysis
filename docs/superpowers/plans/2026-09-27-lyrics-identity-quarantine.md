# Lyrics Identity Quarantine Implementation Plan

> **For agentic workers:** Implemented natively in this task; no commits or branch changes.

**Goal:** Preserve immutable lyric records and paid snapshots while durably excluding specifically reviewed unsafe identities from future lyric classification and any explicit scientific-eligibility selection.

**Architecture:** A versioned JSON manifest stores only identifiers, hashes, metadata, review evidence, and status (never lyric text). A small module validates the manifest and exposes a predicate; shared online/batch candidate selection uses that predicate. Existing chart-only exports remain unchanged because they do not export lyric classifications.

**Tech Stack:** Python 3.12, JSON, pytest, SQLAlchemy selectors.

**Spec:** User-supplied 2026-09-27 audit addendum; evidence summary in `docs/operations/lyrics-identity-audit-2026-09-27.md`.

## Global Constraints

- Do not alter or delete `LyricDocument` rows or immutable classification snapshots.
- Do not cancel, resubmit, or otherwise interfere with active Vertex batches.
- Do not quarantine hash collisions solely because hashes match.
- Do not create commits, switch branches, or modify other branches.
- Do not expose or persist raw lyric text in the manifest.

## Review Focus

- Unknown or malformed manifest status/UUID/hash must fail closed and be tested.
- Only `suspected_mismatch`, `confirmed_mismatch`, `insufficient_text`, and `contaminated_text` are excluded; related versions and needs-review remain available.
- Active already-reserved batch items must remain importable and immutable.
- A missing manifest must not silently disable exclusions.
- Chart exports must not drop a canonical track merely because one lyric document is quarantined.

### Task 1: Durable manifest and shared eligibility predicate

**Files:**
- Create `config/lyrics_identity_quarantine.json`
- Create `src/chart_observatory/lyrics/identity_quarantine.py`
- Modify `src/chart_observatory/lyrics/classification_queue.py`
- Modify `src/chart_observatory/lyrics/classification_service.py`
- Test `tests/unit/lyrics/test_identity_quarantine.py`
- Test `tests/unit/lyrics/test_classification_queue.py`

- [ ] Write failing tests for excluded statuses, retained statuses, malformed manifest data, and candidate selection.
- [ ] Verify RED, implement the validator/predicate and apply it only to new candidate selection.
- [ ] Verify GREEN and relevant lyrics tests.
- [ ] Document that active batch reservations/imports and chart-only exports are untouched.

### Task 2: Source-level suspension pending independent validation

**Files:**
- Modify `config/lyrics_identity_quarantine.json`
- Modify `src/chart_observatory/lyrics/identity_quarantine.py`
- Modify online, batch, retry, legacy-import, and scientific-quality selection paths
- Test the source policy at every provider/scientific boundary

- [x] Advance the manifest schema and record the auditable `LETRAS` suspension policy.
- [x] Exclude all `LETRAS` documents from future online and batch provider queues.
- [x] Exclude `LETRAS` errors from future retry batches.
- [x] Reject future legacy imports from the suspended source.
- [x] Exclude existing `LETRAS` results from scientific quality metrics while counting them.
- [x] Leave already-reserved batches and result reconciliation untouched.
- [x] Verify the database contains 26,540 `LETRAS` documents and 26,536 already-reserved active batch items.
