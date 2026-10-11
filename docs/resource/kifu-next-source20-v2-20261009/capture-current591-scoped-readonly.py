"""Read only current post-591 state for exactly the v2 20 player owners.

The root supplies current pinned image IDs. This script never changes SQL rows,
signs evidence, touches the deployment, or scans the global album inventory.
"""
import argparse
import gzip
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

D = Path(__file__).parent
HOSTS = {'PROD': ('ucloud-v100', 'katrain-ucloud-katrain-web-1'),
         'TEST': ('home-ubuntu', 'katrain-web')}
PACKET = D / 'source20-v2.json'
REMOTE = r'''
import datetime,gzip,hashlib,json,os,sys
from pathlib import Path
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from katrain.web.core.models_db import KifuPlayer,KifuPlayerAlias,KifuPlayerName,KifuNameResearchEvidence,KifuNameBatch,KifuNameChange,KifuNameSourceRegistry
from katrain.web.kifu.identity import _approved_names,_qualified_name_rows
assert len(KifuPlayerName.__table__.columns)==13
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'],
                     isolation_level='REPEATABLE READ',
                     connect_args={'options':'-c default_transaction_read_only=on'})
rows=[]
with engine.connect() as conn:
 conn.exec_driver_sql('SET TRANSACTION READ ONLY')
 conn.exec_driver_sql("SET LOCAL statement_timeout='90s'")
 assert conn.exec_driver_sql('SHOW transaction_read_only').scalar_one()=='on'
 batch=dict(conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id==591)).mappings().one())
 assert batch['status']=='applied'
 latest=conn.execute(select(KifuNameBatch.id).order_by(KifuNameBatch.id.desc()).limit(1)).scalar_one()
 assert latest==591, f'expected current batch 591, found {latest}'
 journal=[dict(x)for x in conn.execute(select(KifuNameChange.__table__).where(KifuNameChange.batch_id==591).order_by(KifuNameChange.sequence)).mappings()]
 registry=dict(conn.execute(select(KifuNameSourceRegistry.__table__).order_by(KifuNameSourceRegistry.id.desc()).limit(1)).mappings().one())
 ids=[entry['prod_player_id' if ENV=='PROD' else 'test_player_id']for entry in TARGETS]
 ownerrows=[dict(x)for x in conn.execute(select(KifuPlayer.__table__).where(KifuPlayer.id.in_(ids))).mappings()]
 byid={x['id']:x for x in ownerrows}
 assert len(byid)==len(TARGETS)==20
 with Session(bind=conn)as session:
  q=_approved_names(session,KifuPlayerName,'player_id').filter(KifuPlayerName.player_id.in_(ids))
  qualified=_qualified_name_rows(session,q,KifuPlayerName,'player_id')
  qualified_keys={(n.player_id,n.lang,n.display_name)for n,e in qualified}
 for entry in TARGETS:
  pid=entry['prod_player_id' if ENV=='PROD' else 'test_player_id']
  owner=byid[pid]
  names=[dict(x)for x in conn.execute(select(KifuPlayerName.__table__).where(KifuPlayerName.player_id==pid).order_by(KifuPlayerName.lang)).mappings()]
  assert all(len(x)==13 for x in names)
  aliases=[dict(x)for x in conn.execute(select(KifuPlayerAlias.__table__).where(KifuPlayerAlias.player_id==pid).order_by(KifuPlayerAlias.id)).mappings()]
  evidence=[dict(x)for x in conn.execute(select(KifuNameResearchEvidence.__table__).where(KifuNameResearchEvidence.player_id==pid).order_by(KifuNameResearchEvidence.id)).mappings()]
  target_lang=entry['missing_language']
  target=next((x for x in names if x['lang']==target_lang),None)
  target_evidence=next((x for x in evidence if target is not None and x['id']==target['evidence_id']),None)
  qlangs={lang for owner_id,lang,display in qualified_keys if owner_id==pid}
  assert qlangs==set(entry['existing_qualified_names'])
  assert all((pid,lang,display)in qualified_keys for lang,display in entry['existing_qualified_names'].items())
  assert target_lang not in qlangs
  games=[dict(x)for x in conn.execute(text('SELECT id,black_player_id,white_player_id,date_played,player_black,player_white,black_rank,white_rank,result,sgf_content FROM kifu_albums WHERE black_player_id=:id OR white_player_id=:id ORDER BY id'),{'id':pid}).mappings()]
  for game in games:
   game['sgf_utf8_sha256']=hashlib.sha256(game.pop('sgf_content').encode()).hexdigest()
   game['side']='black'if game['black_player_id']==pid else'white'
  rows.append({'prod_player_id':entry['prod_player_id'],'test_player_id':entry['test_player_id'],
               'id':pid,'owner_preimage':owner,'all_name_preimages_13_fields':names,
               'alias_preimages':aliases,'all_owner_evidence_preimages':evidence,
               'target_lang':target_lang,'target_name_preimage':target,
               'target_evidence_preimage':target_evidence,
               'qualified_languages':sorted(qlangs),'linked_album_members':games,
               'game_slots':len(games)})
 conn.rollback()
code={name:hashlib.sha256(Path('/app/katrain/web/kifu',name).read_bytes()).hexdigest()
      for name in ('identity.py','name_candidates.py','name_evidence.py','name_orthographic.py','name_batch.py','name_inventory.py')}
result={'environment':ENV,'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'read_only':True,'scope':'exact20playerowners_current591_no_global_inventory',
        'source_packet_sha256':PACKET_SHA,'image_id':IMAGE,'batch591':batch,
        'batch591_journal':journal,'source_registry':registry,'code_sha256':code,
        'rows':rows,'game_slots':sum(row['game_slots']for row in rows),
        'unique_albums':len({game['id']for row in rows for game in row['linked_album_members']})}
sys.stdout.buffer.write(gzip.compress(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),
                                            default=lambda x:x.isoformat()if isinstance(x,datetime.datetime)else str(x)).encode(),mtime=0))
engine.dispose()
'''

