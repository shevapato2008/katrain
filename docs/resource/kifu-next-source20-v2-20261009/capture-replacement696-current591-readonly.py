"""Read one replacement owner only, reusing the reviewed exact-owner capture query."""
import gzip
import hashlib
import importlib.util
import json
import shlex
import subprocess
from pathlib import Path

D = Path(__file__).parent
SRC = D / 'capture-current591-scoped-readonly.py'
spec = importlib.util.spec_from_file_location('bounded20', SRC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

TARGET = {'prod_player_id': 696, 'test_player_id': 697,
          'missing_language': 'ko',
          'existing_qualified_names': {'cn': '高若环', 'en': 'Gao Ruohuan',
                                       'jp': '高若环', 'tw': '高若環'}}
IMAGES = {
    'PROD': 'sha256:02e58b41bac1ca2bdb4cd0aa1d15a319c63781e098b0cb1523dbbc318f2bc7bc',
    'TEST': 'sha256:b606992b2f6c6ce6a7c00bd6c49f1a9fcc7330fc5ee44dd426bd6ecf30267e48',
}
PACKET = {'kind': 'replacement696_single_owner_read_only_request', 'player': TARGET}
raw = (json.dumps(PACKET, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
packet_path = D / 'replacement696-single-owner-readonly-request.json'
packet_path.write_bytes(raw)
packet_sha = hashlib.sha256(raw).hexdigest()
remote = (module.REMOTE.replace('len(TARGETS)==20', 'len(TARGETS)==1')
          .replace('exact20playerowners_current591_no_global_inventory',
                   'exact1playerowner_current591_no_global_inventory'))

for env in ('PROD', 'TEST'):
    host, container = module.HOSTS[env]
    image = IMAGES[env]
    code = f'ENV={env!r}\nTARGETS={[TARGET]!r}\nIMAGE={image!r}\nPACKET_SHA={packet_sha!r}\n' + remote
    command = (f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'
               ' | grep "^KATRAIN_DATABASE_URL="'
               f' | docker run --rm --read-only -i --env-file /dev/stdin --network container:{container}'
               f' --entrypoint python {shlex.quote(image)} -c {shlex.quote(code)}')
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host, command],
                            capture_output=True)
    if result.returncode:
        raise RuntimeError(f'{env}: read-only bounded capture failed: {result.stderr.decode(errors="replace")[-450:]}')
    data = json.loads(gzip.decompress(result.stdout))
    assert data['environment'] == env and data['source_packet_sha256'] == packet_sha
    assert data['read_only'] is True and len(data['rows']) == 1
    assert data['rows'][0]['id'] == TARGET['prod_player_id' if env == 'PROD' else 'test_player_id']
    path = D / f'{env}-replacement696-current591-readonly.json.gz'
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes(result.stdout)
    print(env, data['captured_at'], data['rows'][0]['game_slots'], hashlib.sha256(result.stdout).hexdigest(), flush=True)
