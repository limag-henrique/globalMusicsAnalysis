"""Read-only, frozen-snapshot quality inspection; no provider calls or lyric exports."""
import csv
import hashlib
import heapq
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError
from sqlalchemy import create_engine, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.classification import LyricsClassification
from chart_observatory.lyrics.identity_quarantine import load_quarantine_entries, load_suspended_sources
from chart_observatory.lyrics.scientific_selection import assess_classification

ROOT = Path('D:/PromiscuidadeMusical')
OUT = Path(__file__).parent
SEED = 'classification-quality-20261010-v1:'
entries = {entry.lyric_document_id: entry for entry in load_quarantine_entries()}
suspended = load_suspended_sources()
engine = create_engine(Settings.load(ROOT).database_url, connect_args={'connect_timeout': 10})
assert engine.url.host == '127.0.0.1' and engine.url.port == 56433

def flatten(payload, prefix=''):
    result = {}
    for key, value in payload.items():
        name = prefix + key
        if isinstance(value, dict):
            result.update(flatten(value, name + '.'))
        elif isinstance(value, int) and not isinstance(value, bool):
            result[name] = value
    return result

status = Counter()
sources = defaultdict(Counter)
versions = Counter()
integrity = Counter()
confidence = Counter()
intensities = defaultdict(Counter)
categoricals = defaultdict(Counter)
flags = Counter()
reasons = Counter()
errors = Counter()
valid_tracks = set()
sample_pools = defaultdict(list)
directed = defaultdict(list)
duplicate_groups = {}
bad_examples = []
report = {'started_utc': datetime.now(UTC).isoformat(), 'provider_calls': 0,
          'sampling_seed': SEED, 'sample_per_source': 12,
          'sample_interpretation': 'Diagnostic source-stratified sample; not population accuracy estimate'}
query = '''
WITH latest AS (
 SELECT DISTINCT ON (lyric_document_id,model_id,taxonomy_version,prompt_version)
  id,lyric_document_id,canonical_track_id,lyrics_hash,model_id,taxonomy_version,prompt_version,
  classification_status,result_json,confidence,error,input_tokens,output_tokens,estimated_cost_usd
 FROM lyric_classification_snapshots
 ORDER BY lyric_document_id,model_id,taxonomy_version,prompt_version,append_order DESC
)
SELECT d.id AS document_id,d.canonical_track_id AS document_track_id,d.content_sha256,
 d.source,d.rights_status,d.language_code,s.*
FROM lyric_documents d JOIN latest s ON s.lyric_document_id=d.id
'''
with engine.connect() as conn:
    conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
    conn.execute(text("SET LOCAL statement_timeout='120s'"))
    report['snapshot_utc'] = str(conn.execute(text('SELECT transaction_timestamp()')).scalar())
    report['table_counts'] = {name: conn.execute(text('SELECT count(*) FROM ' + name)).scalar()
                             for name in ('canonical_tracks', 'lyric_documents',
                                          'lyric_classification_snapshots', 'platform_item_track_links')}
    rows = conn.execution_options(stream_results=True).execute(text(query)).mappings()
    for row in rows:
        source = row['source']
        state = row['classification_status']
        status[state] += 1
        sources[source][state] += 1
        versions[(row['model_id'], row['taxonomy_version'], row['prompt_version'])] += 1
        integrity['missing_document_language'] += row['language_code'] is None
        document = SimpleNamespace(id=row['document_id'], canonical_track_id=row['document_track_id'],
            content_sha256=row['content_sha256'], source=source, rights_status=row['rights_status'])
        snapshot = SimpleNamespace(canonical_track_id=row['canonical_track_id'], lyrics_hash=row['lyrics_hash'],
            classification_status=state, result_json=row['result_json'])
        eligibility = assess_classification(document, snapshot,
            entries=(entries[document.id],) if document.id in entries else (), suspended_sources=suspended)
        reasons.update(eligibility.reasons)
        integrity['primary_eligible'] += eligibility.primary_eligible
        integrity['exploratory_eligible'] += eligibility.exploratory_eligible
        if state != 'classified':
            if state == 'error':
                errors[row['error'] or 'unspecified'] += 1
            continue
        valid_tracks.add(str(row['canonical_track_id']))
        try:
            result = LyricsClassification.model_validate(row['result_json'])
        except ValidationError as error:
            integrity['schema_invalid'] += 1
            if len(bad_examples) < 50:
                bad_examples.append({'snapshot_id': str(row['id']), 'errors': error.errors(include_input=False)})
            continue
        integrity['schema_valid'] += 1
        integrity['result_status_mismatch'] += result.classification_status.value != state
        integrity['snapshot_confidence_missing'] += row['confidence'] is None
        integrity['confidence_mismatch'] += row['confidence'] is not None and abs(row['confidence'] - result.confidence) > 1e-6
        integrity['classified_missing_usage'] += row['input_tokens'] is None or row['output_tokens'] is None
        integrity['classified_missing_cost'] += row['estimated_cost_usd'] is None
        band = '0.00-0.50' if result.confidence <= .5 else '0.51-0.79' if result.confidence < .8 else '0.80-0.94' if result.confidence < .95 else '0.95-1.00'
        confidence[band] += 1
        payload = result.model_dump(mode='json')
        values = flatten(payload)
        for name, value in values.items():
            intensities[name][value] += 1
        categoricals['consent'][payload['relationships']['consent']] += 1
        categoricals['target_gender'][payload['gender_representation']['target_gender']] += 1
        record_flags = []
        for topic, coding in payload['antisocial'].items():
            categoricals['stance.' + topic][coding['stance']] += 1
            if coding['intensity'] == 0 and coding['stance'] != 'neutral':
                record_flags.append('stance_without_intensity')
        if result.confidence <= .5:
            record_flags.append('classified_low_confidence')
        if not any(values.values()):
            record_flags.append('all_intensities_zero')
        if payload['relationships']['consent'] in ('coercive', 'nonconsensual'):
            record_flags.append('coercive_or_nonconsensual')
        if payload['gender_representation']['objectification'] >= 2 and payload['gender_representation']['target_gender'] == 'not_applicable':
            record_flags.append('objectification_without_target')
        for flag in set(record_flags):
            flags[flag] += 1
        record = {'document_id': str(row['document_id']), 'snapshot_id': str(row['id']),
                  'track_id': str(row['canonical_track_id']), 'source': source,
                  'confidence': result.confidence, 'intensities': values,
                  'consent': payload['relationships']['consent'],
                  'target_gender': payload['gender_representation']['target_gender'],
                  'stances': {k: v['stance'] for k,v in payload['antisocial'].items()},
                  'flags': sorted(set(record_flags)), 'exploratory_eligible': eligibility.exploratory_eligible}
        rank = int(hashlib.sha256((SEED + record['document_id']).encode()).hexdigest(), 16)
        pool = sample_pools[source]
        heapq.heappush(pool, (-rank, record))
        if len(pool) > 12:
            heapq.heappop(pool)
        for flag in set(record_flags) - {'all_intensities_zero'}:
            if len(directed[flag]) < 3:
                directed[flag].append(record)
        duplicate_key = (row['content_sha256'],row['model_id'],row['taxonomy_version'],row['prompt_version'])
        group = duplicate_groups.get(duplicate_key)
        vector = tuple(values.values())
        if group is None:
            duplicate_groups[duplicate_key] = {'count':1,'tracks':{str(row['canonical_track_id'])},'min':vector,'max':vector}
        else:
            group['count'] += 1
            group['tracks'].add(str(row['canonical_track_id']))
            group['min'] = tuple(min(a,b) for a,b in zip(group['min'],vector))
            group['max'] = tuple(max(a,b) for a,b in zip(group['max'],vector))
    rows.close()
    sample = [record for pool in sample_pools.values() for _,record in sorted(pool, reverse=True)]
    selected = {record['document_id']: record for record in sample}
    for records in directed.values():
        for record in records:
            selected.setdefault(record['document_id'], record)
    ids = [record['track_id'] for record in selected.values()]
    metadata = conn.execute(text('''SELECT t.id,t.title,string_agg(a.name, ', ' ORDER BY a.name) AS artists
        FROM canonical_tracks t LEFT JOIN track_artists ta ON ta.track_id=t.id
        LEFT JOIN artists a ON a.id=ta.artist_id WHERE t.id=ANY(CAST(:ids AS uuid[])) GROUP BY t.id,t.title'''), {'ids': ids}).mappings()
    lookup = {str(row['id']): {'title':row['title'],'artists':row['artists']} for row in metadata}
    for record in selected.values():
        record.update(lookup.get(record['track_id'], {}))
        record['sample_kind'] = 'source_stratified' if any(record['document_id']==r['document_id'] for r in sample) else 'directed_flag'
        record['human_review_status'] = 'not_reviewed'
