"""Capture current repair targets and immutable linked game facts; no SQL writes."""
import gzip,json,shlex,subprocess
from pathlib import Path
D=Path(__file__).parent
HOSTS={
 'PROD':('ucloud-v100','katrain-ucloud-katrain-web-1','sha256:16ff2a118049c852d674800d9b0c8e4a676a68e10aca8d8baf67f30f64cd0a0c'),
 'TEST':('home-ubuntu','katrain-web','sha256:52907d65efc9e59b8b546d2e335d5d45729aa0eed1c5e1480be7f4cbe0d28259')}
REMOTE=r'''
import datetime,gzip,hashlib,json,os,sys
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from katrain.web.core.models_db import KifuPlayer,KifuPlayerName,KifuNameResearchEvidence,KifuNameBatch,KifuNameChange
from katrain.web.kifu.name_batch import _image
from katrain.web.kifu.identity import _approved_names,_qualified_name_rows
from katrain.web.kifu.name_evidence import registry_sha256
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'],connect_args={'options':'-c default_transaction_read_only=on'})
rows=[]
with engine.connect() as conn:
 conn.exec_driver_sql('SET TRANSACTION READ ONLY')
 conn.exec_driver_sql("SET LOCAL statement_timeout='45s'")
 players=conn.execute(select(KifuPlayer.__table__).where(KifuPlayer.canonical_name.in_([r['canonical_name']for r in TARGETS]))).mappings().all()
 assert len(players)==len(TARGETS)==20
 ids=[r['id']for r in players]
 with Session(bind=conn)as session:
  qualified=_qualified_name_rows(session,_approved_names(session,KifuPlayerName,'player_id').filter(KifuPlayerName.player_id.in_(ids)),KifuPlayerName,'player_id')
  qualified_by_owner={i:set()for i in ids}
  for n,e in qualified: qualified_by_owner[n.player_id].add(n.lang)
 for target in TARGETS:
  p=next(p for p in players if p['canonical_name']==target['canonical_name'])
  pid=p['id']; assert {'cn','tw','jp','en'}<=qualified_by_owner[pid] and 'ko'not in qualified_by_owner[pid]
  names=conn.execute(select(KifuPlayerName.__table__).where(KifuPlayerName.player_id==pid,KifuPlayerName.lang.in_(['cn','tw','jp','ko','en']))).mappings().all()
  n=next(n for n in names if n['lang']=='ko'); assert n['display_name']==target['display_name'] and n['status']=='verified' and n['decision_kind']=='generated'
  evidence=_image(conn,KifuNameResearchEvidence.__table__,n['evidence_id'])
  assert evidence['review_status']=='approved' and 'normative_ja_ko'not in evidence['research_payload']
  name=_image(conn,KifuPlayerName.__table__,n['id'])
  journal=conn.execute(select(KifuNameChange.__table__).where(((KifuNameChange.target_table=='kifu_player_names')&(KifuNameChange.target_row_id==n['id']))|((KifuNameChange.target_table=='kifu_name_research_evidence')&(KifuNameChange.target_row_id==n['evidence_id']))).order_by(KifuNameChange.id)).mappings().all()
  batchids=sorted({j['batch_id']for j in journal})
  batches=conn.execute(select(KifuNameBatch.id,KifuNameBatch.status,KifuNameBatch.bundle_sha256,KifuNameBatch.applied_at).where(KifuNameBatch.id.in_(batchids))).mappings().all()
  assert any(j['target_table']=='kifu_name_research_evidence'and j['before_image']is None for j in journal)
  games=[dict(g)for g in conn.execute(text('SELECT id,black_player_id,white_player_id,date_played,player_black,player_white,black_rank,white_rank,result,sgf_content FROM kifu_albums WHERE black_player_id=:id OR white_player_id=:id ORDER BY id'),{'id':pid}).mappings()]
  for g in games:
   g['sgf_utf8_sha256']=hashlib.sha256(g.pop('sgf_content').encode()).hexdigest();g['side']='black'if g['black_player_id']==pid else'white'
  rows.append({'prod_id':target['prod_id'],'id':pid,'canonical_name':p['canonical_name'],'owner_preimage':dict(p),
   'target_name_preimage':name,'target_evidence_preimage':evidence,'target_name_preimage_sha256':registry_sha256(name),
   'target_evidence_preimage_sha256':registry_sha256(evidence),'original_creation_journal':[dict(j)for j in journal],
   'original_batches':[dict(b)for b in batches],'current_other_four_qualified':True,'current_ko_strictly_unqualified':True,
   'current_primary_names':[dict(n)for n in names],'linked_album_members':games,'game_slots':len(games)})
 conn.rollback()
result={'environment':ENV,'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image_id':IMAGE,
 'read_only':True,'rows':rows,'game_slots':sum(r['game_slots']for r in rows),'unique_albums':len({g['id']for r in rows for g in r['linked_album_members']})}
sys.stdout.buffer.write(gzip.compress(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=lambda x:x.isoformat()if isinstance(x,datetime.datetime)else str(x)).encode(),mtime=0))
engine.dispose()
'''
def capture(env,targets):
 host,container,image=HOSTS[env]
 program='TARGETS='+repr(targets)+'\nENV='+repr(env)+'\nIMAGE='+repr(image)+'\n'+REMOTE
 command=(f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'
  ' | grep "^KATRAIN_DATABASE_URL="'
  f' | docker run --rm --read-only -i --env-file /dev/stdin --network container:{container} --entrypoint python {image} -c {shlex.quote(program)}')
 proc=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',host,command],capture_output=True)
 if proc.returncode:
  import re
  raise RuntimeError(env+': '+re.sub(r'\w+://\S+','[redacted URL]',proc.stderr.decode(errors='replace')[-1800:]))
 data=json.loads(gzip.decompress(proc.stdout));assert len(data['rows'])==20
 (D/f'{env}-ko20-current-preimages.json.gz').write_bytes(proc.stdout)
 print(env,len(data['rows']),data['game_slots'],'slots',data['unique_albums'],'albums; current KO proof gap and four other languages confirmed',flush=True)
if __name__=='__main__':
 summary=json.loads((D/'positive-ko20-summary.json').read_text())
 frequencies=json.loads((D/'old-ko28-frequency-readonly.json').read_text())
 targets=[{'prod_id':r['prod_id'],'canonical_name':next(f['canonical_name']for f in frequencies if f['id']==r['prod_id']),'display_name':r['name']}for r in summary['records']]
 for env in HOSTS: capture(env,targets)
