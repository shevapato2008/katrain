"""Root-only PROD read-only runner for the r5→r6 batch-597 statistics correction."""

import hashlib
import json
from pathlib import Path
import re
import subprocess


D = Path(__file__).resolve().parent
WEB = 'katrain-ucloud-katrain-web-1'
WEB_IMAGE = 'sha256:fabec65da76101313ba5b96ae2f4116982f8b3b7722a3b76a9bec06721ab08ee'
IMAGE = 'sha256:6eb7597b5b478c082fe91405c0223531a46380bf53b9d7dc33e8e74cfb642b02'
R6_MODULE_SHA256 = '0aab89aa5a93541dde26381254d3e9ff1a1a1dc6707b6089ba6fd6f473506b1f'
if not __debug__:
    raise RuntimeError('stats assertions must be enabled')


def main():
    progress_path = D / '597-r6-PROD-progress-actual.json'
    audit_path = D / '597-r6-PROD-correction-audit.json'
    if progress_path.exists() or audit_path.exists():
        raise FileExistsError('corrected stats output already exists')
    actual = subprocess.check_output(['docker', 'image', 'inspect', IMAGE,
                                      '--format', '{{.Id}}'], text=True).strip()
    if actual != IMAGE:
        raise RuntimeError('pinned PROD importer image ID changed')
    meta = json.loads(subprocess.check_output(['docker', 'inspect', WEB], text=True))[0]
    if meta['Image'] != WEB_IMAGE:
        raise RuntimeError('running web image differs from its pin')
    module_sha = subprocess.check_output([
        'docker', 'run', '--rm', '--read-only', '--network', 'none', '--entrypoint', 'sha256sum', IMAGE,
        '/app/katrain/web/kifu/raw_event_translation.py'], text=True).split()[0]
    if module_sha != R6_MODULE_SHA256:
        raise RuntimeError('r6 module hash differs from pin')
    urls = [entry.split('=', 1)[1] for entry in meta['Config']['Env']
            if entry.startswith('KATRAIN_DATABASE_URL=')]
    if len(urls) != 1:
        raise RuntimeError('running web container lacks one database URL')
    command = ['docker', 'run', '--rm', '--read-only', '--user', '0:0', '-i',
               '--network', 'container:' + WEB, '--env-file', '/dev/stdin',
               '-v', str(D) + ':/work:ro', '-w', '/app', '--entrypoint', 'python',
               IMAGE, '/work/597_r6_correction.py']
    completed = subprocess.run(command, input=('KATRAIN_DATABASE_URL=' + urls[0] + '\n').encode(),
                               capture_output=True)
    if completed.returncode:
        stderr = completed.stderr.decode(errors='replace')[-2000:]
        raise RuntimeError(re.sub(r'[A-Za-z][A-Za-z0-9+.-]*://\S+', '[redacted URL]', stderr))
    data = json.loads(completed.stdout)
    audit = data['audit']
    assert audit['environment'] == 'PROD' and audit['batch_id'] == 597 and audit['read_only'] is True
    assert audit['new_597_scope']['games'] == 174 and audit['new_597_scope']['raw_cards_after'] == 148
    assert audit['older_restored_owner_count'] == 1241
    progress_path.write_text(json.dumps(data['progress'], ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'progress': progress_path.name,
                      'progress_sha256': hashlib.sha256(progress_path.read_bytes()).hexdigest(),
                      'audit': audit_path.name,
                      'audit_sha256': hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                      'older_restoration': audit['older_r6_restoration_scope']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
