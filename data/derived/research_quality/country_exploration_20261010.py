"""Read-only informal description of model labels in one historical chart source."""
import json
from datetime import UTC,datetime,date
from pathlib import Path
import polars as pl
from sqlalchemy import create_engine,text
from chart_observatory.config import Settings
from chart_observatory.lyrics.classification import TAXONOMY_VERSION,PROMPT_VERSION
from chart_observatory.lyrics.identity_quarantine import load_quarantine_entries,EXCLUDED_DECISIONS

root=Path('D:/PromiscuidadeMusical')
out=root/'data/derived/research_quality'/('country-exploration-'+datetime.now(UTC).strftime('%Y%m%d-%H%M%S'))
out.mkdir()
metrics={
 'explicitness':('sexuality','sexual_explicitness'),
 'objectification':('gender_representation','objectification'),
 'misogyny':('gender_representation','misogyny'),
 'materialism':('material_status','materialism'),
 'infidelity':('relationships','infidelity'),
 'casual_sex':('relationships','casual_sex'),
 'transactional_sex':('relationships','transactional_sex'),
 'drugs_alcohol':('antisocial','drugs_alcohol','intensity'),
 'violence':('antisocial','violence','intensity'),
}
excluded={str(r.lyric_document_id) for r in load_quarantine_entries() if r.decision in EXCLUDED_DECISIONS}
engine=create_engine(Settings.load(root).database_url,connect_args={'connect_timeout':5})
assert engine.url.host=='127.0.0.1' and engine.url.port==56433
with engine.connect() as c:
 c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
 rows=c.execute(text('''WITH latest AS (SELECT DISTINCT ON (lyric_document_id) * FROM lyric_classification_snapshots
  WHERE model_id=:model AND taxonomy_version=:taxonomy AND prompt_version=:prompt
  ORDER BY lyric_document_id,append_order DESC)
  SELECT s.id,s.lyric_document_id,s.lyrics_hash,s.append_order,s.confidence,s.result_json
  FROM latest s JOIN lyric_documents d ON d.id=s.lyric_document_id
  WHERE s.classification_status='classified' AND s.confidence>=0.8
  AND s.lyrics_hash=d.content_sha256 AND d.rights_status='RESEARCH_AUTHORIZED' '''),
  {'model':'gemini-3.8-flash','taxonomy':TAXONOMY_VERSION,'prompt':PROMPT_VERSION}).mappings()
 records=[]
 for r in rows:
  if str(r['lyric_document_id']) in excluded: continue
  record={'document_id':str(r['lyric_document_id']),'lyrics_hash':r['lyrics_hash'],'append_order':r['append_order']}
  for metric,keys in metrics.items():
   value=r['result_json']
   for key in keys:value=value[key]
   assert isinstance(value,int) and 0<=value<=3
   record[metric]=value
  records.append(record)
 observed=str(c.execute(text('SELECT transaction_timestamp()')).scalar_one())
 countries=dict(c.execute(text('SELECT code,name FROM countries')).all())
engine.dispose()
classification=pl.DataFrame(records)
lineage=pl.read_parquet(root/'data/derived/research_quality/20261010-183608/original_id_lineage.parquet')
labels=lineage.filter(pl.col('metadata_lineage_verified')).join(classification,on=['document_id','lyrics_hash'],how='inner')
labels=labels.sort(['chart_track_id','append_order'],descending=[False,True]).unique(subset=['chart_track_id'],keep='first',maintain_order=True)
catalog=pl.scan_parquet(root/'data/normalized/source_catalog.parquet').filter(
 (pl.col('provider')=='MGD') & (pl.col('origin_platform')=='SPOTIFY') & (pl.col('chart_family')=='TOP_200') &
 (pl.col('period_start')>=date(2021,1,1)) & (pl.col('period_start')<=date(2021,12,31)))
days=catalog.group_by('market_code').agg(pl.col('period_start').n_unique().alias('days_observed')).collect(engine='streaming')
tracks=catalog.select('market_code',pl.col('native_id').alias('chart_track_id')).unique().collect(engine='streaming')
assert tracks['chart_track_id'].null_count()==0
totals=tracks.group_by('market_code').agg(pl.len().alias('chart_tracks'))
joined=tracks.join(labels,on='chart_track_id',how='inner')
agg=[pl.len().alias('classified_tracks')]
for metric in metrics:
 agg += [(pl.col(metric)>=2).sum().alias(metric+'_positive'),(100*(pl.col(metric)>=2).mean()).alias(metric+'_pct')]
result=joined.group_by('market_code').agg(agg).join(totals,on='market_code').join(days,on='market_code').with_columns(
 (pl.col('classified_tracks')/pl.col('chart_tracks')).alias('coverage'))
result=result.with_columns(((pl.col('market_code').str.len_chars()==2) & (pl.col('classified_tracks')>=300) &
 (pl.col('coverage')>=0.6) & (pl.col('days_observed')>=350)).alias('included'))
result=result.sort('explicitness_pct',descending=True)
result.write_csv(out/'country-metrics.csv')
included=result.filter('included')
report={'observed_utc':observed,'provider':'MGD','platform':'SPOTIFY','chart_family':'TOP_200','year':2021,
 'weighting':'unique tracks per market, equal weight; no listener/population estimate',
 'metric':'fraction of classified tracks with intensity>=2 on 0..3 model scale',
 'confidence_filter':0.8,'confidence_is_self_reported_not_calibrated':True,
 'exclusions':'known identity quarantine, invalid/mismatched snapshot hashes, unauthorized rights',
 'linkage':'exact original-song-id lineage and exact native Spotify ID, NOT independently verified lyric identity',
 'scientific_primary_eligible':False,'minimum_tracks':300,'minimum_coverage':0.6,'minimum_days':350,
 'classified_with_lineage':labels.height,'included_markets':included.height,
 'country_names':countries,'leaderboards':{metric:included.sort(metric+'_pct',descending=True).head(10).to_dicts() for metric in metrics},
 'provider_calls':0,'all_markets':result.to_dicts()}
(out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
print(json.dumps({'directory':str(out),'included_markets':included.height,'leaderboards':{
 metric:[{k:r[k] for k in ['market_code','classified_tracks','chart_tracks','coverage',metric+'_pct']} for r in
 included.sort(metric+'_pct',descending=True).head(7).to_dicts()] for metric in metrics}},ensure_ascii=False))
