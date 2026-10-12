# Research publication release

## Problem

External reviewers need a coherent, portable research dataset rather than operational
backups, repeated exports, private lyric payloads, credentials and dated diagnostics.

## Agreed scope

The project owner requested consolidation for Kaggle and GitHub and removal of
irrelevant files. Original research data/documents use CC BY 4.0; original code
uses MIT. Classification and lyric-to-recording verification are completed.
The circulating market is distinct from artist nationality. Preserve the frozen
analysis, source attribution, native chart family, coverage and missing values.

## Deliverables and user stories

1. A reviewer can inspect the article and international atlas.
2. A reviewer can recompute country/year denominators from recording membership.
3. A reviewer can inspect all 26 lyric scores without redistribution of lyric text.
4. A reviewer can compare equal-market and distinct-recording global trends.
5. A reviewer can reproduce economic, gender, homicide and digital associations.
6. A reviewer can reproduce the thirty historical search specifications.
7. A reviewer can identify source URLs, units, dates and upstream license scope.
8. A reviewer can verify every packaged byte against a SHA-256 manifest.
9. A reviewer can reproduce results without a private database or API credentials.
10. The owner receives an upload folder and ZIP for each publication platform.
11. The owner sees a cleanup ledger distinguishing deleted temporary material
    from unique research evidence retained outside the public release.

## Decisions

- Build standalone GitHub and Kaggle distributions from an explicit allowlist.
- Use Parquet for larger linked tables; provide accessible CSV views on Kaggle.
- Include author-created classifications, derived recording membership and
  aggregates; withhold original lyrics, bulk raw provider charts and DB backups.
- CC BY covers original contributions, not a claim to relicense upstream works.
- Sanitize provenance paths and retain source hashes and publicly usable endpoints.
- Do not alter application behavior, database state, branches, commits or remotes.
- Prepare publication; online uploads are outside this request's preparation scope.
- Delete only demonstrably disposable artifacts, never unique source/audit evidence.
- Detect changes in shared input files during copying rather than silently mixing
  snapshots produced by concurrent work.

## Verification boundary

The delivered folder/archive is the public interface. A standalone verifier checks
checksums, unique keys, score ranges, corpus counts, aggregate denominators, source
coverage, missingness and package contents. A standalone reproduction command
recalculates outputs from packaged tables. Tests use that file/command boundary;
no internal database queries are needed by external validators.

## Out of scope

Publication of copyrighted lyrics, credentials, operational cloud account details,
bulk historical provider responses, PostgreSQL clusters, Git history rewriting,
automatic commits/pushes, new paid model requests and invented validation metrics.

## Workflow note

Alignment and license choice are confirmed in the conversation. The specification
is local because no issue tracker or triage vocabulary is configured for this task.
