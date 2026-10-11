"""Private local inspection only: never export lyric bodies into review artifacts."""
import hashlib
import json
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from chart_observatory.config import Settings

directory=Path(__file__).parent
sys.stdout.reconfigure(encoding='utf-8')
samples=json.loads((directory/'selected-for-initial-review.json').read_text(encoding='utf-8'))
engine=create_engine(Settings.load(Path('D:/PromiscuidadeMusical')).database_url)
with engine.connect() as connection:
    connection.execute(text('SET TRANSACTION READ ONLY'))
    rows=connection.execute(text('SELECT id,text,content_sha256 FROM lyric_documents WHERE id=ANY(CAST(:ids AS uuid[]))'),{'ids':[r['document_id'] for r in samples]}).mappings()
    documents={str(row['id']):dict(row) for row in rows}
checks={key:hashlib.sha256((row['text'] or '').encode('utf-8')).hexdigest()==row['content_sha256'] for key,row in documents.items()}
(directory/'sample-content-hash-check.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
for index in range(int(sys.argv[1]),min(int(sys.argv[2]),len(samples))):
    record=samples[index]
    lyric=documents[record['document_id']]['text'] or ''
    print(json.dumps({'index':index,'document_id':record['document_id'],'title':record['title'],'artist':record['artists'],'source':record['source'],
        'confidence':record['confidence'],'nonzero_intensities':{k:v for k,v in record['intensities'].items() if v},
        'stances':record['stances'],'consent':record['consent'],'target_gender':record['target_gender'],
        'flags':record['flags'],'text_chars':len(lyric),'truncated':len(lyric)>10000,'text':lyric[:10000]},ensure_ascii=False))
engine.dispose()
