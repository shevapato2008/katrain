"""Root-only PROD read-only Docker runner for bounded batch-594 statistics."""

import hashlib
import json
from pathlib import Path
import re
import subprocess


if not __debug__:
    raise RuntimeError('stats runner assertions must be enabled')
D = Path(__file__).resolve().parent
WEB = 'katrain-ucloud-katrain-web-1'
IMAGE = 'sha256:6ffe9b6dad44ae280dc756d8468f1695337ca786541976413b515e614ebab3c5'
STDERR_URL = re.compile(r'\w+://\S+')


def main():
    progress_path = D / '594-PROD-progress-actual.json'
    audit_path = D / '594-PROD-bounded-stats.json'
    if progress_path.exists() or audit_path.exists():
        raise FileExistsError('batch-594 stats output already exists')
    actual = subprocess.check_output(['docker', 'image', 'inspect', IMAGE,
                                      '--format', '{{.Id}}'], text=True).strip()
    if actual != IMAGE:
        raise RuntimeError('pinned PROD importer image ID changed')
    meta = json.loads(subprocess.check_output(['docker', 'inspect', WEB], text=True))[0]
    urls = [entry.split('=', 1)[1] for entry in meta['Config']['Env']
            if entry.startswith('KATRAIN_DATABASE_URL=')]
    if len(urls) != 1:
        raise RuntimeError('running web container lacks one database URL')
    command = ['docker', 'run', '--rm', '--read-only', '--user', '0:0', '-i',
               '--network', 'container:' + WEB, '--env-file', '/dev/stdin',
               '-v', str(D) + ':/work:ro', '-w', '/app', '--entrypoint', 'python',
               IMAGE, '/work/594_bounded_stats.py']
    completed = subprocess.run(command, input=('KATRAIN_DATABASE_URL=' + urls[0] + '\n').encode(),
                               capture_output=True)
    if completed.returncode:
        stderr = completed.stderr.decode(errors='replace')[-2000:]
        raise RuntimeError(STDERR_URL.sub('[redacted URL]', stderr))
    data = json.loads(completed.stdout)
    audit = data['audit']
    assert audit['environment'] == 'PROD' and audit['batch_id'] == 594 and audit['read_only'] is True
    assert audit['bounded_scope']['games'] == audit['bounded_scope']['event_after_qualified'] == 938
    progress_path.write_text(json.dumps(data['progress'], ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'progress': progress_path.name,
                      'progress_sha256': hashlib.sha256(progress_path.read_bytes()).hexdigest(),
                      'audit': audit_path.name,
                      'audit_sha256': hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                      'bounded_scope': audit['bounded_scope'],
                      'raw_title_coverage': audit['raw_title_coverage']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
