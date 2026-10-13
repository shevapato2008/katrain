"""Capture exactly the proposed 20 owners; no global album/name snapshot or SQL writes.

Root supplies pinned importer images and runs PROD then TEST after the current batch settles.
The saved post-591 TEST mapping is checked against current four qualified names here.
"""
import argparse
import gzip
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path

D = Path(__file__).resolve().parent
HOSTS = {'PROD': ('ucloud-v100', 'katrain-ucloud-katrain-web-1'),
         'TEST': ('home-ubuntu', 'katrain-web')}
REQUEST = D / 'next20-current-scoped-request.json'
REMOTE = r'''
import datetime,gzip,hashlib,json,os,sys
from pathlib import Path
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from katrain.web.core.models_db import KifuPlayer,KifuPlayerAlias,KifuPlayerName,KifuNameResearchEvidence,KifuNameBatch,KifuNameSourceRegistry
from katrain.web.kifu.name_batch import catalog_snapshot_sha
from katrain.web.kifu.identity import _approved_names,_qualified_name_rows
assert len(KifuPlayerName.__table__.columns)==13
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'],poolclass=NullPool,
                     isolation_level='REPEATABLE READ',
                     connect_args={'options':'-c default_transaction_read_only=on'})
catalog=catalog_snapshot_sha(engine)
with engine.connect() as conn:
 conn.exec_driver_sql('SET TRANSACTION READ ONLY')
 conn.exec_driver_sql("SET LOCAL statement_timeout='90s'")
 assert conn.exec_driver_sql('SHOW transaction_read_only').scalar_one()=='on'
 latest=dict(conn.execute(select(KifuNameBatch.id,KifuNameBatch.status,KifuNameBatch.bundle_sha256)
                          .order_by(KifuNameBatch.id.desc()).limit(1)).mappings().one())
 assert latest['status']=='applied' and latest['id']>=592
 registry=dict(conn.execute(select(KifuNameSourceRegistry.__table__).order_by(KifuNameSourceRegistry.id.desc()).limit(1)).mappings().one())
 ids=[x['prod_player_id' if ENV=='PROD' else 'test_player_id'] for x in TARGETS]
 owners={x['id']:dict(x) for x in conn.execute(select(KifuPlayer.__table__).where(KifuPlayer.id.in_(ids))).mappings()}
 assert len(owners)==len(TARGETS)==20
 with Session(bind=conn) as session:
  q=_approved_names(session,KifuPlayerName,'player_id').filter(KifuPlayerName.player_id.in_(ids))
  qualified=_qualified_name_rows(session,q,KifuPlayerName,'player_id')
  qualified_keys={(n.player_id,n.lang,n.display_name)for n,e in qualified}
 rows=[]
 for entry in TARGETS:
  pid=entry['prod_player_id' if ENV=='PROD' else 'test_player_id']
  names=[dict(x)for x in conn.execute(select(KifuPlayerName.__table__).where(KifuPlayerName.player_id==pid).order_by(KifuPlayerName.lang)).mappings()]
  assert all(len(x)==13 for x in names)
  aliases=[dict(x)for x in conn.execute(select(KifuPlayerAlias.__table__).where(KifuPlayerAlias.player_id==pid).order_by(KifuPlayerAlias.id)).mappings()]
  evidence=[dict(x)for x in conn.execute(select(KifuNameResearchEvidence.__table__).where(KifuNameResearchEvidence.player_id==pid).order_by(KifuNameResearchEvidence.id)).mappings()]
  target=next((x for x in names if x['lang']==entry['missing_language']),None)
  target_evidence=next((x for x in evidence if target is not None and x['id']==target['evidence_id']),None)
  expected=entry['existing_qualified_names']
  assert {lang for owner,lang,name in qualified_keys if owner==pid}==set(expected)
  assert all((pid,lang,name) in qualified_keys for lang,name in expected.items())
  assert entry['missing_language'] not in expected
  games=[dict(x)for x in conn.execute(text('SELECT id,black_player_id,white_player_id,date_played,player_black,player_white,black_rank,white_rank,result,sgf_content FROM kifu_albums WHERE black_player_id=:id OR white_player_id=:id ORDER BY id'),{'id':pid}).mappings()]
  for game in games:
   game['sgf_utf8_sha256']=hashlib.sha256(game.pop('sgf_content').encode()).hexdigest()
   game['side']='black' if game['black_player_id']==pid else 'white'
  rows.append({'prod_player_id':entry['prod_player_id'],'test_player_id':entry['test_player_id'],
               'id':pid,'owner_preimage':owners[pid],'all_name_preimages_13_fields':names,
               'alias_preimages':aliases,'all_owner_evidence_preimages':evidence,
               'target_lang':entry['missing_language'],'target_name_preimage':target,
               'target_evidence_preimage':target_evidence,
               'qualified_languages':sorted(expected),'linked_album_members':games,'game_slots':len(games)})
 conn.rollback()
result={'environment':ENV,'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'read_only':True,'scope':'exact20owners_no_global_album_or_approved_name_snapshot',
        'request_sha256':REQUEST_SHA,'image_id':IMAGE,'catalog_sha256':catalog,
        'latest_batch':{'id':latest['id'],'status':latest['status'],'bundle_sha256':latest['bundle_sha256']},
        'source_registry':registry,'rows':rows,
        'game_slots':sum(x['game_slots']for x in rows),
        'unique_albums':len({g['id']for x in rows for g in x['linked_album_members']})}
sys.stdout.buffer.write(gzip.compress(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),
                                            default=lambda x:x.isoformat()if isinstance(x,datetime.datetime)else str(x)).encode(),mtime=0))
engine.dispose()
'''


def capture(env, targets, request_sha, image):
    host, container = HOSTS[env]
    program = f'ENV={env!r}\nTARGETS={targets!r}\nREQUEST_SHA={request_sha!r}\nIMAGE={image!r}\n' + REMOTE
    command = (f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'
               ' | grep "^KATRAIN_DATABASE_URL="'
               f' | docker run --rm --read-only -i --env-file /dev/stdin --network container:{container}'
               f' --entrypoint python {shlex.quote(image)} -c {shlex.quote(program)}')
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host, command], capture_output=True)
    if result.returncode:
        message = re.sub(r'\w+://\S+', '[redacted URL]', result.stderr.decode(errors='replace')[-1600:])
        raise RuntimeError(f'{env}: {message}')
    data = json.loads(gzip.decompress(result.stdout))
    assert data['environment'] == env and data['request_sha256'] == request_sha and len(data['rows']) == 20
    path = D / f'{env}-next20-current-scoped-readonly.json.gz'
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes(result.stdout)
    print(env, path.name, 'slots', data['game_slots'], 'sha256', hashlib.sha256(result.stdout).hexdigest(), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root-confirms-current-state', action='store_true')
    parser.add_argument('--prod-image', required=True)
    parser.add_argument('--test-image', required=True)
    args = parser.parse_args()
    if not args.root_confirms_current_state:
        raise SystemExit('root current-state confirmation required')
    raw = REQUEST.read_bytes()
    request = json.loads(raw)
    assert len(request['rows']) == 20
    sha = hashlib.sha256(raw).hexdigest()
    capture('PROD', request['rows'], sha, args.prod_image)
    capture('TEST', request['rows'], sha, args.test_image)
