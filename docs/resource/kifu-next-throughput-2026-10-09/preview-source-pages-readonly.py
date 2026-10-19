"""Run existing source-page synchronization preview after the actual KO batch applies."""
import gzip,importlib.util,json,shlex,subprocess
from pathlib import Path
D=Path(__file__).parent
spec=importlib.util.spec_from_file_location('context_capture',D/'capture-post589-context.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
REMOTE=r'''
import gzip,json,os,sys
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from katrain.web.core.models_db import KifuPlayerName,KifuNameResearchEvidence
from katrain.web.kifu.identity import _approved_names,_qualified_name_rows
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.player_pages import sync_player_pages
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'],connect_args={'options':'-c default_transaction_read_only=on'})
with engine.connect() as conn:
 conn.exec_driver_sql('SET TRANSACTION READ ONLY')
 with Session(bind=conn)as session:
  query=_approved_names(session,KifuPlayerName,'player_id').filter(KifuPlayerName.player_id.in_(IDS),KifuPlayerName.lang=='ko')
  rows=_qualified_name_rows(session,query,KifuPlayerName,'player_id')
  assert len(rows)==20,'All20 strict KO proofs must qualify after actual apply before page preview'
  for name,evidence in rows:
   proof=evidence.research_payload.get('normative_ja_ko')
   assert proof and proof['research_sha256']==RESEARCH_BY_ID[name.player_id]
   assert name.display_name==NAMES_BY_ID[name.player_id]
 conn.rollback()
report=sync_player_pages(engine,player_ids=IDS,apply=False)
assert report['committed']is False
sys.stdout.buffer.write(gzip.compress(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(),mtime=0))
engine.dispose()
'''
def preview(env):
 research=json.load(gzip.open(D/f'{env}-ko20-unsigned-research.json.gz','rt'))
 from katrain.web.kifu.name_candidates import canonical_sha256
 ids=[r['owner']['id']for r in research]
 hashes={r['owner']['id']:canonical_sha256(r)for r in research}
 names={r['owner']['id']:r['candidate_name']for r in research}
 host,container,image=module.M.HOSTS[env]
 program='IDS='+repr(ids)+'\nRESEARCH_BY_ID='+repr(hashes)+'\nNAMES_BY_ID='+repr(names)+'\n'+REMOTE
 command=(f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'
  ' | grep "^KATRAIN_DATABASE_URL="'
  f' | docker run --rm --read-only -i --env-file /dev/stdin --network container:{container} --entrypoint python {image} -c {shlex.quote(program)}')
 result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',host,command],capture_output=True)
 if result.returncode:
  import re
  raise RuntimeError(env+': '+re.sub(r'\w+://\S+','[redacted URL]',result.stderr.decode(errors='replace')[-1200:]))
 report=json.loads(gzip.decompress(result.stdout));(D/f'{env}-source-pages-preview-readonly.json.gz').write_bytes(result.stdout)
 print(env,'existing page preview read only:',report['players_scanned'],'players',report['pages_added'],'pages proposed',report['players_changed'],'player rows',flush=True)
if __name__=='__main__':
 import sys
 for env in (sys.argv[1:]or['PROD','TEST']):preview(env)
