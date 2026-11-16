# Reproducible Research Validation Report — 2026-11-15

## 1. Executive Summary & Scientific Verdict

> [!NOTE]
> **Superseded by Reconciled Final Run (Section 8 below)**: After resolving a host MSIX AppContainer reset that cleared virtualized Python/PostgreSQL paths, PostgreSQL 16.15 (`127.0.0.1:55433/chart_observatory_recovery_20261007`) was restored cleanly from `tmp/postgres-gate-ce9e13c20d354b07b25a7878a84075ca/source.dump`, selections `v4`/`v5` and all milestone runs (`bdbac1a1`, `f59314e5`, `15da3853`, `a8085116`, `b85c4d84`) were replayed and parity-verified, `19` verified `LRCLIB` candidates unique to `15da3853` were reconciled (`0` hash conflicts), and `scripts/run_lyrics_recovery_pipeline.py` advanced `v4` to **`28,116 / 30,224` candidates (`87,275 / 90,600` position-linked texts, `96.33%`)** under run `0e4b956cfc254c96d5e0b3cc4a33343cbe80f58fc4ec2ea91f24c374d60e1b53` and `v5` (with Slovenia IPF provisional) to **`28,827 / 31,104` candidates (`87,986 / 91,480` positions, `96.18%`, `711 / 880` Slovenia IPF texts recovered)** under run `6bb3f8af88d48ab52d0c538449142f111ed4608bb2a8835eda9d5fb0c98aaa51`. Scientific approvals remain `0` (`G1: reprovado`, `G2–G5: pendente`).

This session repaired core lyric identity/discovery/challenge-handling defects, executed an isolated low-coverage recovery campaign in parallel coordination with active OpenAI Codex workers, verified PostgreSQL staging and SHA-256 text integrity end-to-end, re-verified all local classification contracts, and re-evaluated the research gates without lowering thresholds, shrinking the global denominator, or fabricating approvals.

- **Required >=80% end-to-end validation outcome**: **NOT REACHED (External & Scientific Blockers)** — `0` of `277,650` expected positions (`0.00%`) hold scientific G1 chart proof or G2 lyric approval (`research_ready: false`, `classification_ready: false`, `paid_calls: 0`).
- **Observed vs. Frozen Scope**: `90,600 / 277,650` expected positions (`32.63%`) are observed across `615 / 2,250` country/year cells (`76 / 250` countries); `187,050` positions (`67.37%`) remain missing across `174` unrecovered countries and depth-shortfall cells.
- **Technical Lyric Text Acquisition Advance**:
  - Recovered **`+417` unique song candidates** (`GENIUS: 406`, `LRCLIB: 11`) and **`+976` position-linked raw lyrics**, lifting observed-position text coverage from `85,476 / 90,600` (`94.34%`) to **`86,452 / 90,600` (`95.42%`)**.
  - Closed **`26` of the `32` deficient country/year cells**, lifting cells at >=80% raw text availability from `583 / 615` (`94.80%`) to **`609 / 615` (`99.02%`)**, cutting remaining cell deficit from `439` to **`198` positions** across **`6`** residual cells (`SA 2026`, `ZW 2018`, `ZA 2026`, `UG 2023`, `ZW 2025`, `UG 2025`).

## 2. Environment & Multi-Agent Coordination

Verified directly in [environment-and-coordination.json](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/environment-and-coordination.json):

- **Runtime & Executables**: Python `3.12.16` at `.venv\Scripts\python.exe`, `pytest`, write access inside `D:\Repositórios\PromiscuidadeMusical`, HTTP 200 connectivity to `https://lrclib.net/` and `https://genius.com/`.
- **PostgreSQL 16.15 Cluster**: Running on `127.0.0.1:55433` (PID `20004`, database `chart_observatory_recovery_20261007`, `transaction_read_only=on`, `pg_is_in_recovery=false`, `quota_lyric_staging_runs: 143`, `quota_lyric_staging_blobs: 34045`, `global_annual_import_runs: 6`).
- **Multi-Agent Lock & Storage Coordination**: Preserved active Codex worker locks and stores (`low-coverage-native-0002`, `low-coverage-native-0003` PID `8780`, `comparison-0003`/`0004` PID `24976`, `variant-review-0001`, `data/derived/lyrics/low-coverage-native-20261115`) and Codex's uncommitted `http-cache` glob edit in `quota_acquisition.py`. Executed all Antigravity work in isolated state/store/runtime paths (`low-coverage-native-agy-0001`, `low-coverage-native-agy-0002`, `data/derived/lyrics/low-coverage-native-agy-20261115`, `data/runtime/antigravity-collaboration-20261115`).