engine.dispose()
shared = [group for group in duplicate_groups.values() if len(group['tracks']) > 1]
report.update(finished_utc=datetime.now(UTC).isoformat(), status_counts=dict(status),
    source_status_counts={key:dict(value) for key,value in sources.items()},
    version_counts=[{'model':k[0],'taxonomy':k[1],'prompt':k[2],'count':v} for k,v in versions.items()],
    classified_distinct_tracks=len(valid_tracks),integrity_counts=dict(integrity),exclusion_reasons=dict(reasons),
    schema_error_examples=bad_examples,confidence_counts=dict(confidence),
    intensity_distributions={k:dict(v) for k,v in intensities.items()},
    categorical_distributions={k:dict(v) for k,v in categoricals.items()},
    diagnostic_flags=dict(flags),error_counts=dict(errors),
    duplicate_text={'classified_groups_across_distinct_tracks':len(shared),
                    'classified_documents_in_groups':sum(g['count'] for g in shared),
                    'groups_with_any_score_difference':sum(g['min'] != g['max'] for g in shared),
                    'groups_with_difference_at_least_two':sum(any(b-a>=2 for a,b in zip(g['min'],g['max'])) for g in shared)},
    source_stratified_sample_count=len(sample),total_review_candidates=len(selected),
    human_accuracy_estimate=None,confidence_calibration=None,
    heuristic_flags_are_not_confirmed_errors=True)
(OUT/'audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
(OUT/'review-candidates.json').write_text(json.dumps(list(selected.values()),indent=2,ensure_ascii=False),encoding='utf-8')
with (OUT/'review-sheet.csv').open('w',encoding='utf-8',newline='') as handle:
    fields=['document_id','snapshot_id','source','title','artists','sample_kind','reviewer','identity_verdict','semantic_verdict','notes']
    writer=csv.DictWriter(handle,fieldnames=fields)
    writer.writeheader()
    for record in selected.values():
        writer.writerow({key:record.get(key,'') for key in fields})
print(json.dumps({key:report[key] for key in ('snapshot_utc','status_counts','source_status_counts','integrity_counts','confidence_counts','diagnostic_flags','duplicate_text','source_stratified_sample_count','total_review_candidates')},indent=2))
