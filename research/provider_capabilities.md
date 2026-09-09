# Provider capabilities

The dynamic machine-readable inventory is [market_capabilities.csv](market_capabilities.csv).
It is regenerated with:

```text
chart-observatory sources coverage
```

## Interpretation

The project owner approved rights activation for every source listed in the project;
the activation record is [milestone_1d_activation_record.md](milestone_1d_activation_record.md).
Capability rows below still describe observed or explicitly failed technical probes,
not legal status. A missing capability remains missing.

- `provider` identifies who supplied or derived the observation.
- `origin_platform` identifies the platform whose ranking semantics are being represented.
- `available` means the capability was observed in the current inventory or API response; it does not imply historical completeness or redistribution rights.
- Empty date fields mean that only capability discovery was performed, not historical extraction.
- YouTube `mostPopular` is a video ranking surface, not YouTube Music Top Songs.
- The source-preserving unified catalog is [source_catalog.parquet](../data/normalized/source_catalog.parquet).
  It materializes only artifacts present locally; Chartmetric historical rows are
  absent until an authenticated, bounded backfill produces its observation artifact.

The Chartmetric smoke test used the authenticated countries endpoint for Spotify
and recorded non-successful probes for Apple Music, Deezer, QQ and Amazon as
unavailable records. Those records are retained to prevent an undocumented
assumption that all platforms have identical coverage.

Authenticated Chartmetric commands are fail-closed by default. Run `sources
chartmetric auth-test --allow-network`, `discover --allow-network`, or the
bounded `dates --allow-network` command only after the operator has approved a
request; collection additionally requires its own `--allow-network` flag and an
explicit chart window. The current API accepts the Spotify chart's `offset` but
rejects `limit`; the adapter therefore applies the requested page size locally
after one server page, preserving the page checkpoint without assuming an
undocumented server parameter.

Geographic classification is intentionally not invented in the extraction
layer. ISO country/territory codes are preserved as returned by each source;
continent and sub-region enrichment belongs in a versioned reference dataset
before statistical sampling.
