"""Cross all 26 frozen lyric dimensions with downloaded social indicators, by year."""
from pathlib import Path
from datetime import UTC, datetime
import hashlib
import json
import polars as pl
from scipy.stats import spearmanr

HERE=Path(__file__).resolve().parent
DATA=HERE/'analysis-final'
OUT=HERE/'social-context'
INDICATORS=['gdp_pc_ppp_constant','gini','youth_unemployment','urban_population',
    'internet_users','fixed_broadband','gender_inequality_index','sigi_2019',
    'homicide_unodc_total','homicide_unodc_female','homicide_unodc_female_intimate_partner_family',
    'ooni_anomaly_pct_valid_tests','ooni_confirmed_pct_valid_tests']

def main():
    OUT.mkdir(exist_ok=True)
    panel=pl.read_parquet(DATA/'context/country-year-crossings.parquet')
    metrics=pl.read_csv(DATA/'all-dimensions.csv')['metric'].to_list()
    records=[]
    for year in range(2017,2022):
        for metric in metrics:
            for indicator in INDICATORS:
                sample=panel.filter((pl.col('year')==year)&(pl.col('classified_tracks')>=300)).select(
                    'market_code','coverage',metric+'_pct',indicator).drop_nulls()
                valid=sample.height>=10 and sample[indicator].n_unique()>1 and sample[metric+'_pct'].n_unique()>1
                rho=float(spearmanr(sample[metric+'_pct'],sample[indicator]).statistic) if valid else None
                records.append(dict(year=year,metric=metric,context=indicator,n=sample.height,rho=rho,
                    median_coverage=sample['coverage'].median(),status='descriptive' if valid else 'insufficient_data'))
    associations=pl.DataFrame(records)
    associations.write_csv(OUT/'all-theme-social-associations.csv')
    associations.write_parquet(OUT/'all-theme-social-associations.parquet')
    panel.filter(pl.col('year')==2021).write_csv(OUT/'market-context-2021.csv')
    panel.filter(pl.col('market_code')=='BR').sort('year').write_csv(OUT/'brazil-social-context.csv')
    labels=pl.read_parquet(DATA/'selected-classifications.parquet').sort('append_order',descending=True).unique('lyric_track_id',keep='first')
    co=[]
    for first,second in [('romantic_affection','explicitness'),('romantic_affection','casual_sex'),
        ('explicitness','objectification'),('explicitness','misogyny'),('materialism','crime'),('violence','crime')]:
        both=((labels[first]>=2)&(labels[second]>=2)).sum()
        first_n=(labels[first]>=2).sum()
        co.append(dict(first=first,second=second,n=labels.height,first_positive=first_n,both_positive=both,
            both_pct=100*both/labels.height,second_given_first_pct=100*both/first_n))
    pl.DataFrame(co).write_csv(OUT/'theme-cooccurrence.csv')
    source=DATA/'context/country-year-crossings.parquet'
    manifest={'created_utc':datetime.now(UTC).isoformat(),'database_snapshot_utc':json.loads((DATA/'manifest.json').read_text())['database_snapshot_utc'],
        'themes':26,'context_indicators':len(INDICATORS),'years':[2017,2018,2019,2020,2021],
        'specifications':associations.height,'observed_associations':associations['rho'].is_not_null().sum(),
        'method':'Separate-year pairwise Spearman, >=300 classified recordings and >=10 markets; descriptive, no significance claims, no imputation',
        'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'provider_calls':0,'database_writes':0}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
