# Data dictionary

`TABLE_SCHEMAS.csv` describes every input column's stored type and row count.

- **recording_id**: normalized native Spotify recording identifier; not a listener.
- **research_recording_id**: opaque canonical research identity in the full corpus.
- **lyrics_sha256**: hash of the frozen original lyric version, whose text is withheld.
- **chart-membership**: unique provider/platform/chart-family/market/year/recording
  presence. Contains no bulk raw ranks, streams, artist biography or lyric text.
- **market_code / year**: circulation market and chart observation year.
- **classified_tracks / chart_tracks / coverage**: distinct scored/observed recording
  counts and their ratio at that table's grain.
- **[dimension]_positive / [dimension]_pct**: count and percentage with intensity >=2;
  missing annotations never receive score zero.
- **external-context**: exact-reference-year numeric observations, units, attribution,
  retrieval dates and privately retained original source hashes. `source_artifact_ref`
  is a hash reference; it does not point to a included original provider file.
- **search-observations**: query-local samples; keep language, comparison_group,
  sampling periods, censoring status and original source hash.
- **global-patterns**: annual fixed-market means/medians/quartiles, paired changes,
  source sensitivity and fixed-sample social correlations. Quartiles are not CIs.
- **models**: all baseline, adjusted and 70%-coverage search models, samples and
  exclusions, with coefficients, clustered intervals and full-family BH q values.
- **categorical codes**: consent, target gender, representation roles, antisocial
  stances. Mention and endorsement remain separate.

## Intensity dimensions

- `explicitness` (integer 0–3)
- `sexual_desire` (integer 0–3)
- `sexual_innuendo` (integer 0–3)
- `explicit_sexual_act` (integer 0–3)
- `explicit_sexual_anatomy` (integer 0–3)
- `romantic_affection` (integer 0–3)
- `heartbreak` (integer 0–3)
- `infidelity` (integer 0–3)
- `transactional_sex` (integer 0–3)
- `casual_sex` (integer 0–3)
- `jealousy_possession` (integer 0–3)
- `reciprocity` (integer 0–3)
- `objectification` (integer 0–3)
- `misogyny` (integer 0–3)
- `sexual_agency` (integer 0–3)
- `status_symbolization` (integer 0–3)
- `commodification` (integer 0–3)
- `money_reference` (integer 0–3)
- `materialism` (integer 0–3)
- `conspicuous_consumption` (integer 0–3)
- `wealth_as_status` (integer 0–3)
- `drugs_alcohol` (integer 0–3)
- `crime` (integer 0–3)
- `violence` (integer 0–3)
- `weapons` (integer 0–3)
- `territorial_identity` (integer 0–3)
