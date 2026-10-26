"""Explicit 004 migration. No application startup; no fake public business rows."""
import argparse, hashlib, json, os, pathlib, re, subprocess, sys
TABLES=['kifu_player_rank_history','kifu_album_rank_snapshots']
MIGRATION='katrain/cron/migrations/004_kifu_player_ranks.sql'
ROOT=pathlib.Path(__file__).resolve().parent if '__file__' in globals() else None
# Canonical PostgreSQL forms of the unchanged published 004 checks; no TEMP DDL is
# needed to verify them. The readonly path is pinned to that exact migration hash.
MIGRATION_004_SHA256='77c1b870add4e4dc860272e892f5f10d5ac787ee0151e7592f10c7fad03c9b22'
CHECKS_004={
 'ck_kifu_player_rank_sha256':"CHECK (content_sha256::text ~ '^[0-9a-f]{64}$'::text)",
 'ck_kifu_player_rank_status':"CHECK (status::text = ANY (ARRAY['qualified'::character varying, 'conflict'::character varying]::text[]))",
 'ck_kifu_player_rank_system':"CHECK (rank_system::text = ANY (ARRAY['professional_dan'::character varying, 'amateur_dan'::character varying, 'kyu'::character varying, 'dan_unspecified'::character varying]::text[]))",
 'ck_kifu_player_rank_value':"CHECK (rank_value >= 1 AND (rank_system::text = 'kyu'::text AND rank_value <= 30 OR rank_system::text <> 'kyu'::text AND rank_value <= 9))",
 'ck_kifu_album_rank_sha256':"CHECK (snapshot_sha256::text ~ '^[0-9a-f]{64}$'::text)",
 'ck_kifu_album_rank_side':"CHECK (side::text = ANY (ARRAY['black'::character varying, 'white'::character varying]::text[]))",
}
def fail(code): raise RuntimeError(code)
def sha(b): return hashlib.sha256(b).hexdigest()
def db_connect(kind='web'):
 import logging
 logging.disable(logging.CRITICAL)
 from sqlalchemy import create_engine
 from sqlalchemy.pool import NullPool
 if kind=='cron':
  from katrain.cron.config import DATABASE_URL
 else:
  from katrain.web.core.config import settings
  DATABASE_URL=settings.DATABASE_URL
 engine=create_engine(DATABASE_URL,echo=False,poolclass=NullPool)
 if engine.dialect.name!='postgresql': fail('postgresql_required')
 return engine.raw_connection()
def role(kind):
 c=db_connect(kind)
 try:
  q=c.cursor(); q.execute('SET TRANSACTION READ ONLY'); q.execute("SET LOCAL statement_timeout='8s'")
  q.execute('SELECT current_user,current_database(),inet_server_addr()::text,inet_server_port()')
  name,database,address,port=q.fetchone()
  return {'role':name,'role_sha256':sha(name.encode()),
          'database_target_sha256':sha(json.dumps([database,address,port]).encode())}
 finally: c.rollback(); c.close()
def inspect_table(q,name,schema):
 q.execute('SELECT to_regclass(%s)::oid',(schema+'.'+name,)); oid=q.fetchone()[0]
 if oid is None: return None
 q.execute("SELECT a.attname,format_type(a.atttypid,a.atttypmod),NOT a.attnotnull,pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum",(oid,))
 columns={n:{'type':t,'nullable':nullable,'default':('sequence_nextval' if default and default.startswith('nextval(') else default)} for n,t,nullable,default in q.fetchall()}
 q.execute("SELECT c.conname,c.contype,ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY x(num,ord) JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=x.num ORDER BY x.ord),r.relname,ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY x(num,ord) JOIN pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=x.num ORDER BY x.ord),c.confdeltype,pg_get_constraintdef(c.oid,true) FROM pg_constraint c LEFT JOIN pg_class r ON r.oid=c.confrelid WHERE c.conrelid=%s ORDER BY c.conname",(oid,))
 constraints={n:({'kind':kind,'columns':cols,'definition':definition} if kind=='c' else
                 {'kind':kind,'columns':cols,'target_table':target,'target_columns':targetcols,'ondelete':delete} if kind=='f' else
                 {'kind':kind,'columns':cols}) for n,kind,cols,target,targetcols,delete,definition in q.fetchall()}
 q.execute("SELECT c.relname,i.indisunique,i.indisprimary,i.indisvalid,i.indisready,ARRAY(SELECT a.attname FROM unnest(i.indkey::smallint[]) WITH ORDINALITY x(num,ord) LEFT JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=x.num ORDER BY x.ord),pg_get_expr(i.indpred,i.indrelid) FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE i.indrelid=%s ORDER BY c.relname",(oid,))
 indexes={n:{'unique':unique,'primary':primary,'valid':valid,'ready':ready,'columns':cols,'predicate':predicate}
          for n,unique,primary,valid,ready,cols,predicate in q.fetchall()}
 return {'columns':columns,'constraints':constraints,'indexes':indexes}
