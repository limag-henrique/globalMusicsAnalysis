"""Analyze international repertoire trends from the existing verified freeze.

Equal-market panels, distinct-recording pools, source sensitivity and fixed-sample
social correlations. Reads local files only; never calls a model or writes the DB.
"""
from datetime import UTC, datetime, date
from pathlib import Path
import hashlib
import json
import sys

import polars as pl
from scipy.stats import spearmanr

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DATA=HERE/'analysis-final'
OUT=HERE/'global-patterns'
YEARS=list(range(2017,2022))
CONTEXT_PAIRS=[('romantic_affection','youth_unemployment'),('materialism','gdp_pc_ppp_constant'),
    ('materialism','gini'),('misogyny','gender_inequality_index'),
    ('violence','homicide_unodc_total'),('territorial_identity','urban_population')]

def write(frame,name):
    frame.write_csv(OUT/(name+'.csv'))
    frame.write_parquet(OUT/(name+'.parquet'))

def balanced(frame,cutoff=.5):
    eligible=frame.filter((pl.col('classified_tracks')>=300)&(pl.col('coverage')>=cutoff)&pl.col('year').is_in(YEARS))
    markets=eligible.group_by('market_code').agg(pl.col('year').n_unique().alias('years')).filter(pl.col('years')==5)['market_code'].to_list()
    return eligible.filter(pl.col('market_code').is_in(markets)),sorted(markets)

def aggregate(pairs,groups,labels,metrics):
    counts=pairs.group_by(groups).agg(pl.len().alias('chart_tracks'))
    joined=pairs.join(labels,on='chart_track_id',validate='m:1')
    stats=joined.group_by(groups).agg(pl.len().alias('classified_tracks'),
        *[(pl.col(m)>=2).sum().alias(m+'_positive') for m in metrics])
    stats=counts.join(stats,on=groups,how='left').with_columns(
        (pl.col('classified_tracks')/pl.col('chart_tracks')).alias('coverage'),
        *[(100*pl.col(m+'_positive')/pl.col('classified_tracks')).alias(m+'_pct') for m in metrics]).sort(groups)
    assert stats.select(pl.struct(groups).n_unique()).item()==stats.height
    assert stats.filter(pl.col('classified_tracks')>pl.col('chart_tracks')).height==0
    return stats

def summarize(frame,markets,label,metrics):
    trends=[]
    for year in YEARS:
        f=frame.filter(pl.col('year')==year)
        assert f.height==len(markets)
        for m in metrics:
            v=f[m+'_pct']
            trends.append(dict(panel=label,year=year,metric=m,markets=len(markets),mean_pct=v.mean(),median_pct=v.median(),
                p25_pct=v.quantile(.25,interpolation='linear'),p75_pct=v.quantile(.75,interpolation='linear'),
                min_pct=v.min(),max_pct=v.max(),classified_track_market_years=f['classified_tracks'].sum(),
                mean_classification_coverage=f['coverage'].mean()))
    changes=[]
    first=frame.filter(pl.col('year')==2017)
    last=frame.filter(pl.col('year')==2021)
    for m in metrics:
        values=first.select('market_code',pl.col(m+'_pct').alias('start_pct')).join(
            last.select('market_code',pl.col(m+'_pct').alias('end_pct')),on='market_code',validate='1:1').with_columns(
            (pl.col('end_pct')-pl.col('start_pct')).alias('change_pp'))
        for r in values.to_dicts():changes.append(dict(panel=label,metric=m,**r))
    return pl.DataFrame(trends),pl.DataFrame(changes)

