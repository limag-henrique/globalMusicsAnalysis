"""Freeze article statistics from a read-only database and existing source artifacts.

Run from the repository root with .venv/Scripts/python.exe research/article/build_analysis.py.
No provider calls, raw lyric exports, database writes, or Git operations.
"""
from datetime import UTC, datetime
from pathlib import Path
import hashlib
import json
import sys

import polars as pl
from scipy.stats import spearmanr
from sqlalchemy import create_engine, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.classification import TAXONOMY_VERSION, PROMPT_VERSION
from chart_observatory.lyrics.identity_quarantine import load_quarantine_entries, EXCLUDED_DECISIONS
from chart_observatory.analysis.article_context import export_crossings, EXCLUDED_MARKETS
from chart_observatory.analysis.historical_models import export_historical_models

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'analysis-final'
OLD = ROOT / 'data/derived/research_quality/country-all-history-20261011-022524'
CONTEXT = ROOT / 'data/derived/article-country-context/20261011'
TRENDS = ROOT / 'data/derived/article-country-context/historical-trends-20261011'
METRICS = {
    'explicitness': ('sexuality', 'sexual_explicitness'),
    'sexual_desire': ('sexuality', 'sexual_desire'),
    'sexual_innuendo': ('sexuality', 'sexual_innuendo'),
    'explicit_sexual_act': ('sexuality', 'explicit_sexual_act'),
    'explicit_sexual_anatomy': ('sexuality', 'explicit_sexual_anatomy'),
    **{m: ('relationships', m) for m in ['romantic_affection','heartbreak','infidelity','transactional_sex','casual_sex','jealousy_possession','reciprocity']},
    **{m: ('gender_representation', m) for m in ['objectification','misogyny','sexual_agency','status_symbolization','commodification']},
    **{m: ('material_status', m) for m in ['money_reference','materialism','conspicuous_consumption','wealth_as_status']},
    **{m: ('antisocial',m,'intensity') for m in ['drugs_alcohol','crime','violence','weapons']},
    'territorial_identity': ('territorial_identity',),
}
FOCUS = ['explicitness','objectification','misogyny','materialism','infidelity','casual_sex','transactional_sex','drugs_alcohol','violence','crime']

def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8*1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def write(frame, name):
    frame.write_csv(OUT / (name+'.csv'))
    frame.write_parquet(OUT / (name+'.parquet'))

def aggregate(pairs, groups, labels):
    totals = pairs.group_by(groups).agg(pl.len().alias('chart_tracks'))
    matched = pairs.join(labels, on='chart_track_id', how='inner', validate='m:1')
    expr = [pl.len().alias('classified_tracks')]
    for metric in METRICS:
        expr += [(pl.col(metric)>=2).sum().alias(metric+'_positive'), (100*(pl.col(metric)>=2).mean()).alias(metric+'_pct')]
    result = totals.join(matched.group_by(groups).agg(expr), on=groups, how='left').with_columns(
        (pl.col('classified_tracks') / pl.col('chart_tracks')).alias('coverage')).sort(groups)
    assert result.filter(pl.col('classified_tracks')>pl.col('chart_tracks')).height == 0
    assert result.select(pl.struct(groups).n_unique()).item() == result.height
    for metric in METRICS:
        assert result.filter((pl.col(metric+'_pct') - 100*pl.col(metric+'_positive')/pl.col('classified_tracks')).abs()>1e-8).height == 0
    return result, matched

