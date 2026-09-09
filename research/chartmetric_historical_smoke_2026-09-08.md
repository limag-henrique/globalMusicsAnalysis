# Chartmetric historical access smoke test

Executed with the configured, explicitly authorized Chartmetric credential on
2026-09-08.

## Results

- Authentication: `AUTHENTICATED`.
- Spotify BR `2022-04-01`: 200 rows, first page collected.
- Spotify BR `2024-04-01`: 200 rows, first page collected.
- Spotify BR `2026-08-01`: 200 rows, first page collected.
- Spotify markets `US, NG, JP, DE, MX, ZA, IN, AU` on `2024-04-01`: 8,000 rows,
  8/8 tasks completed, resumable raw JSON and Parquet artifacts written.
- Capability discovery: 311 capability rows; the account exposed Spotify and
  YouTube in the platform inventory run.

The provider dates endpoint returned HTTP 400 for the configured account even
for the documented `spotify_track` streaming type. The backfill therefore
supports explicit date windows and reports date-discovery failure rather than
inventing dates. A full historical backfill must use a provider-approved date
enumeration or an explicitly bounded calendar window.

