# MGD × Kaggle overlap

Status: `NOT_COMPUTED`.

MGD was fully imported from the local `./mgd` directory. The Kaggle adapter for
`dhruvildave/spotify-charts` is implemented and fixture-tested, but the current
environment has no `kagglehub` installation and no local Kaggle `charts.csv`.
Therefore this report intentionally contains no fabricated overlap percentage.

Once the dataset is acquired, run:

```text
chart-observatory sources kaggle download
chart-observatory sources kaggle import
```

Then compare observations using origin platform, market, chart, date, rank and
resolved track identity. Preserve both source observations; use the explicit
equivalence key only for deduplication in a later canonical analysis table.
