# Milestone 1A acceptance report

Date: 2026-09-04  
Scope: Tasks 1–16 only

## Outcome

Milestone 1A provides a source-agnostic, rights-gated foundation with PostgreSQL migrations, immutable chart and provenance records, recording identity and review-safe resolution, a schema-configurable authorized-file importer, a disabled fixture-tested Apple Music adapter, native-period metrics, five versioned exports, and CLI/FastAPI/Streamlit entry points.

No provider network request, account creation, purchase, credential use, Git commit, branch change, or Milestone 1B work occurred.

## Synthetic acceptance evidence

The fixture `tests/fixtures/manual/valid_daily.csv` contains three BR observations for one daily native period.

| Check | Result |
|---|---:|
| Valid imported observations | 3 |
| Available coverage cells | 1 |
| Unresolved observations | 3 / 3 |
| Immutable raw artifacts | 1 SHA-256-addressed artifact |
| `chart_observations` export rows | 3 |
| `coverage_matrix` export rows | 1 |
| `track_master` export rows | 0, expected until resolution |
| `track_platform_country_summary` export rows | 0, expected until resolution |
| `cross_platform_presence` export rows | 0, expected until resolution |

All five datasets were generated as Parquet with a manifest SHA-256. CSV and Parquet null round-trips are covered by automated tests.

## Scientific invariants verified

- Origin platform and source provider are separate entities.
- Missing provider metrics remain null.
- Daily and weekly periods remain native; mixed-frequency alignment requires an explicit policy.
- Streams and views never share an aggregate.
- Fuzzy title similarity only creates candidates; it never confirms identity.
- Conflicting ISRC claims remain visible and require review.
- Multiple platform videos may link to one recording without merging ranked items.
- Snapshots, entries, raw-artifact records, and audit events are append-only in PostgreSQL.
- Absent, pending, expired, denied, or ambiguous rights fail closed per operation.
- Spotify collection is denied before transport, and the registry remains operational after both Spotify registrations are removed.

## Verification record

- Non-live tests: 58 passed.
- Ruff: passed.
- Mypy strict: passed for 88 source files.
- Python compileall: passed.
- Alembic: repeated upgrade passed; full downgrade-to-base then upgrade-to-head passed on PostgreSQL 16 on 2026-09-03.
- Local CLI/API/export smoke: passed on 2026-09-04.
- PostgreSQL import smoke on resume: not repeated because Docker Desktop's Windows service was stopped and this session lacked permission to start it. The SQL importer itself passed its transactional integration test, including artifact and audit provenance.

Two upstream deprecation warnings from Starlette's legacy `TestClient` are filtered in pytest; application warnings and test failures are not suppressed.

## Activation state and review gate

Apple Music, Spotify, YouTube, YouTube Music, Amazon Music, Soundcharts, Chartmetric, and Luminate remain network-disabled. The Apple implementation was exercised only with local synthetic fixtures. Authorized-file import requires explicit per-run authorization and independent grants for import, raw storage, and normalized storage.

Implementation stops here for human review. Milestone 1B and YouTube network work require a new approval.
