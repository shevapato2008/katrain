"""Capture fresh global and unchanged member context after applied batch 589 using pinned r2."""
import gzip,importlib.util,json,shlex,subprocess
from pathlib import Path
D=Path(__file__).parent
S=importlib.util.spec_from_file_location('member_capture',D/'capture-current-preimages.py')
M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
M.D=D/'post589';M.D.mkdir(exist_ok=True)
M.HOSTS={
 'PROD':('ucloud-v100','katrain-ucloud-katrain-web-1','sha256:b1966627c63c7f7004c7de84a8e278c3f975c57554093c677d38b1c4ec7a8590'),
 'TEST':('home-ubuntu','katrain-web','sha256:cee5c76bf9dc5bd07a70d324e84da78090bf7926feafc9cfb0c8e934fc4a1aa8')}
REMOTE=r'''
import datetime,gzip,hashlib,json,os,sys
from pathlib import Path
from sqlalchemy import create_engine,select
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.kifu.name_batch import catalog_snapshot_sha,approved_name_snapshot,orthographic_alias_snapshot
from katrain.web.core.models_db import KifuNameSourceRegistry,KifuNameBatch
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'],connect_args={'options':'-c default_transaction_read_only=on'})
inventory=build_inventory(engine)
catalog=catalog_snapshot_sha(engine)
approved=approved_name_snapshot(engine)
with engine.connect() as conn:
 conn.exec_driver_sql('SET TRANSACTION READ ONLY')
 aliases=orthographic_alias_snapshot(conn)
 registry=dict(conn.execute(select(KifuNameSourceRegistry.__table__).order_by(KifuNameSourceRegistry.id.desc()).limit(1)).mappings().one())
 batch=dict(conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id==589)).mappings().one())
 assert batch['status']=='applied'
 conn.rollback()
files=['identity.py','name_candidates.py','name_evidence.py','name_orthographic.py','name_batch.py','name_inventory.py']
code={f:hashlib.sha256(Path('/app/katrain/web/kifu',f).read_bytes()).hexdigest()for f in files}
data={'environment':ENV,'image_id':IMAGE,'read_only':True,'inventory':inventory,'catalog_sha256':catalog,
 'approved_name_snapshot':approved,'known_aliases':aliases,'source_registry':registry,
 'actual_preceding_batch':{'id':batch['id'],'status':batch['status'],'bundle_sha256':batch['bundle_sha256'],'applied_at':batch['applied_at']},
 'context_refreshed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'actual_r2_code_sha256':code}
sys.stdout.buffer.write(gzip.compress(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=lambda value:value.isoformat()).encode(),mtime=0))
engine.dispose()
'''
def global_capture(env):
 host,container,image=M.HOSTS[env]
 program='ENV='+repr(env)+'\nIMAGE='+repr(image)+'\n'+REMOTE
 command=(f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'
  ' | grep "^KATRAIN_DATABASE_URL="'
  f' | docker run --rm --read-only -i --env-file /dev/stdin --network container:{container} --entrypoint python {image} -c {shlex.quote(program)}')
 result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',host,command],capture_output=True)
 if result.returncode:
  import re
  raise RuntimeError(env+': '+re.sub(r'\w+://\S+','[redacted URL]',result.stderr.decode(errors='replace')[-1800:]))
 data=json.loads(gzip.decompress(result.stdout));assert data['actual_preceding_batch']['status']=='applied'
 (D/f'{env}-post589-global-context.json.gz').write_bytes(result.stdout)
 print(env,'actual batch589 applied; fresh global inventory/catalog',data['context_refreshed_at'],'qualified',len(data['approved_name_snapshot']),flush=True)
if __name__=='__main__':
 summary=json.loads((D/'positive-ko20-summary.json').read_text());freq=json.loads((D/'old-ko28-frequency-readonly.json').read_text())
 targets=[{'prod_id':r['prod_id'],'canonical_name':next(f['canonical_name']for f in freq if f['id']==r['prod_id']),'display_name':r['name']}for r in summary['records']]
 for env in M.HOSTS:
  global_capture(env);M.capture(env,targets)
  old=json.load(gzip.open(D/f'{env}-ko20-current-preimages.json.gz','rt'));new=json.load(gzip.open(M.D/f'{env}-ko20-current-preimages.json.gz','rt'))
  for before,after in zip(old['rows'],new['rows']):
   for key in ['id','prod_id','owner_preimage','target_name_preimage','target_evidence_preimage','linked_album_members']:
    assert before[key]==after[key],(env,before['id'],key)
  print(env,'all20 member owner/name/evidence/SGF scope unchanged after589',flush=True)