def model_check(actual,model):
 types={'Integer':'integer','String':'character varying','Date':'date','DateTime':'timestamp','JSON':'json','Boolean':'boolean'}
 if set(actual['columns'])!=set(model['columns']): fail('model_column_set_mismatch')
 for name,c in model['columns'].items():
  t=types[c['kind']]
  if c['kind']=='String': t+='('+str(c['length'])+')'
  if c['kind']=='DateTime': t+=' with time zone' if c['timezone'] else ' without time zone'
  if actual['columns'][name]['type']!=t or actual['columns'][name]['nullable']!=c['nullable']: fail('model_column_type_or_nullable_mismatch')
 pk=[x['columns'] for x in actual['constraints'].values() if x['kind']=='p']
 if pk!=[[n for n,c in model['columns'].items() if c['primary_key']]]: fail('model_primary_key_mismatch')
 if actual['columns']['id']['default']!='sequence_nextval': fail('serial_default_missing')
 fk=sorted([{'columns':x['columns'],'target_table':x['target_table'],'target_columns':x['target_columns'],
             'ondelete':{'a':'NO ACTION','r':'RESTRICT'}.get(x['ondelete'],x['ondelete'])}
            for x in actual['constraints'].values() if x['kind']=='f'],key=lambda x:x['columns'])
 if fk!=model['foreign_keys']: fail('model_foreign_key_mismatch')
 unique=sorted([x['columns'] for x in actual['constraints'].values() if x['kind']=='u'])
 if unique!=model['unique_columns']: fail('model_unique_mismatch')
 checks=sorted(n for n,x in actual['constraints'].items() if x['kind']=='c')
 if checks!=model['check_names']: fail('model_check_set_mismatch')
 for name,x in model['indexes'].items():
  a=actual['indexes'].get(name)
  if not a or not a['valid'] or not a['ready'] or a['columns']!=x['columns'] or a['unique']!=x['unique'] or a['predicate']!=x['predicate']: fail('model_index_mismatch')
def negative(q,sql,params,state):
 q.execute('SAVEPOINT rank_negative')
 try:
  q.execute(sql,params)
 except Exception as exc:
  q.execute('ROLLBACK TO SAVEPOINT rank_negative'); q.execute('RELEASE SAVEPOINT rank_negative')
  if getattr(exc,'pgcode',None)!=state: fail('temporary_rehearsal_wrong_error')
  return
 q.execute('ROLLBACK TO SAVEPOINT rank_negative'); q.execute('RELEASE SAVEPOINT rank_negative')
 fail('temporary_rehearsal_constraint_not_enforced')
def rehearsal(sql,models):
 c=db_connect()
 try:
  q=c.cursor(); q.execute("SET statement_timeout='8s'"); q.execute("SET lock_timeout='3s'")
  # All fake parents and child records live in this connection's temporary namespace.
  q.execute('CREATE TEMPORARY TABLE kifu_players(id integer PRIMARY KEY)')
  q.execute('CREATE TEMPORARY TABLE kifu_albums(id integer PRIMARY KEY)')
  if sql.count('CREATE TABLE IF NOT EXISTS ')!=2: fail('unexpected_migration_shape')
  q.execute(sql.replace('CREATE TABLE IF NOT EXISTS ','CREATE TEMPORARY TABLE IF NOT EXISTS '))
  q.execute('BEGIN')  # The published SQL explicitly commits; SAVEPOINT probes need a new transaction.
  expected={n:inspect_table(q,n,'pg_temp') for n in TABLES}
  for n in TABLES: model_check(expected[n],models[n])
  q.execute('INSERT INTO pg_temp.kifu_players VALUES(1)'); q.execute('INSERT INTO pg_temp.kifu_albums VALUES(1)')
  insert="INSERT INTO pg_temp.kifu_player_rank_history(player_id,rank_value,rank_system,observed_at,source_kind,source_ref,evidence,content_sha256,status,is_current) VALUES(1,%s,%s,now(),'release_rehearsal','{}','{}',%s,%s,%s) RETURNING id"
  q.execute(insert,(9,'professional_dan','a'*64,'qualified',True)); fact=q.fetchone()[0]
  # The partial unique predicate also covers current rows whose status is conflict.
  negative(q,insert,(8,'professional_dan','b'*64,'conflict',True),'23505')
  negative(q,insert,(9,'professional_dan','a'*64,'qualified',False),'23505')
  for rank,system in [(0,'professional_dan'),(10,'professional_dan'),(31,'kyu'),(1,'invalid')]:
   negative(q,insert,(rank,system,'c'*64,'qualified',False),'23514')
  negative(q,insert,(1,'kyu','d'*64,'invalid',False),'23514')
  negative(q,insert,(1,'kyu','A'*64,'qualified',False),'23514')
  q.execute(insert,(30,'kyu','e'*64,'qualified',False)); q.fetchone()
  snapshot="INSERT INTO pg_temp.kifu_album_rank_snapshots(album_id,side,rank_fact_id,snapshot,snapshot_sha256,publication_key,native_batch_id) VALUES(1,%s,%s,'{}',%s,'release-rehearsal',1)"
  q.execute(snapshot,('black',fact,'f'*64))
  negative(q,snapshot,('black',fact,'f'*64),'23505')
  negative(q,snapshot,('other',fact,'f'*64),'23514')
  negative(q,snapshot,('white',fact,'F'*64),'23514')
  negative(q,'DELETE FROM pg_temp.kifu_player_rank_history WHERE id=%s',(fact,),'23503')
  c.rollback()
  return expected
 finally: c.close()  # closes and drops every temporary table/sequence, even after the SQL's COMMIT
