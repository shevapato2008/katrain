import json
import subprocess
import sys
from pathlib import Path

p = Path(__file__).resolve().parent
env, phase = sys.argv[1:]
web = 'katrain-web' if env == 'TEST' else 'katrain-ucloud-katrain-web-1'
image = 'katrain-kifu-importer:review-target-' + env.lower() + '-20261009-r3'
expected = {'TEST': 'sha256:62283df0e9c81b3367e7865acaa8015a9d4931be9f162b6ec969e80c9073d845',
            'PROD': 'sha256:ed6112e7006cad941c52ab28f668af0235ddad2d9761128eeee745c63625c67e'}[env]
assert subprocess.check_output(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'], text=True).strip() == expected
meta = json.loads(subprocess.check_output(['docker', 'inspect', web], text=True))[0]
url = next(e.split('=', 1)[1] for e in meta['Config']['Env'] if e.startswith('KATRAIN_DATABASE_URL='))
result = subprocess.run(['docker', 'run', '--rm', '--read-only', '--user', '0:0', '--network', 'container:' + web,
                         '-e', 'KATRAIN_DATABASE_URL=' + url, '-v', str(p) + ':/work:ro',
                         '--entrypoint', 'python', image, '/work/inner.py', env, phase], capture_output=True, text=True)
(p / f'{env}-{phase}.json').write_text(result.stdout)
if result.returncode:
    import re
    print(re.sub(r'\w+://\S+', '[redacted URL]', result.stderr))
    raise SystemExit(result.returncode)
data = json.loads(result.stdout)
if phase == 'dry-run':
    assert data.get('ready') and data.get('write_ready', True) and not data.get('errors')
if phase == 'apply':
    assert data.get('status') == 'applied'
print(json.dumps({'environment': env, 'phase': phase, 'passed': True,
                  'status': data.get('status'), 'batch_id': data.get('batch_id'), 'changes': data.get('change_count'),
                  'verified_name_count': data.get('verified_name_count'), 'qualified_count': data.get('read_qualified_count'),
                  'complete_players_delta': data.get('complete_players_delta'), 'bundle_sha256': data.get('bundle_sha256')}, ensure_ascii=False))
