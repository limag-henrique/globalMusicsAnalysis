"""Read-only aggregate text hygiene and exact-text disagreement diagnostics."""
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import create_engine, text
from chart_observatory.config import Settings

OUT = Path(__file__).parent
engine = create_engine(Settings.load(Path('D:/PromiscuidadeMusical')).database_url)
assert engine.url.host == '127.0.0.1' and engine.url.port == 56433

def flatten(value, prefix=''):
    result = {}
    for key, item in value.items():
        name = prefix + key
        if isinstance(item, dict):
            result.update(flatten(item, name + '.'))
        elif isinstance(item, int) and not isinstance(item, bool):
            result[name] = item
    return result

with engine.connect() as conn:
    conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
    stamp = str(conn.execute(text('SELECT transaction_timestamp()')).scalar())
    hygiene = list(conn.execute(text('''
        SELECT source,count(*) AS documents,
          count(*) FILTER (WHERE text LIKE '%Adicionar aos favoritos%' AND text LIKE '%Rolagem automática%') AS website_footer,
          count(*) FILTER (WHERE text ~ '&#[0-9]+;|&amp;|&quot;|&apos;|&lt;|&gt;') AS html_entity,
          count(*) FILTER (WHERE length(text)<300) AS text_under_300_chars,
          count(*) FILTER (WHERE text LIKE '[Verse 2]%' OR text LIKE '[Куплет 2]%' OR text LIKE '[Vers 2]%' OR text LIKE '[Ritornello 2]%') AS starts_at_second_section
        FROM lyric_documents GROUP BY source ORDER BY source
    ''')).mappings())
    (OUT/'content-contamination.json').write_text(json.dumps({'snapshot_utc':stamp,
        'method':'Literal footer signature and HTML-entity patterns; short/section flags are diagnostics, not completeness verdicts.',
        'sources':[dict(row) for row in hygiene]},indent=2,ensure_ascii=False),encoding='utf-8')
    groups = defaultdict(list)
    rows = conn.execution_options(stream_results=True).execute(text('''
        WITH latest AS (
          SELECT DISTINCT ON (lyric_document_id,model_id,taxonomy_version,prompt_version)
            id,lyric_document_id,model_id,taxonomy_version,prompt_version,classification_status,result_json
          FROM lyric_classification_snapshots
          ORDER BY lyric_document_id,model_id,taxonomy_version,prompt_version,append_order DESC
        ), shared AS (
          SELECT content_sha256 FROM lyric_documents GROUP BY content_sha256
          HAVING count(DISTINCT canonical_track_id)>1
        )
        SELECT d.id,d.canonical_track_id,d.content_sha256,d.source,s.id AS snapshot_id,
          s.model_id,s.taxonomy_version,s.prompt_version,s.result_json
        FROM lyric_documents d JOIN shared h USING(content_sha256)
        JOIN latest s ON s.lyric_document_id=d.id WHERE s.classification_status='classified'
    ''')).mappings()
    for row in rows:
        key=(row['content_sha256'],row['model_id'],row['taxonomy_version'],row['prompt_version'])
        groups[key].append({'document_id':str(row['id']),'track_id':str(row['canonical_track_id']),
            'snapshot_id':str(row['snapshot_id']),'source':row['source'],'scores':flatten(row['result_json'])})
    rows.close()
    severe=[]
    for key, records in groups.items():
        if len({r['track_id'] for r in records})<2:
            continue
        differences={name:{'minimum':min(r['scores'][name] for r in records),
                           'maximum':max(r['scores'][name] for r in records)}
                     for name in records[0]['scores']
                     if max(r['scores'][name] for r in records)-min(r['scores'][name] for r in records)>=2}
        if differences:
            severe.append({'content_sha256':key[0],'model':key[1],'taxonomy':key[2],
                           'prompt':key[3],'differences':differences,'records':records})
    ids=[r['track_id'] for group in severe for r in group['records']]
    if ids:
        metadata=conn.execute(text('''SELECT t.id,t.title,string_agg(a.name, ', ' ORDER BY a.name) AS artists
          FROM canonical_tracks t LEFT JOIN track_artists ta ON ta.track_id=t.id
          LEFT JOIN artists a ON a.id=ta.artist_id
          WHERE t.id=ANY(CAST(:ids AS uuid[])) GROUP BY t.id,t.title'''),{'ids':ids}).mappings()
        lookup={str(r['id']):{'title':r['title'],'artists':r['artists']} for r in metadata}
        for group in severe:
            for record in group['records']:
                record.update(lookup.get(record['track_id'],{}))
    (OUT/'duplicate-disagreements.json').write_text(json.dumps({'snapshot_utc':stamp,'groups':severe},indent=2,ensure_ascii=False),encoding='utf-8')
engine.dispose()
print(json.dumps({'hygiene':[dict(row) for row in hygiene],'severe_duplicate_groups':severe},ensure_ascii=False,indent=2))
