"""Capture selected TW source rows and physical targets using r2, read only."""
import gzip,json,shlex,subprocess
from pathlib import Path
D=Path(__file__).parent
HOSTS={'PROD':('ucloud-v100','katrain-ucloud-katrain-web-1','sha256:b1966627c63c7f7004c7de84a8e278c3f975c57554093c677d38b1c4ec7a8590'),'TEST':('home-ubuntu','katrain-web','sha256:cee5c76bf9dc5bd07a70d324e84da78090bf7926feafc9cfb0c8e934fc4a1aa8')}
REMOTE=r'''
import datetime,gzip,hashlib,json,os,sys
from pathlib import Path
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from katrain.web.core.models_db import KifuPlayer,KifuPlayerName,KifuNameResearchEvidence,KifuNameBatch,KifuNameChange
from katrain.web.kifu.name_batch import _image
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_orthographic import verified_source_live
from katrain.web.kifu.identity import _approved_names,_qualified_name_rows
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'],connect_args={'options':'-c default_transaction_read_only=on'})
rows=[]
with engine.connect() as conn:
 conn.exec_driver_sql('SET TRANSACTION READ ONLY')
 conn.exec_driver_sql("SET LOCAL statement_timeout='45s'")
 players=conn.execute(select(KifuPlayer.__table__).where(KifuPlayer.canonical_name.in_([r['canonical_name']for r in TARGETS]))).mappings().all();assert len(players)==len(TARGETS)
 with Session(bind=conn)as session:
  qualified=_qualified_name_rows(session,_approved_names(session,KifuPlayerName,'player_id').filter(KifuPlayerName.player_id.in_([p['id']for p in players])),KifuPlayerName,'player_id')
  qualifiedkeys={(n.player_id,n.lang,n.display_name)for n,e in qualified}
  for t in TARGETS:
   p=next(p for p in players if p['canonical_name']==t['canonical_name']);pid=p['id'];lang=t['source_lang'];original=t['qualified_source_name']
   assert(pid,lang,original)in qualifiedkeys and not any(k[0]==pid and k[1]=='tw'for k in qualifiedkeys)
   n=conn.execute(select(KifuPlayerName.__table__).where(KifuPlayerName.player_id==pid,KifuPlayerName.lang==lang)).mappings().one()
   name=_image(conn,KifuPlayerName.__table__,n['id']);evidence=_image(conn,KifuNameResearchEvidence.__table__,n['evidence_id'])
   assert name['decision_kind']==evidence['decision_kind']=='conventional'
   changes=conn.execute(select(KifuNameChange.__table__).where(KifuNameChange.target_table=='kifu_name_research_evidence',KifuNameChange.target_row_id==evidence['id'])).mappings().all();changes=[c for c in changes if c['before_image']is None];assert len(changes)==1
   b=conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id==changes[0]['batch_id'])).mappings().one();assert b['status']=='applied'
   sb={'id':b['id'],'bundle_sha256':b['bundle_sha256'],'evidence_creation_sha256':registry_sha256(evidence)}
   ref='verified_japanese_display'if lang=='jp'else'verified_chinese_display';owner={'kind':'player','id':pid}
   content={'reference_kind':ref,'owner':owner,'original_name':original,'source_lang':'ja'if lang=='jp'else'zh-Hans','source_script':'Kanji'if lang=='jp'else'Hans','binding':{'kind':ref,'owner':owner,'source_name':name,'source_evidence':evidence,'source_batch':sb}}
   live=verified_source_live(conn,{'content':content})if t['player_id']!=446 else None
   target=conn.execute(select(KifuPlayerName.__table__).where(KifuPlayerName.player_id==pid,KifuPlayerName.lang=='tw')).mappings().one_or_none()
   target=_image(conn,KifuPlayerName.__table__,target['id'])if target else None
   games=[dict(g)for g in conn.execute(text('SELECT id,black_player_id,white_player_id,date_played,player_black,player_white,black_rank,white_rank,result,sgf_content FROM kifu_albums WHERE black_player_id=:id OR white_player_id=:id ORDER BY id'),{'id':pid}).mappings()]
   for g in games:g['sgf_utf8_sha256']=hashlib.sha256(g.pop('sgf_content').encode()).hexdigest();g['side']='black'if g['black_player_id']==pid else'white'
   rows.append({'prod_id':t['player_id'],'id':pid,'canonical_name':p['canonical_name'],'owner_preimage':dict(p),'source_name':name,'source_evidence':evidence,'source_batch':sb,'source_creation_journal':[dict(c)for c in changes],'source_qualified_product_gate':True,'verified_source_live':live,'current_target':target,'unsigned_anchor_content':content,'games':len(games),'linked_album_members':games,'source_urls':t['source_urls']})
 conn.rollback()
result={'environment':ENV,'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image_id':IMAGE,'read_only':True,'code_sha256':{f:hashlib.sha256(Path('/app/katrain/web/kifu',f).read_bytes()).hexdigest()for f in ['identity.py','name_evidence.py','name_orthographic.py','name_batch.py']},'rows':rows}
sys.stdout.buffer.write(gzip.compress(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=lambda x:x.isoformat()if isinstance(x,datetime.datetime)else str(x)).encode(),mtime=0))
'''
def capture(env,targets):
 host,container,image=HOSTS[env];program='TARGETS='+repr(targets)+'\nENV='+repr(env)+'\nIMAGE='+repr(image)+'\n'+REMOTE
 command=(f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'+' | grep "^KATRAIN_DATABASE_URL="'+f' | docker run --rm --read-only -i --env-file /dev/stdin --network container:{container} --entrypoint python {image} -c {shlex.quote(program)}')
 r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',host,command],capture_output=True)
 if r.returncode:
  import re
  raise RuntimeError(env+': '+re.sub(r'\w+://\S+','[redacted URL]',r.stderr.decode(errors='replace')[-1600:]))
 data=json.loads(gzip.decompress(r.stdout));(D/f'{env}-tw-source-readonly.json.gz').write_bytes(r.stdout)
 print(env,'rows',len(data['rows']),'targets',[(q['prod_id'],None if q['current_target']is None else(q['current_target']['display_name'],q['current_target']['status']))for q in data['rows']],flush=True)
if __name__=='__main__':
 targets=json.loads((D/'tw17-selected-shortlist.json').read_text())
 for env in HOSTS:capture(env,targets)
