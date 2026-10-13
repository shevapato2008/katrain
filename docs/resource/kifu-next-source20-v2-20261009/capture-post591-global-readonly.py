"""Capture one current post-591 global read-only context per environment.

Run PROD now with the pinned stable r4 importer image. Run TEST only after the
root signals its network container is stable. No SQL write, signing or deploy.
"""
import argparse
import gzip
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path

D = Path(__file__).parent
SOURCE = D / 'source20-post591-final-pending.json'
HOSTS = {'PROD': ('ucloud-v100', 'katrain-ucloud-katrain-web-1'),
         'TEST': ('home-ubuntu', 'katrain-web')}
IMAGES = {'PROD': 'sha256:02e58b41bac1ca2bdb4cd0aa1d15a319c63781e098b0cb1523dbbc318f2bc7bc',
          'TEST': 'sha256:b606992b2f6c6ce6a7c00bd6c49f1a9fcc7330fc5ee44dd426bd6ecf30267e48'}
REMOTE = r'''
import datetime,gzip,hashlib,json,os,sys
from pathlib import Path
from sqlalchemy import create_engine,select
from katrain.web.core.models_db import KifuNameBatch,KifuNameSourceRegistry
from katrain.web.kifu.name_batch import catalog_snapshot_sha,approved_name_snapshot,orthographic_alias_snapshot
from katrain.web.kifu.name_inventory import build_inventory
def readonly_engine():
 return create_engine(os.environ['KATRAIN_DATABASE_URL'],
                      connect_args={'options':'-c default_transaction_read_only=on -c statement_timeout=600000'})
engine=readonly_engine()
with engine.connect() as conn:
 assert conn.exec_driver_sql('SHOW transaction_read_only').scalar_one()=='on'
 latest=dict(conn.execute(select(KifuNameBatch.__table__).order_by(KifuNameBatch.id.desc()).limit(1)).mappings().one())
 assert latest['id']==591 and latest['status']=='applied',latest['id']
 conn.rollback()
engine.dispose()
engine=readonly_engine()
inventory=build_inventory(engine)
engine.dispose()
engine=readonly_engine()
with engine.connect() as conn:
 assert conn.exec_driver_sql('SHOW transaction_read_only').scalar_one()=='on'
 conn.rollback()
catalog=catalog_snapshot_sha(engine)
engine.dispose()
engine=readonly_engine()
with engine.connect() as conn:
 assert conn.exec_driver_sql('SHOW transaction_read_only').scalar_one()=='on'
 conn.rollback()
approved=approved_name_snapshot(engine)
engine.dispose()
engine=readonly_engine()
with engine.connect() as conn:
 assert conn.exec_driver_sql('SHOW transaction_read_only').scalar_one()=='on'
 aliases=orthographic_alias_snapshot(conn)
 registry=dict(conn.execute(select(KifuNameSourceRegistry.__table__).order_by(KifuNameSourceRegistry.id.desc()).limit(1)).mappings().one())
 latest_after=dict(conn.execute(select(KifuNameBatch.__table__).order_by(KifuNameBatch.id.desc()).limit(1)).mappings().one())
 assert latest_after['id']==591 and latest_after['status']=='applied',latest_after['id']
 conn.rollback()
from collections import defaultdict
names=defaultdict(dict)
for row in approved:
 if row['owner']['kind']=='player' and row['owner']['id'] in IDS and row['lang'] in ('cn','tw','jp','ko','en'):
  names[row['owner']['id']][row['lang']]=row['display_name']
qualified=[]
for row in TARGETS:
 pid=row['prod_player_id' if ENV=='PROD' else 'test_player_id']
 assert names[pid]==row['existing_qualified_names'],(pid,names[pid])
 assert row['missing_language'] not in names[pid]
 qualified.append({'prod_player_id':row['prod_player_id'],'test_player_id':row['test_player_id'],
                   'owner_id':pid,'missing_language':row['missing_language'],
                   'currently_qualified_names':names[pid]})
code={name:hashlib.sha256(Path('/app/katrain/web/kifu',name).read_bytes()).hexdigest()
      for name in ('identity.py','name_candidates.py','name_evidence.py','name_orthographic.py','name_batch.py','name_inventory.py')}
result={'environment':ENV,'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'read_only':True,'scope':'current_post591_global_one_pass_no_owner_writes',
        'source_packet_sha256':SOURCE_SHA,'image_id':IMAGE,
        'inventory':inventory,'catalog_sha256':catalog,
        'approved_name_snapshot':approved,'known_aliases':aliases,
        'source_registry':registry,'latest_batch':latest_after,
        'target20_current_qualified_names':qualified,'code_sha256':code}
sys.stdout.buffer.write(gzip.compress(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),
                                            default=lambda x:x.isoformat()if isinstance(x,datetime.datetime)else str(x)).encode(),mtime=0))
engine.dispose()
'''


def capture(env):
    source_raw = SOURCE.read_bytes()
    packet = json.loads(source_raw)
    targets = [{k: row[k] for k in ('prod_player_id', 'test_player_id', 'missing_language',
                                    'existing_qualified_names')} for row in packet['players']]
    assert len(targets) == 20
    ids = [row['prod_player_id' if env == 'PROD' else 'test_player_id'] for row in targets]
    host, container = HOSTS[env]
    image = IMAGES[env]
    code = (f'ENV={env!r}\nTARGETS={targets!r}\nIDS={ids!r}\nIMAGE={image!r}\n'
            f'SOURCE_SHA={hashlib.sha256(source_raw).hexdigest()!r}\n' + REMOTE)
    command = (f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'
               ' | grep "^KATRAIN_DATABASE_URL="'
               f' | docker run --rm --read-only -i --env-file /dev/stdin --network container:{container}'
               f' --entrypoint python {shlex.quote(image)} -c {shlex.quote(code)}')
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host, command],
                            capture_output=True)
    if result.returncode:
        message = re.sub(r'\w+://\S+', '[redacted URL]', result.stderr.decode(errors='replace')[-1300:])
        raise RuntimeError(f'{env}: {message}')
    data = json.loads(gzip.decompress(result.stdout))
    assert data['environment'] == env and data['source_packet_sha256'] == hashlib.sha256(source_raw).hexdigest()
    assert data['read_only'] and len(data['target20_current_qualified_names']) == 20
    assert data['latest_batch']['id'] == 591 and data['latest_batch']['status'] == 'applied'
    path = D / f'{env}-post591-global-readonly.json.gz'
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes(result.stdout)
    print(env, path.name, 'sha256', hashlib.sha256(result.stdout).hexdigest(),
          'inventory', data['inventory']['sha256'],
          'catalog', data['catalog_sha256'],
          'qualified_snapshot_rows', len(data['approved_name_snapshot']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', choices=['PROD', 'TEST'], required=True)
    args = parser.parse_args()
    capture(args.env)
