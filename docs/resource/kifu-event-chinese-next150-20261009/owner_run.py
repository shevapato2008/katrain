"""Root-only remote runner for owner prepare/dry-run/apply/verify.

Apply requires a separate root execution approval pinned to both actual plans.
The running web container supplies its database URL without displaying it.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess


if not __debug__:
    raise RuntimeError('owner approval assertions must be enabled')

D = Path(__file__).resolve().parent
STDERR_URL = re.compile(r'\w+://\S+')
WEB_IMAGES = {
    'TEST': 'sha256:1f9c816c13f307987d44b66e0c5039391851104d4a0e89e5133f5d374f657547',
    'PROD': 'sha256:fabec65da76101313ba5b96ae2f4116982f8b3b7722a3b76a9bec06721ab08ee',
}
MODULE_SHA256 = '0aab89aa5a93541dde26381254d3e9ff1a1a1dc6707b6089ba6fd6f473506b1f'
CONFIG = {
    'TEST': ('katrain-web',
             'sha256:82124209ad6425190d587fec10b06eb7cab8b80067cd345cc523bd9a760523c4'),
    'PROD': ('katrain-ucloud-katrain-web-1',
             'sha256:6eb7597b5b478c082fe91405c0223531a46380bf53b9d7dc33e8e74cfb642b02'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=tuple(CONFIG))
    parser.add_argument('phase', choices=('prepare', 'dry-run', 'apply', 'verify'))
    args = parser.parse_args()
    env, phase = args.environment, args.phase
    web, image = CONFIG[env]
    output = D / f'{env}-owner-{phase}.json.gz'
    if output.exists():
        raise FileExistsError(output)
    if phase == 'apply':
        approval = json.loads((D / 'owner-plan-execution-approval.json').read_text())
        assert approval['status'] == 'approved_owner_plan_execution'
        assert approval['allow_apply'] is True and approval['reviewer_id'] == '/root'
        assert approval['environments'][env]['image_id'] == image
    actual = subprocess.check_output(['docker', 'image', 'inspect', image,
                                      '--format', '{{.Id}}'], text=True).strip()
    if actual != image:
        raise RuntimeError('pinned native importer image ID changed')
    meta = json.loads(subprocess.check_output(['docker', 'inspect', web], text=True))[0]
    if meta['Image'] != WEB_IMAGES[env]:
        raise RuntimeError('running web image differs from its pin')
    module_sha = subprocess.check_output([
        'docker', 'run', '--rm', '--read-only', '--network', 'none', '--entrypoint', 'sha256sum', image,
        '/app/katrain/web/kifu/raw_event_translation.py'], text=True).split()[0]
    if module_sha != MODULE_SHA256:
        raise RuntimeError('native mixed-game module hash differs')
    urls = [item.split('=', 1)[1] for item in meta['Config']['Env']
            if item.startswith('KATRAIN_DATABASE_URL=')]
    if len(urls) != 1:
        raise RuntimeError('running web container lacks one database URL')
    command = ['docker', 'run', '--rm', '--read-only', '--user', '0:0', '-i',
               '--network', 'container:' + web, '--env-file', '/dev/stdin',
               '-v', str(D) + ':/work:ro', '-w', '/app', '--entrypoint', 'python',
               image, '/work/owner_inner.py', env, phase]
    completed = subprocess.run(command, input=('KATRAIN_DATABASE_URL=' + urls[0] + '\n').encode(),
                               capture_output=True)
    if completed.returncode:
        stderr = completed.stderr.decode(errors='replace')[-2000:]
        raise RuntimeError(STDERR_URL.sub('[redacted URL]', stderr))
    result = json.loads(completed.stdout)
    if result['environment'] != env or result['phase'] != phase:
        raise RuntimeError('owner result identity differs')
    output.write_bytes(gzip.compress(completed.stdout, mtime=0))
    print(json.dumps({'environment': env, 'phase': phase,
                      'status': result['status'], 'output': output.name,
                      'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                      'compressed_bytes': output.stat().st_size,
                      'plan_canonical_sha256': result['plan_canonical_sha256']},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
