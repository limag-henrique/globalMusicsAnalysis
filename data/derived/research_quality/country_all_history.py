"""Local descriptive analysis of all imported classifications and available chart history.

Read-only PostgreSQL and local files. No uploads or provider generation.
"""
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import polars as pl
from sqlalchemy import create_engine, text
from chart_observatory.config import Settings
from chart_observatory.lyrics.classification import TAXONOMY_VERSION, PROMPT_VERSION
from chart_observatory.lyrics.identity_quarantine import load_quarantine_entries, EXCLUDED_DECISIONS

ROOT = Path('D:/PromiscuidadeMusical')
OUT = ROOT/'data/derived/research_quality'/('country-all-history-'+datetime.now(UTC).strftime('%Y%m%d-%H%M%S'))
OUT.mkdir()
METRICS = {
    'explicitness': ('sexuality', 'sexual_explicitness'),
    'objectification': ('gender_representation', 'objectification'),
    'misogyny': ('gender_representation', 'misogyny'),
    'materialism': ('material_status', 'materialism'),
    'infidelity': ('relationships', 'infidelity'),
    'casual_sex': ('relationships', 'casual_sex'),
    'transactional_sex': ('relationships', 'transactional_sex'),
    'drugs_alcohol': ('antisocial', 'drugs_alcohol', 'intensity'),
    'violence': ('antisocial', 'violence', 'intensity'),
    'crime': ('antisocial', 'crime', 'intensity'),
}

def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())

excluded = {str(x.lyric_document_id) for x in load_quarantine_entries() if x.decision in EXCLUDED_DECISIONS}
engine = create_engine(Settings.load(ROOT).database_url, connect_args={'connect_timeout': 5})
assert engine.url.host == '127.0.0.1' and engine.url.port == 56433
records = []
with engine.connect() as connection:
    connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
    observed = str(connection.execute(text('SELECT transaction_timestamp()')).scalar_one())
    latest = '''WITH latest AS (SELECT DISTINCT ON (lyric_document_id) *
    FROM lyric_classification_snapshots WHERE model_id=:model AND taxonomy_version=:taxonomy
    AND prompt_version=:prompt ORDER BY lyric_document_id,append_order DESC)'''
    params = {'model': 'gemini-3.8-flash', 'taxonomy': TAXONOMY_VERSION, 'prompt': PROMPT_VERSION}
    totals = dict(connection.execute(text(latest+''' SELECT count(*) FILTER (WHERE classification_status='classified') classified_documents,
      count(DISTINCT canonical_track_id) FILTER (WHERE classification_status='classified') classified_tracks,
      count(*) FILTER (WHERE classification_status='error') error_documents FROM latest'''),params).mappings().one())
    document_rows = list(connection.execute(text('SELECT id,canonical_track_id,source,content_sha256 FROM lyric_documents')).mappings())
    keys = {(str(x['canonical_track_id']),x['source'],x['content_sha256']): str(x['id']) for x in document_rows}
    rows = connection.execute(text(latest+''' SELECT s.id,s.lyric_document_id,s.canonical_track_id,
      s.lyrics_hash,s.append_order,s.confidence,s.result_json FROM latest s
      JOIN lyric_documents d ON d.id=s.lyric_document_id WHERE s.classification_status='classified'
      AND s.lyrics_hash=d.content_sha256 AND d.rights_status='RESEARCH_AUTHORIZED' '''),params).mappings()
    for row in rows:
        if str(row['lyric_document_id']) in excluded:
            continue
        record = {'document_id':str(row['lyric_document_id']), 'lyric_track_id':str(row['canonical_track_id']),
          'snapshot_id':str(row['id']), 'lyrics_hash':row['lyrics_hash'], 'append_order':row['append_order'],
          'confidence':float(row['confidence'])}
        for metric, path in METRICS.items():
            value = row['result_json']
            for component in path:
                value = value[component]
            assert isinstance(value,int) and 0 <= value <= 3
            record[metric] = value
        records.append(record)
engine.dispose()
annotations = pl.DataFrame(records)
annotations.write_parquet(OUT/'classified-snapshot-selection.parquet')
global_annotations = annotations.sort('append_order',descending=True).unique(subset='lyric_track_id',keep='first')

