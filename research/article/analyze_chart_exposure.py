"""Cross verified lyrics with actual chart days, streams, genre tags and social data."""
from pathlib import Path
from datetime import date
import hashlib
import json
import sys
import polars as pl
from scipy.stats import spearmanr

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'chart-exposure'
DATA=HERE/'analysis-final'

def write(frame,name):
    frame.write_csv(OUT/(name+'.csv'));frame.write_parquet(OUT/(name+'.parquet'))

def rates(frame,groups,metrics):
    expr=[pl.len().alias('classified_tracks'),pl.col('chart_days').sum().alias('classified_chart_days'),
        pl.col('chart_streams').sum().alias('classified_chart_streams')]
    for m in metrics:
        expr += [(100*(pl.col(m)>=2).mean()).alias(m+'_recording_pct'),
            (100*(pl.col('chart_days')*(pl.col(m)>=2)).sum()/pl.col('chart_days').sum()).alias(m+'_chart_day_pct'),
            (100*(pl.col('chart_streams')*(pl.col(m)>=2)).sum()/pl.col('chart_streams').sum()).alias(m+'_stream_pct')]
    return frame.group_by(groups).agg(expr).sort(groups)

def main():
    OUT.mkdir(exist_ok=True)
    metrics=pl.read_csv(DATA/'all-dimensions.csv')['metric'].to_list()
    global_manifest=json.loads((HERE/'global-patterns/manifest.json').read_text())
    markets=global_manifest['panels']['mgd_top200']
    labels=pl.read_parquet(DATA/'native-id-annotations.parquet').select('chart_track_id',*metrics)
    source=ROOT/'data/normalized/mgd_observations.parquet'
    daily=pl.scan_parquet(source).filter(pl.col('country_code').is_in(markets)&pl.col('period_start').is_between(date(2017,1,1),date(2021,12,31))).select(
        pl.col('country_code').alias('market_code'),pl.col('native_id').alias('chart_track_id'),
        'period_start','rank','metric_value','metric_type').with_columns(pl.col('period_start').dt.year().alias('year'))
    assert daily.filter((pl.col('metric_value')<0)|(pl.col('metric_type')!='STREAMS')).select(pl.len()).collect().item()==0
    raw_count=daily.select(pl.len()).collect().item()
    daily=daily.unique()
    tracks=daily.group_by('market_code','year','chart_track_id').agg(pl.len().alias('raw_rows'),
        pl.col('period_start').n_unique().alias('chart_days'),pl.col('rank').min().alias('peak_rank'),
        pl.col('metric_value').sum().alias('chart_streams'),pl.col('metric_value').is_not_null().sum().alias('stream_days')).collect(engine='streaming')
    assert tracks.filter(pl.col('raw_rows')!=pl.col('chart_days')).height==0,'Duplicate recording/day within MGD'
    exact_duplicates_removed=raw_count-tracks['raw_rows'].sum()
    assert tracks.filter(pl.col('stream_days')!=pl.col('chart_days')).height==0,'Missing streams; preserve explicit missingness before weighting'
    tracks=tracks.sort('market_code','year','chart_track_id')
    matched=tracks.join(labels,on='chart_track_id',validate='m:1')
    totals=tracks.group_by('market_code','year').agg(pl.len().alias('chart_tracks'),pl.col('chart_days').sum().alias('total_chart_days'),pl.col('chart_streams').sum().alias('total_chart_streams'))
    weighted=rates(matched,['market_code','year'],metrics).join(totals,on=['market_code','year'],validate='1:1').with_columns(
        (pl.col('classified_tracks')/pl.col('chart_tracks')).alias('recording_coverage'),
        (pl.col('classified_chart_days')/pl.col('total_chart_days')).alias('chart_day_coverage'),
        (pl.col('classified_chart_streams')/pl.col('total_chart_streams')).alias('stream_coverage'))
    assert weighted.height==51*5
    write(weighted,'weighted-country-year')
    write(matched,'classified-track-market-year')
    global_rows=[]
    for year in range(2017,2022):
        panel=weighted.filter(pl.col('year')==year)
        for m in metrics:
            for weight in ['recording','chart_day','stream']:
                global_rows.append(dict(year=year,metric=m,weight=weight,markets=51,mean_pct=panel[m+'_'+weight+'_pct'].mean()))
    write(pl.DataFrame(global_rows),'global-weighted-trends')
    social=pl.read_parquet(DATA/'context/country-year-crossings.parquet')
    indicators=['gdp_pc_ppp_constant','gini','youth_unemployment','urban_population','internet_users',
        'gender_inequality_index','homicide_unodc_total']
    joined=weighted.join(social.select('market_code','year',*indicators),on=['market_code','year'],validate='1:1')
    rows=[]
    for m in metrics:
        for indicator in indicators:
            available=joined.filter(pl.col(indicator).is_not_null())
            fixed=available.group_by('market_code').agg(pl.col('year').n_unique().alias('years')).filter(pl.col('years')==5)['market_code'].to_list()
            for year in range(2017,2022):
                sample=available.filter(pl.col('market_code').is_in(fixed)&(pl.col('year')==year))
                for weight in ['recording','chart_day','stream']:
                    rho=float(spearmanr(sample[m+'_'+weight+'_pct'],sample[indicator]).statistic) if sample.height>=10 else None
                    rows.append(dict(metric=m,context=indicator,year=year,weight=weight,markets=sample.height,rho=rho))
    write(pl.DataFrame(rows),'weighted-social-correlations')
    genres_path=ROOT/'data/derived/genre_claims.parquet'
    genres=pl.read_parquet(genres_path).select(pl.col('canonical_track_id').alias('chart_track_id'),'normalized_genre').unique()
    # Genre selection depends on charted repertoire size, not thematic scores.
    br_all=tracks.filter(pl.col('market_code')=='BR').select('chart_track_id').unique()
    br_genres=br_all.join(genres,on='chart_track_id',validate='1:m')
    genre_counts=br_genres.group_by('normalized_genre').agg(pl.len().alias('chart_tracks')).sort('chart_tracks',descending=True)
    selected=genre_counts.head(8)['normalized_genre'].to_list()
    br_labels=matched.filter(pl.col('market_code')=='BR').select('chart_track_id',*metrics).unique('chart_track_id')
    gen=br_labels.join(genres.filter(pl.col('normalized_genre').is_in(selected)),on='chart_track_id',validate='1:m')
    gs=gen.group_by('normalized_genre').agg(pl.len().alias('classified_tracks'),
        *[(100*(pl.col(m)>=2).mean()).alias(m+'_pct') for m in metrics]).join(genre_counts,on='normalized_genre',validate='1:1').with_columns(
        (pl.col('classified_tracks')/pl.col('chart_tracks')).alias('classification_coverage')).sort('chart_tracks',descending=True)
    write(gs,'brazil-genre-thematic-profiles')
    findings={'markets':markets,'period':'2017-01-01 to 2021-12-31','source':'MGD Spotify Top 200 only',
        'recording_weight':'one recording ID per market/year','chart_day_weight':'number of observed daily chart entries',
        'stream_weight':'sum of chart-eligible streams during observed chart days; not all-platform streams or unique listeners',
        'social_method':'same complete-data markets within each indicator for every year, Spearman separately by year and weighting',
        'genres':'top eight artist-derived labels by distinct Brazilian chart recording count; overlapping, not exclusive genre groups',
        'provider_calls':0,'database_writes':0,'exact_duplicate_chart_rows_removed':exact_duplicates_removed,
        'duplicate_rule':'Identical market/date/recording/rank/streams rows counted once; conflicting recording/day values rejected',
        'database_snapshot_utc':global_manifest['database_snapshot_utc'],
        'inputs':[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [source,genres_path,DATA/'native-id-annotations.parquet',DATA/'context/country-year-crossings.parquet',Path(__file__)]],
        'outputs':[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(OUT.glob('*')) if p.suffix in ['.csv','.parquet']]}
    (OUT/'manifest.json').write_text(json.dumps(findings,indent=2),encoding='utf-8')
    print(json.dumps({'market_years':weighted.height,'raw_daily_rows':tracks['raw_rows'].sum(),'classified_rows':matched['raw_rows'].sum(),
        'brazil_2021':weighted.filter((pl.col('market_code')=='BR')&(pl.col('year')==2021)).select('classified_tracks','chart_tracks','recording_coverage','chart_day_coverage','stream_coverage',
        *[m+'_'+w+'_pct' for m in ['romantic_affection','heartbreak','explicitness','casual_sex','misogyny','materialism','crime','weapons'] for w in ['recording','chart_day','stream']]).to_dicts(),
        'genres':gs.select('normalized_genre','chart_tracks','classified_tracks','classification_coverage','romantic_affection_pct','explicitness_pct','casual_sex_pct','misogyny_pct','materialism_pct').to_dicts()},indent=2))

if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');main()
