import importlib.util,json,sqlite3
from pathlib import Path

spec=importlib.util.spec_from_file_location('verifier_perf',Path(__file__).parents[2]/'scripts/verify_codex_import_stream.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

def test_refresh_skips_unchanged_inputs_and_reloads_audit_and_wal(tmp_path,monkeypatch):
 catalog=tmp_path/'catalog.sqlite'; audit=tmp_path/'audit.jsonl'; reservations=tmp_path/'reservations.json'
 writer=sqlite3.connect(catalog)
 writer.execute('pragma journal_mode=WAL')
 writer.executescript('create table songs(id text,payload text,result text); create table memberships(scope text,country text,period text,platform text,rank integer,song_id text);')
 writer.execute('insert into songs values (?,?,?)',('SPOTIFY:1',json.dumps({'title':'A','artist':'B'}),'{}'))
 writer.executemany('insert into memberships values (?,?,?,?,?,?)',[('annual','BR','2020','spotify',i,'SPOTIFY:1') for i in range(60)])
 writer.commit();audit.write_text(json.dumps({'candidate_id':'SPOTIFY:1','provider_supported':False})+'\n')
 conn=sqlite3.connect(':memory:');v.init_verifier_db(conn)
 refresh=v.SnapshotRefresh(catalog,audit,reservations)
 original=v.snapshot_catalog_and_audit; calls=[]
 def snapshot(*args,**kwargs):
  calls.append(1);return original(*args,**kwargs)
 monkeypatch.setattr(v,'snapshot_catalog_and_audit',snapshot)
 try:
  refresh.refresh(conn)
  assert len(json.loads(conn.execute('select memberships_json from candidate_snapshots').fetchone()[0]))==60
  refresh.refresh(conn);assert len(calls)==1
  audit.write_text(json.dumps({'candidate_id':'SPOTIFY:1','provider_supported':True})+'\n')
  refresh.refresh(conn);assert len(calls)==2
  assert refresh.strict_map['SPOTIFY:1']['provider_supported'] is True
  writer.execute('update songs set payload=?',(json.dumps({'title':'Changed'}),));writer.commit()
  refresh.refresh(conn);assert len(calls)==3
  assert conn.execute('select title from candidate_snapshots').fetchone()[0]=='Changed'
  reservations.write_text('{}');refresh.refresh(conn);assert len(calls)==4
 finally:
  refresh.close();writer.close();conn.close()