def migrate(payload):
 sql=payload['sql']; models=payload['models']
 if sha(sql.encode())!=payload['migration_sha256']: fail('migration_payload_hash_mismatch')
 expected=rehearsal(sql,models)
 c=db_connect()
 try:
  q=c.cursor(); q.execute("SET search_path TO public"); q.execute("SET statement_timeout='8s'"); q.execute("SET lock_timeout='3s'")
  before={n:inspect_table(q,n,'public') for n in TABLES}
  for n in TABLES:
   if before[n] is not None and before[n]!=expected[n]: fail('existing_public_schema_mismatch')
  # No DROP/ALTER/GRANT or data import. The exact unmodified published 004 file owns DDL.
  q.execute(sql)
  after={n:inspect_table(q,n,'public') for n in TABLES}
  if after!=expected: fail('post_migration_schema_mismatch')
  counts={}
  for n in TABLES:
   model_check(after[n],models[n]); q.execute('SELECT count(*) FROM public.'+n); counts[n]=q.fetchone()[0]
   if before[n] is None and counts[n]!=0: fail('unexpected_new_rank_rows')
  c.rollback()
  return {'phase':'schema_verified','migration_sha256':payload['migration_sha256'],
          'temporary_pg_rehearsal':'passed','fake_public_business_rows':0,'schema':after,
          'tables_preexisting':{n:before[n] is not None for n in TABLES},'row_counts':counts}
 finally: c.close()
def verify_existing_readonly(payload):
 if payload['migration_sha256']!=MIGRATION_004_SHA256: fail('readonly_verification_requires_unchanged_004')
 c=db_connect()
 try:
  q=c.cursor(); q.execute('SET TRANSACTION READ ONLY'); q.execute("SET LOCAL statement_timeout='8s'")
  q.execute('SHOW transaction_read_only')
  if q.fetchone()[0]!='on': fail('readonly_transaction_not_enabled')
  actual={n:inspect_table(q,n,'public') for n in TABLES}; counts={}
  for n in TABLES:
   if actual[n] is None: fail('existing_rank_table_missing')
   model_check(actual[n],payload['models'][n])
   for name,x in actual[n]['constraints'].items():
    if x['kind']=='c' and ' '.join(x['definition'].split())!=' '.join(CHECKS_004[name].split()): fail('existing_rank_check_definition_mismatch')
   q.execute('SELECT count(*) FROM public.'+n); counts[n]=q.fetchone()[0]
  c.rollback()
  return {'phase':'schema_verified','verification_mode':'existing-readonly','transaction_read_only':True,
          'migration_sha256':payload['migration_sha256'],'schema':actual,'row_counts':counts,
          'tables_preexisting':{n:True for n in TABLES},'ddl_executed':False,'temp_objects_created':False,
          'grants_executed':False,'business_writes':False}
 finally: c.close()
def run_private(container,mode,payload=None):
 p=subprocess.run(['docker','exec','-i',container,'python3','-c',(ROOT/'schema_rank.py').read_text(),mode],
                  input=json.dumps(payload or {}),text=True,capture_output=True,timeout=100)
 if p.returncode:
  try: code=json.loads(p.stdout).get('error_code')
  except Exception: code=None
  fail(code if code and re.fullmatch('[A-Za-z0-9_]+',code) else 'private_schema_command_failed')
 return json.loads(p.stdout)
def save(path,value):
 pathlib.Path(path).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n'); os.chmod(path,0o600)
