# PromiscuidadeMusical: verified lyrical themes and social context

An external-validation release of the research linking charted music to intimacy,
gender and power, material status, violence, digital access and cultural circulation.
Brazil is the focal case; the comparative atlas covers 68 circulation markets.

## What is included

- Original 26-dimension classifications and categorical codes, with recording IDs
  and text hashes, but without lyric text.
- Derived recording/market/year/chart-family membership, sufficient to recompute
  the deduplicated country and annual denominators.
- Country/year music profiles, source sensitivity and coverage, global patterns,
  social-context observations, local Google Trends samples, and all search models.
- The manuscript, international atlas, scientific figures and source attribution.
- Portable analysis code, a notebook, schemas, a data dictionary, checksums and
  an external review template.

The database freeze is **11 October 2026, 23:39:03 UTC**. Classification and
lyric-to-recording verification are **completed**, as confirmed by the project
lead. This release does not invent reviewer counts or agreement statistics.

The selected full corpus has **154,964 research recording identities**. Country
comparisons use **153,501 native recording IDs** in **68 markets**. Recording IDs,
documents, recording/market pairs and annual appearances are different units.
See METHODS.md and DATA_DICTIONARY.md before combining tables.

## Reproduce and verify

Python 3.12 was used for the frozen analyses. Work from the release root:

```bash
python -m pip install -r requirements.txt
python code/verify_release.py .
python code/reproduce.py --release . --output reproduced
python code/plot_global_patterns.py
```

Verification is offline. Reproduction uses packaged tables; it does not require
the original repository, PostgreSQL, `.env`, Google credentials or new API calls.
It recalculates scores-to-prevalence aggregation, market/year coverage, the social
matrix, categorical distributions, all eight global source/weighting sensitivity
panels and the thirty historical search models, then compares published values.
The plotting command recreates the four additional global figures in
`reproduced-figures/`, without altering frozen input tables.

## Files

- `data/inputs/`: recording classifications, categorical codes, chart membership,
  external context, search observations and source coverage inputs.
- `data/results/`: frozen analytical outputs used in the manuscript and atlas.
- `article/`: manuscript and international atlas.
- `figures/`: scientific figures, when present in the source freeze.
- `code/`: portable offline reproduction and verification.
- `notebooks/external_validation.ipynb`: walkthrough for reviewers.
- `RELEASE_MANIFEST.json` and `SHA256SUMS.txt`: packaged-file integrity.

CSV files use UTF-8. Parquet preserves numeric/null types. Empty CSV fields are
missing values, not zeros. Large linked tables use Parquet; Kaggle also includes
accessible CSV views where practical.

## Main patterns to investigate

The balanced global panel contains the same 55 markets in all five full years
2017–2021, with at least 300 classified recordings and 50% classification coverage
per market/year. Equal-market means show broad growth in money references,
materialism, crime and weapons, while romantic affection remains near 40%.
These are repertoire changes, not estimates of individual behavior or audience size.
`global-patterns/change-summary` records all 26 dimensions and source sensitivities.

The social matrix crosses all 26 dimensions with 13 contextual indicators in each
full year: 1,690 specified cells, 1,586 descriptive correlations available. Keep
missing cells and sample sizes. The historical search model family has 30 models;
multiple-comparison correction is applied to the entire estimated family.

## External review

Use EXTERNAL_REVIEW.md to report an issue with a release checksum, table, column,
recording ID, market and year. Independent reviewers can reproduce numerical
results from the release, inspect source attribution, and obtain any copyrighted
lyrics separately through their own authorized sources for semantic validation.

## Licenses and upstream material

Original research data/documents: **CC BY 4.0**. Original code: **MIT**.
See LICENSE-DATA.md, LICENSE-CODE.txt and THIRD_PARTY_SOURCES.md. This does not
relicense the songs, lyrics, platform services or original upstream datasets.
Raw lyrics, bulk provider chart dumps, credentials, billing ledgers, DB clusters
and operational backups are intentionally outside this public release.

## Publishing

GitHub: upload this curated folder to a repository chosen by the owner. Do not
publish the operational repository wholesale: it includes private research inputs.
Each delivered GitHub file stays below GitHub's ordinary file-size limit.

Kaggle: edit the owner in `dataset-metadata.json`. The account identifier is a
template, not an upload destination. Using the official Kaggle CLI:

```bash
kaggle datasets create -p PATH_TO_KAGGLE_FOLDER --public --keep-tabular --dir-mode zip
```

This release was prepared locally; no account upload, commit or push is performed
by the consolidation process. Add the final Kaggle/GitHub URLs and persistent
identifier to CITATION.cff after publication.
