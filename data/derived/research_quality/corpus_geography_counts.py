"""Read-only country/year coverage of the quoted pending cohort and current corpus."""
import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from sqlalchemy import create_engine, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.classification import PROMPT_VERSION, TAXONOMY_VERSION

ROOT = Path('D:/PromiscuidadeMusical')
REFERENCE = ROOT/'data/derived/research_quality/country-all-history-20261011-022524'
OUT = ROOT/'data/derived/research_quality'/('corpus-geography-'+datetime.now(UTC).strftime('%Y%m%d-%H%M%S'))
OUT.mkdir()
historical = pl.read_csv(ROOT/'data/derived/research_quality/20261011-061304/snapshot_eligibility.csv', columns=['document_id','track_id','status'])
engine = create_engine(Settings.load(ROOT).database_url, connect_args={'connect_timeout':5})
assert engine.url.host == '127.0.0.1' and engine.url.port == 56433
with engine.connect() as connection:
    connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
    observed = str(connection.execute(text('SELECT transaction_timestamp()')).scalar_one())
    rows = connection.execute(text('''WITH latest AS (SELECT DISTINCT ON (lyric_document_id)
      lyric_document_id,canonical_track_id,classification_status FROM lyric_classification_snapshots
      WHERE model_id=:model AND taxonomy_version=:taxonomy AND prompt_version=:prompt
      ORDER BY lyric_document_id,append_order DESC)
      SELECT d.id::text document_id,d.canonical_track_id::text track_id,
      coalesce(l.classification_status,'not_submitted') status FROM lyric_documents d
      LEFT JOIN latest l ON l.lyric_document_id=d.id'''),
      {'model':'gemini-3.8-flash','taxonomy':TAXONOMY_VERSION,'prompt':PROMPT_VERSION}).mappings()
    current = pl.DataFrame([dict(x) for x in rows])
engine.dispose()
lineage = pl.read_parquet(REFERENCE/'recovered-original-id-lineage.parquet').select('document_id','chart_track_id').unique()
mapping = lineage.join(current.select('document_id','track_id'),on='document_id').select('chart_track_id','track_id').unique()
# Reuse the source inventory whose Spotify URL/ID normalization was previously checked.
catalog = pl.scan_parquet(REFERENCE/'unique-chart-track-market-year-source.parquet').filter(
    pl.col('origin_platform')=='SPOTIFY').select('market_code','year','chart_track_id').unique().collect()
pairs = catalog.join(mapping,on='chart_track_id').select('market_code','year','track_id').unique()
pairs.write_parquet(OUT/'linked-track-market-year.parquet')

def summarize(frame, name):
    status = frame.group_by('track_id').agg((pl.col('status')=='classified').any().alias('classified'))
    counts = {'total_tracks':status.height,'classified_tracks':status['classified'].sum(),
              'pending_tracks':status.filter(~pl.col('classified')).height}
    linked = pairs.join(status,on='track_id')
    per_country = linked.group_by('market_code','track_id').agg(pl.col('classified').first(),
          pl.col('year').min().alias('first_year'),pl.col('year').max().alias('last_year'))
    countries = per_country.group_by('market_code').agg(pl.len().alias('total_corpus_tracks'),
          pl.col('classified').sum().alias('classified_tracks'),(~pl.col('classified')).sum().alias('pending_tracks'),
          pl.col('first_year').min(),pl.col('last_year').max()).with_columns(
          (100*pl.col('pending_tracks')/pl.col('total_corpus_tracks')).alias('pending_pct'))
    annual_country = linked.group_by('market_code','year').agg(pl.len().alias('total_corpus_tracks'),
          pl.col('classified').sum().alias('classified_tracks'),(~pl.col('classified')).sum().alias('pending_tracks'))
    annual_global = linked.select('year','track_id','classified').unique().group_by('year').agg(
          pl.len().alias('total_corpus_tracks'),pl.col('classified').sum().alias('classified_tracks'),
          (~pl.col('classified')).sum().alias('pending_tracks')).sort('year')
    countries.sort('market_code').write_csv(OUT/(name+'-country-counts.csv'))
    annual_country.sort('market_code','year').write_csv(OUT/(name+'-country-year-counts.csv'))
    annual_global.write_csv(OUT/(name+'-year-counts.csv'))
    matched = linked['track_id'].n_unique()
    pending = status.filter(~pl.col('classified'))
    unmatched = status.join(linked.select('track_id').unique(),on='track_id',how='anti')
    for row in countries.to_dicts():
        assert row['total_corpus_tracks']==row['classified_tracks']+row['pending_tracks']
    assert counts['total_tracks']==counts['classified_tracks']+counts['pending_tracks']
    return {**counts,'mapped_unique_tracks':matched,
      'unmapped_classified_tracks':unmatched['classified'].sum(),
      'unmapped_pending_tracks':unmatched.filter(~pl.col('classified')).height,
      'mapped_pending_unique_tracks':pending.join(linked.select('track_id').unique(),on='track_id')['track_id'].n_unique(),
      'countries':countries.sort('classified_tracks',descending=True).to_dicts(),
      'pending_country_order':countries.filter(pl.col('market_code')!='GLOBAL').sort('pending_tracks',descending=True).to_dicts(),
      'years':annual_global.to_dicts(),
      'brazil_years':annual_country.filter(pl.col('market_code')=='BR').sort('year').to_dicts()}

old = summarize(historical,'quoted-cohort')
assert old['pending_tracks']==19671 and old['classified_tracks']==139409
now = summarize(current,'current')
report = {'observed_utc':observed,'quoted_snapshot_utc':'2026-10-11T06:13:05.712984+00:00',
    'quoted_cohort':old,'current':now,
    'source_years':[2017,2018,2019,2020,2021,2022],
    'last_source_date':'2022-03-13','sources':'Spotify Top 200 and Viral 50, MGD and Kaggle',
    'unit':'canonical corpus track UUID; deduplicated across recording IDs, years, chart families and providers per market',
    'market_interpretation':'Circulation market, not artist origin; years are ranking observation years, not release years',
    'overlap':'Tracks may belong to multiple countries and multiple years; rows must not be summed as globally unique music',
    'lineage':'Exact original source ID/document lineage; no fuzzy association, no independently validated lyric identity',
    'classification_inclusion':'Operational classified status, including exploratory records; not scientific eligibility or accuracy',
    'unlinked_2026_sources':'YouTube and Pro-Musica had no exact usable song links in the prior full source inventory',
    'online_model_calls':0,'database_mutations':0}
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'directory':str(OUT),'observed_utc':observed,
    'quoted':{k:v for k,v in old.items() if k not in ('countries','pending_country_order','brazil_years')},
    'current':{k:v for k,v in now.items() if k not in ('countries','pending_country_order','brazil_years')},
    'top_pending':old['pending_country_order'][:15],
    'current_countries':now['countries']},ensure_ascii=True))