def main():
    OUT.mkdir(exist_ok=True)
    metrics=pl.read_csv(DATA/'all-dimensions.csv')['metric'].to_list()
    annual=pl.read_parquet(DATA/'annual-country-metrics.parquet')
    panel,markets=balanced(annual)
    assert len(markets)==55 and panel.height==275 and 'BR' in markets
    write(panel,'balanced-country-year')
    trend,changes=summarize(panel,markets,'combined55',metrics)
    panels=[trend];deltas=[changes];panel_meta={'combined55':markets}
    strict,strict_markets=balanced(annual,.7)
    tr,de=summarize(strict,strict_markets,'coverage70',metrics)
    panels.append(tr);deltas.append(de);panel_meta['coverage70']=strict_markets
    labels=pl.read_parquet(DATA/'native-id-annotations.parquet').select('chart_track_id',*metrics)
    assert labels['chart_track_id'].n_unique()==labels.height
    catalog_path=ROOT/'data/derived/research_quality/country-all-history-20261011-022524/unique-chart-track-market-year-source.parquet'
    catalog=pl.read_parquet(catalog_path).filter((pl.col('origin_platform')=='SPOTIFY')&pl.col('market_code').is_in(markets)&pl.col('year').is_in(YEARS))
    pooled=aggregate(catalog.select('year','chart_track_id').unique(),['year'],labels,metrics)
    write(pooled,'distinct-recording-year-pool')
    # Fixed 55-market universe; source-specific availability and coverage are reported.
    source_panels={}
    for label,source in [('top200_union',catalog.filter(pl.col('chart_family')=='TOP_200')),
        ('mgd_top200',catalog.filter((pl.col('provider')=='MGD')&(pl.col('chart_family')=='TOP_200'))),
        ('kaggle_viral50',catalog.filter(pl.col('chart_family')=='VIRAL_50'))]:
        source_annual=aggregate(source.select('market_code','year','chart_track_id').unique(),['market_code','year'],labels,metrics)
        write(source_annual,label+'-annual')
        source_panel,source_markets=balanced(source_annual)
        source_panels[label]=(source_panel,source_markets)
        tr,de=summarize(source_panel,source_markets,label,metrics)
        panels.append(tr);deltas.append(de);panel_meta[label]=source_markets
    common=sorted(set(source_panels['top200_union'][1])&set(source_panels['kaggle_viral50'][1]))
    for source,name in [('top200_union','top200_matched52'),('kaggle_viral50','viral50_matched52')]:
        frame=source_panels[source][0].filter(pl.col('market_code').is_in(common))
        tr,de=summarize(frame,common,name,metrics)
        panels.append(tr);deltas.append(de);panel_meta[name]=common
    quality=pl.read_parquet(ROOT/'data/derived/mgd_coverage.parquet')
    qmarkets=quality.filter(pl.col('eligible')&(pl.col('first_date')<=date(2017,1,1)))['country_code'].to_list()
    qmarkets=sorted(set(qmarkets)&set(markets))
    qpanel=panel.filter(pl.col('market_code').is_in(qmarkets))
    tr,de=summarize(qpanel,qmarkets,'full_window_chart_quality',metrics)
    panels.append(tr);deltas.append(de);panel_meta['full_window_chart_quality']=qmarkets
    all_trends=pl.concat(panels).sort('panel','metric','year')
    all_changes=pl.concat(deltas).sort('panel','metric','market_code')
    write(all_trends,'annual-global-trends');write(all_changes,'market-endpoint-changes')
    summary=all_changes.group_by('panel','metric').agg(pl.len().alias('markets'),
        pl.col('start_pct').mean().alias('start_mean_pct'),pl.col('end_pct').mean().alias('end_mean_pct'),
        pl.col('change_pp').mean().alias('mean_change_pp'),pl.col('change_pp').median().alias('median_change_pp'),
        pl.col('change_pp').quantile(.25,interpolation='linear').alias('p25_change_pp'),
        pl.col('change_pp').quantile(.75,interpolation='linear').alias('p75_change_pp'),
        (pl.col('change_pp')>0).sum().alias('markets_increasing'),(pl.col('change_pp')<0).sum().alias('markets_decreasing')).sort('panel','metric')
    write(summary,'change-summary')
    # Same-market means must agree with the mean of paired differences.
    assert summary.filter((pl.col('mean_change_pp')-(pl.col('end_mean_pct')-pl.col('start_mean_pct'))).abs()>1e-10).height==0
    # All-market pooled recording counts must not sum duplicate appearances.
    assert pooled['classified_tracks'].sum()<=panel['classified_tracks'].sum()
    social=pl.read_parquet(DATA/'context/country-year-crossings.parquet').filter(pl.col('market_code').is_in(markets)&pl.col('year').is_in(YEARS))
    context_records=[];context_samples=[]
    for lyric,external in CONTEXT_PAIRS:
        valid=social.select('market_code','year',lyric+'_pct',external).drop_nulls()
        stable=valid.group_by('market_code').agg(pl.col('year').n_unique().alias('years')).filter(pl.col('years')==5)['market_code'].to_list()
        for year in YEARS:
            sample=valid.filter(pl.col('market_code').is_in(stable)&(pl.col('year')==year))
            rho=float(spearmanr(sample[lyric+'_pct'],sample[external]).statistic)
            context_records.append(dict(metric=lyric,context=external,year=year,markets=len(stable),rho=rho))
            for r in sample.to_dicts():context_samples.append(dict(metric=lyric,context=external,**r))
    write(pl.DataFrame(context_records),'fixed-sample-social-correlations')
    (OUT/'context-samples.json').write_text(json.dumps(context_samples,indent=2),encoding='utf-8')
    # Pattern structure is descriptive: population prevalence and causal effects are not estimated.
    focus=['romantic_affection','heartbreak','explicitness','misogyny','materialism','crime','weapons','territorial_identity']
    report={'created_utc':datetime.now(UTC).isoformat(),'database_snapshot_utc':json.loads((DATA/'manifest.json').read_text())['database_snapshot_utc'],
        'years':YEARS,'threshold':2,'balanced_panel':'same 55 markets; >=300 classified IDs and >=50% classification coverage in every full year',
        'weighting':'equal market; each recording ID counted once per market/year; pooled sensitivity counts each ID once per year across selected markets',
        'spread':'quartiles describe the observed market distribution; not confidence intervals',
        'interpretation':'descriptive repertoire change; fixed classification reused over appearances; no within-song semantic change or population trend inferred',
        'panels':panel_meta,'selected_changes':summary.filter((pl.col('panel')=='combined55')&pl.col('metric').is_in(focus)).to_dicts(),
        'provider_calls':0,'database_writes':0,
        'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in
            [DATA/'annual-country-metrics.parquet',DATA/'native-id-annotations.parquet',DATA/'context/country-year-crossings.parquet',catalog_path,ROOT/'data/derived/mgd_coverage.parquet',Path(__file__)]],
        'outputs':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(OUT.glob('*'))
            if p.is_file() and (p.suffix in ['.csv','.parquet'] or p.name=='context-samples.json')]}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'panels':{k:len(v) for k,v in panel_meta.items()},'changes':report['selected_changes'],'social_correlations':context_records},indent=2))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