def main():
 if len(sys.argv)>1 and sys.argv[1] in {'db-role-web','db-role-cron','db-migrate','db-verify-existing-readonly'}:
  mode=sys.argv[1]
  value=verify_existing_readonly(json.loads(sys.stdin.read())) if mode=='db-verify-existing-readonly' else migrate(json.loads(sys.stdin.read())) if mode=='db-migrate' else role(mode.removeprefix('db-role-'))
  print(json.dumps(value,sort_keys=True)); return
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--host',choices=['home-ubuntu','ucloud-v100'],required=True)
 for key in ['sha','web-container','migration','candidate','receipt']: p.add_argument('--'+key,required=True)
 p.add_argument('--go'); p.add_argument('--verify-existing-readonly',action='store_true')
 p.add_argument('--cron-container'); p.add_argument('--roles-only',action='store_true')
 a=p.parse_args()
 if not re.fullmatch('[0-9a-f]{40}',a.sha): fail('full_source_sha_required')
 if not (a.roles_only or a.verify_existing_readonly) and a.go!='APPROVED:'+a.sha: fail('exact_controller_go_required')
 built=json.loads(pathlib.Path(a.candidate).read_text())
 if built.get('phase')!='candidate_verified' or built.get('kind')!='web' or built.get('host')!=a.host or built.get('source_develop_sha')!=a.sha: fail('built_receiver_candidate_required')
 migration=pathlib.Path(a.migration).read_bytes(); migration_sha=sha(migration)
 if built['runtime']['source_files'][MIGRATION]!=migration_sha: fail('candidate_migration_hash_mismatch')
 web=run_private(a.web_container,'db-role-web')
 receipt={'host':a.host,'source_develop_sha':a.sha,'phase':'roles_checked','web_role_sha256':web['role_sha256']}
 if a.host=='home-ubuntu':
  if not a.cron_container: fail('test_current_cron_role_required')
  cron=run_private(a.cron_container,'db-role-cron')
  receipt.update({'cron_role_sha256':cron['role_sha256'],'same_web_cron_role':web['role_sha256']==cron['role_sha256'],
                  'same_database_target':web['database_target_sha256']==cron['database_target_sha256']})
  if not receipt['same_database_target']: fail('test_web_cron_database_target_mismatch')
  if not receipt['same_web_cron_role']:
   if a.verify_existing_readonly:
    receipt.update({'phase':'role_difference_requires_controller','schema_mutated':False,'grants_executed':False})
    save(a.receipt,receipt); print(json.dumps(receipt)); sys.exit(3)
   # Concrete proposal only, never executed. No public/default privileges or unrelated tables.
   identifier='"'+cron['role'].replace('"','""')+'"'
   proposal=pathlib.Path(a.receipt).with_suffix('.proposed-grants.sql')
   proposal.write_text('BEGIN;\nGRANT SELECT, INSERT, UPDATE ON TABLE public.kifu_player_rank_history, public.kifu_album_rank_snapshots TO '+identifier+';\nGRANT USAGE ON SEQUENCE public.kifu_player_rank_history_id_seq, public.kifu_album_rank_snapshots_id_seq TO '+identifier+';\nCOMMIT;\n'); os.chmod(proposal,0o600)
   receipt.update({'phase':'role_difference_requires_controller','proposed_narrow_grants':str(proposal),'schema_mutated':False})
   save(a.receipt,receipt); print(json.dumps(receipt)); sys.exit(3)
 if a.roles_only: save(a.receipt,receipt); print(json.dumps(receipt)); return
 try:
  mode='db-verify-existing-readonly' if a.verify_existing_readonly else 'db-migrate'
  payload={'migration_sha256':migration_sha,'models':built['runtime']['rank_models']}
  if not a.verify_existing_readonly: payload['sql']=migration.decode()
  result=run_private(a.web_container,mode,payload)
 except Exception as exc:
  receipt.update({'phase':'schema_failed','migration_sha256':migration_sha,
                  'public_schema_may_have_committed':not a.verify_existing_readonly,'error_type':type(exc).__name__,
                  'error_code':str(exc) if re.fullmatch('[A-Za-z0-9_]+',str(exc)) else 'details_redacted'})
  save(a.receipt,receipt); raise
 receipt.update(result); save(a.receipt,receipt)
 print(json.dumps({'phase':receipt['phase'],'receipt':a.receipt,'migration_sha256':migration_sha,
                   'same_web_cron_role':receipt.get('same_web_cron_role'),'row_counts':receipt['row_counts']}))
if __name__=='__main__':
 try: main()
 except Exception as exc:
  print(json.dumps({'phase':'refused','error_type':type(exc).__name__,
                    'error_code':str(exc) if re.fullmatch('[A-Za-z0-9_]+',str(exc)) else 'details_redacted'})); sys.exit(1)