def main():
    if OUT.exists():
        raise RuntimeError('Frozen analysis already exists; choose a new output to refresh it.')
    OUT.mkdir(parents=True)
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={'connect_timeout':5})
    excluded = {str(x.lyric_document_id) for x in load_quarantine_entries() if x.decision in EXCLUDED_DECISIONS}
    records, categorical = [], []
    query = '''WITH latest AS (SELECT DISTINCT ON (lyric_document_id) * FROM lyric_classification_snapshots
      WHERE model_id=:model AND taxonomy_version=:taxonomy AND prompt_version=:prompt
      ORDER BY lyric_document_id,append_order DESC)'''
    params = {'model':'gemini-3.8-flash','taxonomy':TAXONOMY_VERSION,'prompt':PROMPT_VERSION}
    with engine.connect() as c:
        c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        timestamp = str(c.execute(text('SELECT transaction_timestamp()')).scalar_one())
        status = [dict(r) for r in c.execute(text(query+''' SELECT classification_status,count(*) documents,
            count(DISTINCT canonical_track_id) tracks FROM latest GROUP BY 1'''),params).mappings()]
        documents = c.execute(text('SELECT count(*) FROM lyric_documents')).scalar_one()
        rows = c.execute(text(query+''' SELECT s.id,s.lyric_document_id,s.canonical_track_id,s.lyrics_hash,
            s.append_order,s.result_json,s.confidence FROM latest s JOIN lyric_documents d ON d.id=s.lyric_document_id
            WHERE s.classification_status='classified' AND s.lyrics_hash=d.content_sha256
            AND d.rights_status='RESEARCH_AUTHORIZED' '''),params).mappings()
        for row in rows:
            if str(row['lyric_document_id']) in excluded:
                continue
            obj = row['result_json']
            r = dict(document_id=str(row['lyric_document_id']),lyric_track_id=str(row['canonical_track_id']),
                     snapshot_id=str(row['id']),lyrics_hash=row['lyrics_hash'],append_order=row['append_order'])
            for name,path in METRICS.items():
                value=obj
                for key in path: value=value[key]
                assert type(value) is int and 0<=value<=3
                r[name]=value
            records.append(r)
            categorical.append({**{k:r[k] for k in ['lyric_track_id','append_order']},
                'consent':obj['relationships']['consent'],'target_gender':obj['gender_representation']['target_gender'],
                **{m+'_stance':obj['antisocial'][m]['stance'] for m in ['drugs_alcohol','crime','violence','weapons']}})
    engine.dispose()
    annotations=pl.DataFrame(records)
    write(annotations,'selected-classifications')
    global_labels=annotations.sort('append_order',descending=True).unique('lyric_track_id',keep='first')
    global_stats=pl.DataFrame([dict(metric=m,n=global_labels.height,positive=(global_labels[m]>=2).sum(),
        pct=100*(global_labels[m]>=2).mean(),mean=global_labels[m].mean()) for m in METRICS])
    write(global_stats,'all-dimensions')
    cats=pl.DataFrame(categorical).sort('append_order',descending=True).unique('lyric_track_id',keep='first')
    distributions=[]
    for name in ['consent','target_gender','drugs_alcohol_stance','crime_stance','violence_stance','weapons_stance']:
        for row in cats.group_by(name).len().to_dicts():
            distributions.append(dict(variable=name,category=row[name],count=row['len'],n=cats.height,pct=100*row['len']/cats.height))
    write(pl.DataFrame(distributions),'categorical-distributions')
    lineage=pl.read_parquet(OLD/'recovered-original-id-lineage.parquet')
    labels=lineage.join(annotations,on=['document_id','lyrics_hash'],validate='m:1').sort('append_order',descending=True).unique('chart_track_id',keep='first')
    write(labels,'native-id-annotations')
    catalog=pl.read_parquet(OLD/'unique-chart-track-market-year-source.parquet').filter(pl.col('origin_platform')=='SPOTIFY')
    catalog=catalog.filter(~pl.col('market_code').is_in(EXCLUDED_MARKETS))
    pairs=catalog.select('market_code','chart_track_id').unique()
    country,matched=aggregate(pairs,['market_code'],labels)
    write(country,'country-metrics')
    annual,_=aggregate(catalog.select('market_code','year','chart_track_id').unique(),['market_code','year'],labels)
    write(annual,'annual-country-metrics')
    by_source,_=aggregate(catalog.select('provider','chart_family','market_code','chart_track_id').unique(),['provider','chart_family','market_code'],labels)
    write(by_source,'source-specific-country-metrics')
    source_cov=catalog.select('provider','chart_family','chart_track_id').unique().group_by('provider','chart_family').agg(
        pl.len().alias('chart_tracks'),pl.col('chart_track_id').is_in(labels['chart_track_id'].implode()).sum().alias('classified_tracks'))
    write(source_cov,'source-coverage')
    observations=pl.read_parquet(CONTEXT/'country-context-observations.parquet')
    indicators=pl.read_parquet(CONTEXT/'coverage.parquet')['indicator_code'].unique().to_list()
    export_crossings(annual,observations,indicators,OUT/'context')
    panel=pl.read_parquet(OUT/'context/country-year-crossings.parquet')
    cov=pl.read_parquet(OUT/'context/coverage.parquet').group_by('indicator_code').agg(
        pl.len().alias('expected'),pl.col('value').is_not_null().sum().alias('observed'),
        pl.col('market_code').filter(pl.col('value').is_not_null()).n_unique().alias('markets')).sort('indicator_code')
    write(cov,'context-coverage')
    associations=[]
    families=[('objectification','gender_inequality_index'),('misogyny','gender_inequality_index'),
        ('objectification','sigi_2019'),('misogyny','sigi_2019'),('materialism','gini'),
        ('materialism','gdp_pc_ppp_constant'),('materialism','youth_unemployment'),
        ('violence','homicide_unodc_total'),('crime','homicide_unodc_total'),
        ('violence','homicide_unodc_female'),('violence','homicide_unodc_female_intimate_partner_family')]
    for music,context in families:
        for year in range(2017,2022):
            sample=panel.filter((pl.col('year')==year)&(pl.col('classified_tracks')>=300)).select('market_code','coverage',music+'_pct',context).drop_nulls()
            rho=float(spearmanr(sample[music+'_pct'],sample[context]).statistic) if sample.height>=10 and sample[context].n_unique()>1 else None
            associations.append(dict(metric=music,context=context,year=year,n=sample.height,rho=rho,
                min_coverage=sample['coverage'].min(),median_coverage=sample['coverage'].median()))
    write(pl.DataFrame(associations),'context-associations')
    old_trends=pl.read_parquet(TRENDS/'country-year-trends.parquet')
    old_music=pl.read_parquet(TRENDS/'country-year-music.parquet')
    drop=[x for x in old_music.columns if x not in ['market_code','year']]
    trajectories=old_trends.drop(drop).join(annual,on=['market_code','year'],validate='m:1')
    trajectories=trajectories.join(panel.select('market_code','year','internet_users','gdp_pc_ppp_constant'),
        on=['market_code','year'],validate='m:1')
    assert trajectories['internet_users'].null_count() < trajectories.height
    assert trajectories['gdp_pc_ppp_constant'].null_count() < trajectories.height
    write(trajectories,'country-year-trends')
    # Retain the ten outcomes used in the established historical specification.
    historical=trajectories.drop([m+'_pct' for m in METRICS if m not in FOCUS])
    model_counts=export_historical_models(historical,OUT/'models')
    persistence=pl.read_parquet(ROOT/'data/derived/article/persistence.parquet').filter(~pl.col('market_code').is_in(EXCLUDED_MARKETS))
    structural=persistence.group_by('market_code').agg(pl.len().alias('track_market_pairs'),
        pl.col('native_periods').median().alias('median_chart_days'),pl.col('native_periods').quantile(.25).alias('p25_chart_days'),
        pl.col('native_periods').quantile(.75).alias('p75_chart_days'),pl.col('native_periods').mean().alias('mean_chart_days'),
        pl.col('calendar_span_days').median().alias('median_span_days'))
    turnover=pl.read_parquet(ROOT/'data/derived/article/market_anxiety.parquet').filter(~pl.col('market_code').is_in(EXCLUDED_MARKETS)).filter(
        (pl.col('period_start')-pl.col('previous_period_start')).dt.total_days()==1).group_by('market_code').agg(
        pl.len().alias('adjacent_chart_pairs'),pl.col('turnover_rate').mean().alias('mean_jaccard_turnover'),pl.col('new_entries').mean().alias('mean_top50_entries'))
    write(structural.join(turnover,on='market_code',how='left'),'chart-dynamics')
    input_paths=[OLD/'recovered-original-id-lineage.parquet',OLD/'unique-chart-track-market-year-source.parquet',OLD/'source-inventory.csv',
        CONTEXT/'country-context-observations.parquet',CONTEXT/'coverage.parquet',CONTEXT/'music-genre_variation.parquet',
        TRENDS/'country-year-trends.parquet',TRENDS/'country-year-music.parquet',ROOT/'data/derived/article/persistence.parquet',
        ROOT/'data/derived/article/market_anxiety.parquet',ROOT/'data/derived/article/genre_distance.parquet',
        ROOT/'data/derived/research_quality/automated-quality-20261010-final/report.json',
        ROOT/'src/chart_observatory/analysis/historical_models.py',Path(__file__).resolve()]
    manifest=dict(created_utc=datetime.now(UTC).isoformat(),database_snapshot_utc=timestamp,documents=documents,status_counts=status,
        selected_documents=annotations.height,selected_unique_tracks=global_labels.height,linked_native_ids=labels.height,
        geographic_unique_tracks=matched['chart_track_id'].n_unique(),markets=country.height,country_years=annual.height,
        chart_unique_tracks=pairs['chart_track_id'].n_unique(),track_market_pairs=pairs.height,annotated_track_market_pairs=matched.height,
        model=params,model_counts=model_counts,metric_threshold=2,confidence_filter=None,
        expert_verification=dict(status='completed',scope='classification results and lyric-to-recording linkage',
            source='Project lead confirmation, 2026-10-11; record the stage as completed only'),
        selection='Latest matching model/taxonomy/prompt per document; current document hash; research authorization; existing identity exclusions; latest per track/native ID',
        source_policy='MGD and Kaggle Spotify Top 200/Viral 50; equal weight per distinct native recording ID per market/year; GLOBAL/HK/PR excluded',
        provider_calls=0,database_writes=0,
        inputs=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in input_paths],
        outputs=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()])
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['inputs','outputs']},indent=2))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