# Recover provider IDs even when absent from track_master; require the exact original
# title/artist-derived UUID, provider source, and text SHA to resolve to an existing document.
lineage_rows = []
lineage_errors = Counter()
master_by_id = {row['canonical_track_id']:row for row in pl.read_parquet(ROOT/'data/derived/track_master.parquet').iter_rows(named=True)}
artifact = ROOT/'data/derived/lyrics/gemini_annotations.jsonl'
with artifact.open(encoding='utf-8') as stream:
    for line_number, line in enumerate(stream, 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            lineage_errors['malformed'] += 1
            continue
        if not isinstance(payload,dict):
            lineage_errors['not_object'] += 1
            continue
        title, artist = str(payload.get('title') or '').strip(), str(payload.get('artist') or '').strip()
        lyrics, provider_id = payload.get('original_lyrics'), payload.get('song_id')
        if not title or not artist or not isinstance(lyrics,str) or not isinstance(provider_id,str):
            lineage_errors['missing_identity'] += 1
            continue
        parsed_id = re.fullmatch(r'(?:https://open\.spotify\.com/track/|spotify:track:)?([A-Za-z0-9]{22})(?:\?.*)?', provider_id)
        if parsed_id:
            provider_id = parsed_id.group(1)
        master = master_by_id.get(provider_id)
        if master and (normalize(title)!=normalize(master['title'] or '') or normalize(artist)!=normalize(master['artist_names'] or '')):
            lineage_errors['known_master_metadata_mismatch'] += 1
            continue
        digest = hashlib.sha256(lyrics.encode('utf-8')).hexdigest()
        track = str(uuid5(NAMESPACE_URL,'chart-observatory:api-lyrics:track:v1:'+normalize(artist)+'\0'+normalize(title)))
        source = str(payload.get('lyrics_source') or 'UNKNOWN_API').strip().upper()[:100]
        document = keys.get((track,source,digest))
        if document is None:
            lineage_errors['no_exact_document'] += 1
            continue
        lineage_rows.append({'document_id':document,'chart_track_id':provider_id,
          'lyrics_hash':digest,'source_row_number':line_number})
lineage = pl.DataFrame(lineage_rows).unique(subset=['document_id','chart_track_id','lyrics_hash'])
lineage.write_parquet(OUT/'recovered-original-id-lineage.parquet')
labels = lineage.join(annotations,on=['document_id','lyrics_hash'],how='inner').sort('append_order',descending=True).unique(subset='chart_track_id',keep='first')
labels.write_parquet(OUT/'native-id-annotations.parquet')

catalog = pl.scan_parquet(ROOT/'data/normalized/source_catalog.parquet')
inventory = catalog.group_by('provider','origin_platform','chart_family').agg(pl.len().alias('rows'),
  pl.col('period_start').min().alias('first_date'),pl.col('period_end').max().alias('last_date')).collect(engine='streaming')
inventory.write_csv(OUT/'source-inventory.csv')
native_catalog = catalog.filter(pl.col('native_id').is_not_null()).with_columns(
  pl.when(pl.col('origin_platform')=='SPOTIFY').then(pl.col('native_id').str.extract(
    r'^(?:https://open\.spotify\.com/track/|spotify:track:)?([A-Za-z0-9]{22})(?:\?.*)?$',1)).otherwise(pl.col('native_id')).alias('normalized_native_id')
  ).select('provider','origin_platform',
  'chart_family','market_code',pl.col('period_start').dt.year().alias('year'),
  pl.col('normalized_native_id').alias('chart_track_id')).unique().collect(engine='streaming')
assert native_catalog['chart_track_id'].null_count()==0, 'Unrecognized native ID format; do not infer linkage'
native_catalog.write_parquet(OUT/'unique-chart-track-market-year-source.parquet')
source_pairs = native_catalog.select('provider','origin_platform','chart_family','market_code','chart_track_id').unique()
source_totals = source_pairs.group_by('provider','origin_platform','chart_family').agg(pl.len().alias('track_market_pairs'),
  pl.col('chart_track_id').n_unique().alias('unique_native_ids'))
source_matches = source_pairs.join(labels.select('chart_track_id'),on='chart_track_id').group_by('provider','origin_platform','chart_family').agg(pl.len().alias('annotated_pairs'),pl.col('chart_track_id').n_unique().alias('annotated_unique_ids'))
source_coverage = source_totals.join(source_matches,on=['provider','origin_platform','chart_family'],how='left').fill_null(0)
source_coverage.write_csv(OUT/'source-annotation-coverage.csv')

def aggregate(pairs, groups):
    totals = pairs.group_by(groups).agg(pl.len().alias('chart_tracks'))
    matched = pairs.join(labels,on='chart_track_id',how='inner')
    expressions = [pl.len().alias('classified_tracks'),pl.col('confidence').mean().alias('mean_model_confidence')]
    for metric in METRICS:
        expressions += [(pl.col(metric)>=2).sum().alias(metric+'_positive'),
          (100*(pl.col(metric)>=2).mean()).alias(metric+'_pct')]
    result = matched.group_by(groups).agg(expressions).join(totals,on=groups).with_columns(
      (pl.col('classified_tracks')/pl.col('chart_tracks')).alias('coverage'))
    for row in result.to_dicts():
        assert row['classified_tracks'] <= row['chart_tracks']
        for metric in METRICS:
            assert 0 <= row[metric+'_positive'] <= row['classified_tracks']
            assert abs(row[metric+'_pct']-100*row[metric+'_positive']/row['classified_tracks']) < 1e-8
    return result, matched

spotify = native_catalog.filter(pl.col('origin_platform')=='SPOTIFY')
combined_pairs = spotify.select('market_code','chart_track_id').unique()
combined, combined_matched = aggregate(combined_pairs,['market_code'])
periods = spotify.group_by('market_code').agg(pl.col('year').min().alias('first_year'),pl.col('year').max().alias('last_year'),pl.col('year').n_unique().alias('years_observed'))
combined = combined.join(periods,on='market_code').with_columns(
  ((pl.col('market_code').str.len_chars()==2) & (pl.col('classified_tracks')>=300)).alias('included_market'))
combined.write_csv(OUT/'all-history-country-metrics.csv')
annual, _ = aggregate(spotify.select('market_code','year','chart_track_id').unique(),['market_code','year'])
annual.write_csv(OUT/'annual-country-metrics.csv')
by_source, _ = aggregate(source_pairs.filter(pl.col('origin_platform')=='SPOTIFY'),['provider','chart_family','market_code'])
by_source.write_csv(OUT/'source-specific-country-metrics.csv')

eligible = combined.filter('included_market').filter(~pl.col('market_code').is_in(['HK','PR']))
included_pairs = combined_pairs.filter(pl.col('market_code').is_in(eligible['market_code']))
included_matches = included_pairs.join(labels,on='chart_track_id')
global_metrics = {metric:100*(global_annotations[metric]>=2).mean() for metric in METRICS}
report = {'observed_utc':observed,'latest_corpus_totals':totals,'valid_classified_unique_tracks_after_quarantine':global_annotations.height,
  'global_metrics':global_metrics,'exact_original_lineage_documents':lineage['document_id'].n_unique(),
  'classified_original_native_ids':labels.height,'lineage_errors':dict(lineage_errors),
  'all_spotify_matched_unique_tracks':combined_matched['chart_track_id'].n_unique(),
  'all_spotify_catalog_unique_tracks':combined_pairs['chart_track_id'].n_unique(),
  'included_markets':eligible.height,'included_unique_annotated_tracks':included_matches['chart_track_id'].n_unique(),
  'included_annotated_track_market_pairs':included_matches.height,'included_catalog_unique_tracks':included_pairs['chart_track_id'].n_unique(),
  'years':sorted(spotify['year'].unique().to_list()),'sources':inventory.to_dicts(),
  'source_coverage':source_coverage.to_dicts(),'confidence_filter':None,'metric_threshold':2,
  'minimum_classified_tracks_for_leaderboard':300,'coverage_exclusion_threshold':None,
  'weighting':'unique music recording ID per market across all years and both Spotify chart families/providers, equal weight; overlapping sources deduplicated',
  'comparison_linkage':'original source IDs and exact document lineage only; independently verified lyric identity remains unavailable',
  'missing_data':'excluded from scored denominators and reported through coverage; never score zero',
  'all_available_sources_considered':True,'unlinked_sources_not_guessed':True,
  'primary_scientific_eligible':False,'population_inference_supported':False,'online_model_calls':0,
  'leaderboards':{metric:eligible.sort(metric+'_pct',descending=True).head(10).to_dicts() for metric in METRICS},
  'all_markets':combined.to_dicts(),
  'brazil':combined.filter(pl.col('market_code')=='BR').to_dicts(),
  'brazil_annual':annual.filter(pl.col('market_code')=='BR').sort('year').to_dicts()}
(OUT/'report.json').write_text(json.dumps(report,default=str,indent=2,ensure_ascii=False))
print(json.dumps({'directory':str(OUT),'latest_corpus_totals':totals,
 'included_unique_annotated_tracks':report['included_unique_annotated_tracks'],
 'included_markets':report['included_markets'],'source_coverage':report['source_coverage'],
 'leaderboards':{metric:[{k:r[k] for k in ['market_code','classified_tracks','coverage',metric+'_pct']} for r in
 report['leaderboards'][metric][:6]] for metric in METRICS},'brazil':report['brazil']},default=str))
