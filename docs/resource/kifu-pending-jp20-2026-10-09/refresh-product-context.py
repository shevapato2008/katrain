"""Refresh global qualification after root's preceding batch, retaining the unchanged inventory."""

import gzip
import importlib.util
import json
import shlex
import subprocess
from pathlib import Path

DIRECTORY = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('source_capture', DIRECTORY / 'capture-readonly.py')
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)

REMOTE = '''import datetime,gzip,json,os,sys
from sqlalchemy import create_engine,select
from katrain.web.kifu.name_batch import catalog_snapshot_sha,approved_name_snapshot,orthographic_alias_snapshot
from katrain.web.core.models_db import KifuNameSourceRegistry
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'],connect_args={'options':'-c default_transaction_read_only=on'})
catalog=catalog_snapshot_sha(engine)
approved=approved_name_snapshot(engine)
with engine.connect() as conn:
    conn.exec_driver_sql('SET TRANSACTION READ ONLY')
    aliases=orthographic_alias_snapshot(conn)
    registry=dict(conn.execute(select(KifuNameSourceRegistry.__table__).order_by(KifuNameSourceRegistry.id.desc()).limit(1)).mappings().one())
    conn.rollback()
data={'catalog_sha256':catalog,'approved_name_snapshot':approved,'known_aliases':aliases,'source_registry':registry,'context_refreshed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
sys.stdout.buffer.write(gzip.compress(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=lambda value:value.isoformat()).encode(),mtime=0))
engine.dispose()
'''


def refresh(environment):
    host, container, image = CAPTURE.HOSTS[environment]
    command = (
        f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'
        ' | grep "^KATRAIN_DATABASE_URL="'
        f' | docker run --rm --read-only -i --env-file /dev/stdin --network container:{container}'
        f' --entrypoint python {image} -c {shlex.quote(REMOTE)}'
    )
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host, command],
                            capture_output=True, check=True)
    data = json.loads(gzip.decompress(result.stdout))
    path = DIRECTORY / f'{environment}-product-snapshots.json.gz'
    old = json.load(gzip.open(path, 'rt'))
    assert old['catalog_sha256'] == data['catalog_sha256']
    data['inventory'] = old['inventory']
    data['inventory_reused_from_actual_unchanged_preceding_capture'] = True
    data['image_id'] = image
    registry = data.pop('source_registry')
    (DIRECTORY / f'{environment}-source-registry-readonly.json').write_text(
        json.dumps(registry, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    path.write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                            separators=(',', ':')).encode(), mtime=0))
    print(environment, 'updated context', data['context_refreshed_at'],
          'qualified names', len(data['approved_name_snapshot']), 'inventory reused unchanged')


if __name__ == '__main__':
    import sys
    for environment in (sys.argv[1:] or ['PROD', 'TEST']):
        refresh(environment)
