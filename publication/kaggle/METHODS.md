# Research methods consolidated for external validation

## Frozen corpus and verification

Snapshot: 2026-10-11 23:39:03 UTC. Model: gemini-3.8-flash. Taxonomy:
lyrics-classification-v1. Prompt: lyrics-classification-prompt-v2.
Specialists completed verification of classifications and lyric-to-recording links.
The project lead confirmed that stage as completed; no invented reviewer counts
or agreement statistics are added.

Intensity: 0 absent; 1 incidental; 2 substantial; 3 central. A theme is positive
when intensity >=2. Presence, stance, consent and representation are separate.
The complete taxonomy and original classification instructions accompany the code.

Selection uses the latest result for the fixed model/taxonomy/prompt, matching the
authorized document hash, existing exclusion decisions, then the latest applicable
result at the recording or native-ID grain. There is no model-confidence cutoff.
The selected full corpus contains 154,964 research recording identities; native-ID
classification coverage before market restrictions contains 154,942 IDs.

## Geography, years and denominators

The recording is the music unit. A circulation market is where it appears in a
chart; it is not artist nationality. The union preserves provider and chart family.
MGD Top 200 and Kaggle Top 200/Viral 50 overlap; do not add provider counts as
independent events. Count each native recording ID once per market/year for annual
statistics and once per market for all-history statistics. GLOBAL, HK and PR are
excluded; Taiwan remains a separately named market.

There are 68 markets and 386 market/year cells, 2017–2021 and 2022 through March 13.
The partial 2022 year is descriptive and excluded from annual social correlations
and historical search models. The country comparison includes 153,501 classified
recording IDs out of 222,102 observed distinct IDs and at least 300 classified
recordings per displayed market. Missing classification is not a score of zero.

Theme prevalence = 100 * positive classified IDs / classified IDs. Coverage =
classified IDs / all observed IDs. These are music proportions, not population,
audience, streams or engagement shares. Themes can overlap.

## Global trends

The fixed global panel keeps the same 55 markets in all full years 2017–2021,
with >=300 classified IDs and >=50% classification coverage in every year.
Each market receives equal weight. Interquartile ranges describe observed
market variation, not confidence intervals. Other released panels retain their
own explicit market sets: >=70% classification coverage, source/chart-family,
matched-source market sets and full-window chart-coverage sensitivity.
The separate pooled series counts each recording once per year across markets.
These two weighting choices answer different questions.

## Social indicators

External values join by market and exact reference year. No interpolation,
last-value carry-forward or substitution for missing values occurs. SIGI stays
in the 2019 edition. Context from the complete year 2022 extends beyond the music
cutoff and stays outside models. Female and total homicide denominators differ;
female homicide is not identical to femicide.

The complete social matrix has 26 themes x 13 indicators x 5 full years = 1,690
specified cells. Spearman correlation is reported separately by year when at
least 10 markets and varying values exist; >=300 classified recordings are
required per musical market/year. There are 1,586 available descriptive cells.
No significance claim is assigned to this exploratory correlation matrix.

## Search and connectivity

Google Trends is local relative interest. Retain term, language and query batch;
do not average raw index levels across independently normalized country queries.
Annual means weight represented bucket days, splitting weeks across years.
Below-threshold samples are interval-censored [0,1); missing is distinct from zero.

The historical search specification uses porn/en from the lexicographically first
batch per country. It requires >=80% temporal coverage, >=300 classified songs,
>=4 eligible years per market, >=20 markets and an identified design matrix.
Country/year fixed effects, clustered country errors and t intervals are used.
Baseline requires >=50% music classification coverage; sensitivity >=70%; adjusted
adds log PPP income and internet use. BH correction covers all 30 estimated models.

OONI uses volunteer-network connectivity tests on three recorded adult domains.
Anomaly is not confirmed blocking; the denominator excludes failed tests where
defined. No tests returned is not evidence of unrestricted access. OONI, DNS,
estimated visits and search interest are not interchangeable population measures.

## Scope of interpretation

Results describe charted repertoires and ecological associations. Shared music,
platform selection, exposure and changing genre composition matter for interpretation.
No causal effect on individuals, intrinsic national trait, national pornography
consumption estimate or TikTok effect is asserted. Contemporary video inventories,
DNS captures and access-pending commercial/survey sources remain separate.
