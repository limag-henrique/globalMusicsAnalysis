# Provider capabilities

The dynamic machine-readable inventory is [market_capabilities.csv](market_capabilities.csv).
It is regenerated with:

```text
chart-observatory sources coverage
```

## Interpretation

- `provider` identifies who supplied or derived the observation.
- `origin_platform` identifies the platform whose ranking semantics are being represented.
- `available` means the capability was observed in the current inventory or API response; it does not imply historical completeness or redistribution rights.
- Empty date fields mean that only capability discovery was performed, not historical extraction.
- YouTube `mostPopular` is a video ranking surface, not YouTube Music Top Songs.

The Chartmetric smoke test used the authenticated countries endpoint for Spotify
and recorded non-successful probes for Apple Music, Deezer, QQ and Amazon as
unavailable records. Those records are retained to prevent an undocumented
assumption that all platforms have identical coverage.

Authenticated Chartmetric commands are fail-closed by default. Run `sources
chartmetric auth-test --allow-network` or `discover --allow-network` only after
the operator has approved a bounded request; collection additionally requires its
own `--allow-network` flag and an explicit chart window.

Geographic classification is intentionally not invented in the extraction
layer. ISO country/territory codes are preserved as returned by each source;
continent and sub-region enrichment belongs in a versioned reference dataset
before statistical sampling.
