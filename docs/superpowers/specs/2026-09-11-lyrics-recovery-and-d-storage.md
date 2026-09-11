# Lyrics Recovery and D: Storage Specification

## Goal

Move the project to `D:\PromiscuidadeMusical` and make lyrics collection resumable,
auditable, memory-bounded, and strictly limited to songs for which an approved source
returned validated lyrics.

## Decisions

- The project destination is `D:\PromiscuidadeMusical`.
- The existing PostgreSQL data directory `D:\PromiscuidadeMusicalPostgres` is already
  on D: and must not be overwritten or copied as ordinary project files.
- A valid insertion requires `lyrics_status=FOUND`, one of `GENIUS`, `LETRAS`,
  `LRCLIB`, or `LYRICS_OVH`, and non-empty original lyrics text.
- `MISSING`, provider errors, Gemini errors, malformed JSON, unknown sources, and empty
  lyrics are never inserted into the main lyrics JSONL.
- Existing valid `FOUND` records remain usable; invalid or negative historical rows do
  not block retry.
- The complete catalog is eligible on every run; only valid existing `FOUND` songs are
  skipped.
- Project copying is verified before the original Desktop directory is considered for
  removal. This implementation does not delete the original automatically.

## Behavior

The backfill writes only successful records. It keeps a bounded number of in-flight
requests equal to the configured worker count, so an interrupted run can resume without
materializing a future for every catalog row. A corrupted or incomplete line is ignored
when resuming.

The audit command compares the catalog with the append-only output and writes one CSV
row per catalog song, including its classification, valid source, number of valid rows,
and number of invalid/negative rows. It also reports malformed lines and duplicate IDs.

## Acceptance criteria

1. A valid `FOUND` record is accepted only with an approved source and non-empty lyrics.
2. A `MISSING` record never makes a song completed for resume purposes.
3. Provider errors and malformed lines never make a song completed.
4. The backfill has at most `workers` futures in flight.
5. The audit command detects the currently observed malformed line and duplicates.
6. The project copy on D: contains the source, tests, configuration, research, and data
   files with matching relative paths and sizes.