## 3. Immutable Scope, Denominators & Stage Funnel

Baseline frozen selection: [global-rescan-2018-2026-20261111-v4-final-0002](file:///d:/Repositórios/PromiscuidadeMusical/data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002/manifest.json) (`manifest_sha256: f04dd74cc28788fd7384ba2b78a3147765322d16ecf88c2cc7d144e2970bf2d4`), audited under policy `complete-rankings-lyrics80-v1` ([audit-v4/report.json](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/audit-v4/report.json), [progress-v4/progress.json](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/progress-v4/progress.json)).

| Stage / Metric | Count | Denominator | % of Denominator | Status / Basis |
| --- | ---: | ---: | ---: | --- |
| Expected chart positions | `277,650` | `277,650` | `100.00%` | `250` countries x `9` years (`2018–2026` through `2026-10-15`); `2,250` cells |
| Recovered / observed positions (`v4`) | `90,600` | `277,650` | `32.63%` | `74,140` definitive + `16,460` provisional across `615` occupied cells (`76` countries); `187,050` missing |
| Observed positions — complete calendar | `64,690` | `277,650` | `23.30%` | `212,960` missing full-year coverage (`425` `QUOTA_FILLED_COMPLETE_CALENDAR` cells) |
| Verified chart positions (`G1`) | `0` | `277,650` | `0.00%` | `G1: reprovado` (`72` unresolved-population cells; `468` depth shortfalls; `0` adjudicated) |
| Positions with available raw text | `86,452` | `90,600` (obs) / `277,650` (exp) | `95.42%` obs / `31.14%` exp | Up from `85,476` (`+976`); `609 / 615` occupied cells >= 80% (`99.02%`) |
| Positions with validated lyrics (`G2`) | `0` | `90,600` obs / `0` G1-approved | `0.00%` / `N/A` | `G2: pendente` (human audio/official transcription adjudication = `0`) |
| Unique song / recording candidates | `30,224` | `30,224` | `100.00%` | `27,707` with raw text (`91.67%`); `2,517` `NONE`; `24,729` unique verified SHA-256 text blobs |
| Classification-eligible records (`G3–G5`) | `0` | `30,224` / `90,600` | `0.00%` | `0` prepared table rows; `0` paid Vertex AI calls; `0` uploads |

> [!NOTE]
> Exploratory published overlay [global-rescan-2018-2026-20261115-v5-published-provisional-0003](file:///d:/Repositórios/PromiscuidadeMusical/docs/operations/published-annual-overlay-20261115.md) records `91,480 / 277,650` (`32.95%`) by adding `880` provisional Slovenia IPF entries (`2018–2025`, `metric_value=null`) flagged `PROVISIONAL_SOURCE_PERIOD_BINDING_REVIEW_REQUIRED`. Historical Zenodo `23645386` files (`1,944,951` rows examined; `1,900,751` national rows across `387` cells) were verified by SHA-256/MD5 in [zenodo_provenance.json](file:///d:/Repositórios/PromiscuidadeMusical/data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002/zenodo_provenance.json) and were already included in `v4` (`0` net increment).

## 4. Country / Year Breakdowns

### 4.1 Annual Universe Breakdown (`250` countries / year, `v4-final-0002`)

Matrix cell statuses across `2,250` cells: `QUOTA_FILLED_COMPLETE_CALENDAR: 425`, `PROVISIONAL_OBSERVED_PERIODS: 119`, `PARTIAL_YEAR: 71`, `NO_VERIFIED_ANNUAL_SOURCE: 1,563`, `POPULATION_QUOTA_UNRESOLVED: 72` (`AQ, BV, GS, HM, IO, SJ, TF, UM`).

| Year | Occupied Cells | Expected Positions | Observed Positions (%) | Provisional | Complete Calendar (%) | Missing Positions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2018 | 60 / 250 | 30,850 | 8,470 (27.46%) | 2,850 | 5,620 (18.22%) | 22,380 |
| 2019 | 65 / 250 | 30,850 | 9,500 (30.79%) | 3,550 | 5,950 (19.29%) | 21,350 |
| 2020 | 68 / 250 | 30,850 | 9,960 (32.29%) | 2,290 | 7,670 (24.86%) | 20,890 |
| 2021 | 68 / 250 | 30,850 | 10,000 (32.41%) | 1,370 | 8,630 (27.97%) | 20,850 |
| 2022 | 70 / 250 | 30,850 | 10,480 (33.97%) | 1,840 | 8,640 (28.01%) | 20,370 |
| 2023 | 71 / 250 | 30,850 | 10,650 (34.52%) | 330 | 10,320 (33.45%) | 20,200 |
| 2024 | 70 / 250 | 30,850 | 10,480 (33.97%) | 3,090 | 7,390 (23.95%) | 20,370 |
| 2025 | 72 / 250 | 30,850 | 10,780 (34.94%) | 310 | 10,470 (33.94%) | 20,070 |
| 2026 (`<=10-15`) | 71 / 250 | 30,850 | 10,280 (33.32%) | 830 | 0 (0.00%) | 20,570 |
| **Total** | **615 / 2,250** | **277,650** | **90,600 (32.63%)** | **16,460** | **64,690 (23.30%)** | **187,050** |

### 4.2 Low-Coverage Cell Recovery (`32` Formerly Deficient Cells -> `6` Residual)

| Country / Year | Baseline Texts | Final Texts (`agy-0002`) | Known Quota | 80% Target | Remaining Deficit | Outcome |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `BG 2025` | 81 | 115 | 120 | 96 | 0 | Closed (`>=80%`) |
| `BG 2026` | 88 | 108 | 120 | 96 | 0 | Closed (`>=80%`) |
| `EE 2023` | 81 | 88 | 110 | 88 | 0 | Closed (`>=80%`) |
| `EG 2023` | 136 | 168 | 180 | 144 | 0 | Closed (`>=80%`) |
| `EG 2024` | 128 | 159 | 180 | 144 | 0 | Closed (`>=80%`) |
| `EG 2025` | 128 | 167 | 180 | 144 | 0 | Closed (`>=80%`) |
| `EG 2026` | 119 | 159 | 180 | 144 | 0 | Closed (`>=80%`) |
| `HK 2023` | 86 | 96 | 120 | 96 | 0 | Closed (`>=80%`) |
| `JP 2022` | 143 | 164 | 180 | 144 | 0 | Closed (`>=80%`) |
| `JP 2023` | 135 | 172 | 180 | 144 | 0 | Closed (`>=80%`) |
| `JP 2024` | 140 | 175 | 180 | 144 | 0 | Closed (`>=80%`) |
| `KR 2023` | 118 | 147 | 150 | 120 | 0 | Closed (`>=80%`) |
| `KR 2024` | 110 | 143 | 150 | 120 | 0 | Closed (`>=80%`) |
| `KZ 2023` | 110 | 133 | 140 | 112 | 0 | Closed (`>=80%`) |
| `KZ 2024` | 100 | 126 | 140 | 112 | 0 | Closed (`>=80%`) |
| `KZ 2025` | 109 | 125 | 140 | 112 | 0 | Closed (`>=80%`) |
| `KZ 2026` | 108 | 118 | 140 | 112 | 0 | Closed (`>=80%`) |
| `RU 2020` | 133 | 160 | 200 | 160 | 0 | Closed (`>=80%`) |
| `SA 2025` | 109 | 115 | 140 | 112 | 0 | Closed (`>=80%`) |
| `SA 2026` | 104 | 111 | 140 | 112 | 1 | **Deficient (`-1`)** |
| `TH 2024` | 137 | 162 | 180 | 144 | 0 | Closed (`>=80%`) |
| `TH 2025` | 137 | 155 | 180 | 144 | 0 | Closed (`>=80%`) |
| `TH 2026` | 138 | 155 | 180 | 144 | 0 | Closed (`>=80%`) |
| `TW 2023` | 104 | 120 | 140 | 112 | 0 | Closed (`>=80%`) |
| `UA 2023` | 119 | 141 | 150 | 120 | 0 | Closed (`>=80%`) |
| `UA 2024` | 115 | 146 | 150 | 120 | 0 | Closed (`>=80%`) |
| `UG 2023` | 88 | 91 | 170 | 136 | 45 | **Deficient (`-45`)** |
| `UG 2025` | 67 | 69 | 170 | 136 | 67 | **Deficient (`-67`)** |
| `ZA 2025` | 139 | 144 | 180 | 144 | 0 | Closed (`>=80%`) |
| `ZA 2026` | 124 | 129 | 180 | 144 | 15 | **Deficient (`-15`)** |
| `ZW 2018` | 99 | 100 | 130 | 104 | 4 | **Deficient (`-4`)** |
| `ZW 2025` | 36 | 38 | 130 | 104 | 66 | **Deficient (`-66`)** |
| **32-Cell Total** | **3,551** | **4,368** | **4,990** | **3,992** | **198** | **26 closed / 6 deficient** |

For comparison, Codex's parallel unpatched run [low-coverage-native-0003/status.json](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/research-resume-20261115/low-coverage-native-0003/status.json) ended at `85,523` positions with text (`585 / 615` cells >= 80%, `30` deficient cells, `414` position deficit, `27` recovered candidates).

## 5. Provenance, Hash Verification, Conflicts & Quarantine

- **PostgreSQL Staging Mirror Verification**: Run `b85c4d84d1e36ffd744c6279b090120457011f8361329e762fc8f25bf14d4114` verified via [staging-mirror-verification-0002.json](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/staging-mirror-verification-0002.json): `candidate_count: 30224`, `text_candidates: 27707`, `verified_text_blobs: 24729`, `run_signature_matches: true`, `local_postgresql_candidates_equal: true`, `local_postgresql_bodies_equal: true`, `scientific_approvals: 0`, `paid_calls: 0`.
- **Staged Source Distribution (`30,224` candidates)**: `GENIUS: 15,987`, `LRCLIB: 11,521`, `LETRAS (quarantined): 162`, `AZLYRICS: 29`, `LYRICS_OVH: 7`, `GOOGLE_MANUAL: 1`, `NONE: 2,517`. Statuses: `inherited_exact_candidate_pending_review: 29,352`, `candidate_pending_validation: 800`, `not_found_or_unverified: 72`.
- **Integrity, Quality Flags & Quarantine** ([candidate-integrity-0002/report.json](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/candidate-integrity-0002/report.json)):
  - `26,909` valid Spotify embed native proofs (`25,459` display matches, `1,450` display disagreements with `1,189` carrying text, `3,214` without native proof, `101` native proof unusable).
  - `3,378` flagged candidates (`3,497` rows in [quality-review.jsonl](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/candidate-integrity-0002/quality-review.jsonl)): `requested_collaboration_credits_unverified: 1,929`, `retrieval_metadata_requires_reconciliation: 1,527`, `requested_title_or_artist_metadata_mismatch: 760`, `full_provider_performer_evidence_missing: 672`, `page_identity_scope_unverified: 617`, `source_identity_evidence_missing: 554`, `provider_performer_or_version_mismatch: 255`, `same_text_different_titles: 148`, `same_text_different_performers: 141`, `short_text: 51`, `very_short_text: 9`.
  - `219` shared-text collisions and `162` quarantined `LETRAS` records preserved unapproved.
  - Exhausted Phase-2 acquisition errors across residual tasks: `GENIUS:404` (`622`), `MUSIXMATCH:429` (`390`), `LETRAS:404` (`364`), `AZLYRICS:429` (`315`), `divergent_exact_lrclib_editions` (`103`), `MUSIXMATCH:405` (`74`), `AZLYRICS:404` (`43`), `GENIUS_SEARCH:422` (`40`), `GENIUS_SEARCH:lyrics_declared_incomplete` (`33`), `MUSIXMATCH:202` (`21`), `GENIUS_PAGE:identity_or_container_unverified` (`2`).

## 6. Executed Fixes, SHA-256 Integrity & Test Results

### 6.1 Modified Modules & Tests

- [quota_acquisition.py](file:///d:/Repositórios/PromiscuidadeMusical/src/chart_observatory/lyrics/quota_acquisition.py) (`sha256: 1af5ab0027c5fb662103e6966636f9d426cf7113676085cdcc8b1cd60b68caf9`): Unicode combining-mark & Semitic vocalization normalization in `identity()`, `bilingual_identity_variants()`, `identities_compatible()`, `_expand_feature_credits()`, strict version/translation rejection, `extract_genius_preloaded_credits()`, `fetch_candidate()` preloaded credit binding, and `PacedHTTP.get` handling for HTTP `202` and AZLyrics HTTP `200` access-request challenges (converting to `429` and removing poisoned challenge body from run cache).
- [quota_discovery.py](file:///d:/Repositórios/PromiscuidadeMusical/src/chart_observatory/lyrics/quota_discovery.py) (`sha256: a3becda3dc995ccd57eefc359a9549a4c1e12e304f57edc7109ea7dd702d325a`): Re-exports shared matching/credit helpers, updates `match_lrclib_credit_binding()`, `role_bound_lrclib_candidate()`, `discover_candidate()`, and `audit_saved_result()`, skips `Genius *` translation accounts, and expands `search/multi` to `per_page=15` when `per_page=5` is saturated by translation noise.
- [test_quota_acquisition.py](file:///d:/Repositórios/PromiscuidadeMusical/tests/unit/lyrics/test_quota_acquisition.py) (`sha256: 7116a12c625deba215ddbcc70bfa7a56a15b58f4924c7646ef94f2448ea828f4`) & [test_quota_discovery.py](file:///d:/Repositórios/PromiscuidadeMusical/tests/unit/lyrics/test_quota_discovery.py) (`sha256: fd08beabd6402b77e1205e0a539691a52f36ba97072d67e03`): Added `5` regression tests covering all fixed failure modes.

### 6.2 Post-Edit Verification Runs

| Check | Command Scope | Result | Timing / Evidence |
| --- | --- | --- | --- |
| Targeted lyrics unit & regression tests | 5 lyrics unit test files | `88 passed` (0 failed, 0 skipped) | `6.82s` |
| Full unit test suite | `.venv\Scripts\python.exe -m pytest tests/unit -q` | `1239 passed` (0 failed, 0 skipped, 2 deprecation warnings) | `85.49s` |
| Classification contract & service tests | 6 classification/contract test files | `90 passed` (0 failed, 0 skipped) | `4.68s`, [classification-tests.xml](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/classification-tests.xml) |
| Classification packaging audit | [audit_classification_preparation.py](file:///d:/Repositórios/PromiscuidadeMusical/scripts/audit_classification_preparation.py) | `local_preparation_verified_pending_scientific_inputs` | `manifest_sha256: e2bdd7d548979d83c9c6325397b603f232b11de38165b523edfeee0bcb5137dc` |
| Isolated PostgreSQL integration | [run_research_postgres_tests.py](file:///d:/Repositórios/PromiscuidadeMusical/scripts/run_research_postgres_tests.py) | `integration_passed: true`, exit `0` | Port `55441`, `production_database_writes: 0` |
| Research gate audit & integrity verify | `chart-observatory research audit` + `verify` | Exit `0`, `integrity: verified`, `G1: reprovado` | [audit-v4/report.json](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/audit-v4/report.json) |
| PostgreSQL staging mirror & integrity | `verify_lyric_staging_mirror.py` + `audit_lyric_candidate_integrity.py` | Exit `0`, exact hash/body/row parity | [staging-mirror-verification-0002.json](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/staging-mirror-verification-0002.json) |

## 7. Classification Eligibility & Remaining Scientific Requirements

Verified in [classification-preparation/report.json](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/classification-preparation/report.json), [topic-dictionary.csv](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/classification-preparation/contract/topic-dictionary.csv) (`26` topics, ordinal `0–3`, `.present` at `score >= 2`), and [preparatory-table-template.csv](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/classification-preparation/contract/preparatory-table-template.csv) (`59` columns, `0` data rows):

1. **Gate G1 (`100%`)**: Supply authorized primary chart records for `174` missing markets and `22,351` depth-shortfall periods, resolve `2,226` source conflicts and `6` tie pairs, resolve population denominator rules for `8` ISO territories (`72` cells), and submit signed G1 human evidence.
2. **Gate G2 (`>=80%`)**: Obtain/verify lyrics for residual gaps (`6` cells, `198` positions; plus `2,517` currently unrecovered candidate IDs) and complete independent human audio/official-transcription adjudication (`0 -> >=80%`).
3. **Rights & Legal Clearance**: Document legal clearance for ML/AI processing of any Spotify-derived metadata/selection inputs and licensed lyric corpora.
4. **Gate G4 & Formal Rubric Acceptance**: Record formal scientific acceptance (`validate_rubric(..., require_accepted=True)`) alongside declared institutional reference `MG.202652246900`, and complete independent human annotation benchmarks (`80` development + `240` validation tracks achieving Krippendorff's `alpha >= 0.80`, `macro_F1 >= 0.80`, and ordinal weighted `kappa >= 0.80`) before submitting any paid Vertex AI batch requests (`\$150` cap preserved).
5. **Machine-Readable Obstacle Register**: [obstacle-register-20261115.json](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/obstacle-register-20261115.json).

---

## 8. Post-Reconciliation Pipeline Execution, Cohort Separation & Final Deliverables

Executed reproducible entry point [run_lyrics_recovery_pipeline.py](file:///d:/Repositórios/PromiscuidadeMusical/scripts/run_lyrics_recovery_pipeline.py) (`inventory -> acquisition -> technical_verification -> review_queue -> persistence_reconciliation -> refreshed_inventory -> completion_report`) backed by [recovery_pipeline.py](file:///d:/Repositórios/PromiscuidadeMusical/src/chart_observatory/lyrics/recovery_pipeline.py) and [inventory_export.py](file:///d:/Repositórios/PromiscuidadeMusical/src/chart_observatory/lyrics/inventory_export.py).

### 8.1 Staging Lineage Reconciliation (`85,476` vs `85,523` vs `86,452` vs Current)

| Snapshot / Run ID | Timestamp | Candidates w/ Text | Position-Linked Texts | Provenance / Resolution |
| --- | --- | ---: | ---: | --- |
| `f59314e586e0` (`low-coverage-native-0002`) | `2026-11-15 21:31:07` | `27,290` | `85,476` | Original `inventario-completo.json` baseline (`checkpoint-0400`) |
| `15da38539e2a` (`low-coverage-native-0003`) | `2026-11-15 22:08:42` | `27,317` | `85,523` | Codex unpatched `final`; held `19` verified `LRCLIB` texts absent from `b85c4d84` |
| `b85c4d84d1e3` (`low-coverage-native-agy-0002`) | `2026-11-15 22:38:32` | `27,707` | `86,452` | Antigravity patched `final`; `0` hash conflicts against `15da3853` (`409` only in `b85c4d84`) |
| Reconciled Baseline (`15da3853` + `b85c4d84`) | `2026-11-16T00:17:04Z` | `27,726` | `86,484` | Adopted `19` verified `LRCLIB` fills from `15da3853` with `reconciled_from_run_id` provenance |
| **Final `v4` (`0e4b956cfc25`)** | `2026-11-16T02:35:24Z` | **`28,116`** | **`87,275`** | `+390` net beyond reconciled baseline (`store_exact: 10`, `http_cache_replay: 311`, `live_cont: 22`, `pg_v1_fallback: 81` incl. `23` + `11` LETRAS replacements) |
| **Final `v5` Provisional (`6bb3f8af88d4`)** | `2026-11-16T02:35:24Z` | **`28,827`** | **`87,986`** | Includes `711 / 880` (`80.80%`) Slovenia IPF provisional texts (`http_cache_replay: 267`, `live: 110 + 161`, `pg_v1_fallback: 173`) kept separate from `v4` |

### 8.2 Separate Measures: Imported-Song Cohort vs. Research Scopes (`v4` & `v5`)

| Cohort / Research Scope | Unique Candidates | Candidates w/ Text | Missing | Memberships | Position Texts | Clean Unverified | Flagged | Quarantined | Sci Approved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Imported Cohort (`canonical_tracks`)** | `159,080` | `159,080` | `0` | `N/A` | `159,111` docs | `N/A` | `N/A` | `26,540` `LETRAS` | `0` |
| **Frozen Research `v4`** | `30,224` | `28,116` (`93.03%`) | `2,108` | `90,600` | `87,275` (`96.33%`) | `25,943` | `2,045` | `128` | `0` |
| **Provisional Research `v5` (`+880` SI)** | `31,104` | `28,827` (`92.68%`) | `2,277` | `91,480` | `87,986` (`96.18%`) | `26,425` | `2,274` | `128` | `0` |

- **Country/Year Availability**: `v4` maintains `609 / 615` occupied cells `>=80%` (`6` residual deficient cells: `SA 2026: 111/140`, `ZW 2018: 100/130`, `ZA 2026: 129/180`, `UG 2023: 91/170`, `ZW 2025: 38/130`, `UG 2025: 69/170`). `v5` reaches `614 / 623` occupied cells `>=80%` (`5` of `8` new Slovenia IPF `2018–2025` cells already `>=80%`: `SI 2019: 89/110`, `SI 2020: 89/110`, `SI 2022: 92/110`, `SI 2024: 90/110`, `SI 2025: 95/110`; `SI 2018: 85/110`, `SI 2021: 85/110`, `SI 2023: 86/110`).
- **Source Chain & Technical Verification (`v4`)**: `acquired_unverified: 25,943`, `pending_adjudication: 760`, `identity_conflict: 1,152`, `suspected_partial: 133`, `quarantined_corrupt_source: 128` (down from `162`), `unavailable: 2,108`, `source_chain_matched: 25,879`.

### 8.3 Parity, Change Ledger, Review Queues & Updated Deliverables

- **Local / PostgreSQL Mirror Parity**: Verified via `verify_lyric_staging_mirror.py` for both `v4` (`0e4b956cfc25`, `25,050` unique verified SHA-256 blobs) and `v5` (`6bb3f8af88d4`, `25,368` blobs) with `run_signature_matches: true`, `local_postgresql_candidates_equal: true`, `local_postgresql_bodies_equal: true`, `scientific_approvals: 0`, `paid_calls: 0`. Also verified `research_database_health.current_inventory` (`current_database_certified: true`, `server_version: "16.15"`).
- **Dynamic Inventory Outputs**:
  - [inventario-completo.json](file:///d:/Repositórios/PromiscuidadeMusical/outputs/inventario-musicas-pais-ano-20261115/inventario-completo.json) (`sha256: 52c11904fe196b00fcf3106d19e4d10aa98a25ee89a0b1a3a7cc6a5372a37a1a`)
  - [inventario.html](file:///d:/Repositórios/PromiscuidadeMusical/outputs/inventario-musicas-pais-ano-20261115/inventario.html) (`sha256: c4fb23604d0a7886c9f182ed3a857ed3fec8ef1f55d538348c9b288d94508295`) — removed hardcoded `0` and `'Pendente'` literals so `prontas_vertex`, cell counts, and per-row eligibility statuses render dynamically from embedded JSON.
- **Pending Queue, Change Ledger & Human Review Interface**:
  - [pending-and-unavailable-queue.jsonl](file:///d:/Repositórios/PromiscuidadeMusical/outputs/inventario-musicas-pais-ano-20261115/pending-and-unavailable-queue.jsonl) (`4,652` rows: `4,281` `v4` + `371` `v5_slovenia_provisional`; `sha256: 1aad767f0b7b6b19ebdf9b56822d47cbf807d710dedf363832ac3de8f331352a`)
  - [change-ledger-v1-repairs.jsonl](file:///d:/Repositórios/PromiscuidadeMusical/outputs/inventario-musicas-pais-ano-20261115/change-ledger-v1-repairs.jsonl) (`1,154` rows: `34` `v1_quarantined_replacement`, `231` `v1_cohort_reuse`, `870` `missing_candidate_recovery`, `19` `cross_run_reconciliation_fill`; `sha256: e88e09c76df5776147640664164acfe7dfdceb48ccf6eef72b1d123f7d4355ea`)
  - [review-interface.html](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/pipeline-run-20261115/review/review-interface.html), `quality-review.jsonl` (`4,574` rows), `native-display-review.jsonl` (`1,450` disagreements across `26,909` valid Spotify proofs)
- **Frozen Copilot Handoff & Completion Report**:
  - [completion-report-20261115.json](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/completion-report-20261115.json)
  - [copilot-frozen-handoff-20261115.md](file:///d:/Repositórios/PromiscuidadeMusical/data/runtime/antigravity-collaboration-20261115/copilot-frozen-handoff-20261115.md)