def capture(env, packet, packet_sha, image):
    host, container = HOSTS[env]
    targets=[{key:row[key] for key in ('prod_player_id','test_player_id','missing_language','existing_qualified_names')}
             for row in packet['players']]
    code=(f'ENV={env!r}\nTARGETS={targets!r}\nIMAGE={image!r}\nPACKET_SHA={packet_sha!r}\n'+REMOTE)
    command=(f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'
             ' | grep "^KATRAIN_DATABASE_URL="'
             f' | docker run --rm --read-only -i --env-file /dev/stdin --network container:{container}'
             f' --entrypoint python {shlex.quote(image)} -c {shlex.quote(code)}')
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',host,command],capture_output=True)
    if result.returncode:
        import re
        message=re.sub(r'\w+://\S+','[redacted URL]',result.stderr.decode(errors='replace')[-1200:])
        raise RuntimeError(f'{env}: {message}')
    data=json.loads(gzip.decompress(result.stdout))
    assert data['environment']==env and data['source_packet_sha256']==packet_sha
    assert len(data['rows'])==20 and data['batch591']['status']=='applied'
    assert {(row['prod_player_id'],row['test_player_id']) for row in data['rows']}=={
        (row['prod_player_id'],row['test_player_id']) for row in packet['players']}
    path=D/f'{env}-current591-exact20-readonly.json.gz'
    if path.exists():raise FileExistsError(path)
    path.write_bytes(result.stdout)
    print(env,'saved',path,'rows',len(data['rows']),'slots',data['game_slots'],'sha256',hashlib.sha256(result.stdout).hexdigest(),flush=True)
    return data

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root-confirms-importer-built-591-applied',action='store_true')
    parser.add_argument('--prod-image',required=True)
    parser.add_argument('--test-image',required=True)
    args=parser.parse_args()
    if not args.root_confirms_importer_built_591_applied:raise SystemExit('root importer-image and batch-591 confirmation required')
    raw=PACKET.read_bytes();packet=json.loads(raw);assert len(packet['players'])==20
    source_sha=hashlib.sha256(raw).hexdigest()
    capture('PROD',packet,source_sha,args.prod_image)
    capture('TEST',packet,source_sha,args.test_image)
