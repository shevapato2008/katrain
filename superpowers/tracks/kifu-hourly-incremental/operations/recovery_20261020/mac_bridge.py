"""Private one-off relay; admin SSH keys stay on this Mac. No retry of writes."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

REQUEST = 'KIFU_CACHE_RECOVERY_REQUEST '
SUMMARY = 'KIFU_CACHE_RECOVERY_SUMMARY '
PROD = 'KIFU_CACHE_RECOVERY_PROD '

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest-name', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--publication-key', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'[0-9A-Za-z_-]+\.json', args.manifest_name)
    assert re.fullmatch(r'[0-9a-f]{64}', args.manifest_sha256)
    assert re.fullmatch(r'19x19-event-recovery-[0-9a-f]{24}', args.publication_key)
    os.umask(0o077)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    assert args.out.is_absolute() and not args.out.is_symlink() and args.out.stat().st_mode & 0o077 == 0
    def save(name, value):
        path = args.out / name
        assert not path.exists(), 'never overwrite a prior write-attempt record'
        with path.open('x',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2)
            stream.flush();os.fsync(stream.fileno())
        directory=os.open(args.out,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
    common = ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15']
    test = common + ['-o','ControlPath=/tmp/kifu-hourly-home-active-20261020.sock','home-ubuntu']
    prod = common + ['-o','ControlPath=/tmp/kifu-hourly-prod-active-20261020.sock','ucloud-v100']
    ident = ['--manifest-sha256',args.manifest_sha256,'--publication-key',args.publication_key]
    prodcmd = ['sudo','-n','docker','exec','-i','-e','PYTHONPATH=/app',
               'katrain-ucloud-katrain-web-1','python3','-u',
               '/tmp/kifu-cache-recovery-ops/native_cached_prod.py',*ident]
    def remote_prod(request, publish):
        label = 'publish' if publish else 'read-receipt'
        command = prodcmd + (['--publish','--cache','/tmp/kifu-cache-recovery-ops/trusted-A-sgf-cache.json'] if publish else [])
        # Record intent before opening the only possible writer. A timeout/lost
        # ACK is retained privately and never retries --publish automatically.
        save(label+'-intent.json', {'manifest_sha256':args.manifest_sha256, 'write':publish})
        try:
            result = subprocess.run(prod+[shlex.join(command)], input=json.dumps(request,ensure_ascii=False),
                                    capture_output=True, text=True, encoding='utf-8', timeout=None if publish else 2400)
        except BaseException as exc:
            save(label+'-transport-error.json', {'error_type':type(exc).__name__,'read_receipt_before_retry':True})
            raise
        save(label+'-private-output.json', {'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        lines = [line[len(PROD):] for line in result.stdout.splitlines() if line.startswith(PROD)]
        assert len(lines)==1, 'missing or ambiguous PROD response; read receipt before retry'
        response = json.loads(lines[0])
        if result.returncode or response.get('status') == 'error':
            raise RuntimeError('PROD operator rejected; full actual error saved privately')
        assert response.get('manifest_sha256') == args.manifest_sha256
        return response
    testcmd = ['docker','exec','-i','-e','PYTHONPATH=/app','katrain-cron','python3','-u',
               '/tmp/kifu-cache-recovery-ops/resume_cached_test.py',
               '--manifest','/app/data/kifu_ingest/packages/'+args.manifest_name,*ident,
               '--cache','/app/data/kifu_ingest/recovery-20261020/trusted-A-sgf-cache.json',
               '--out','/tmp/kifu-cache-recovery-evidence','--prod-relay']
    count=0; summaries=[]
    with (args.out/'TEST-private-stderr.log').open('x',encoding='utf-8') as stderr:
        proc = subprocess.Popen(test+[shlex.join(testcmd)], stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                stderr=stderr,text=True,encoding='utf-8',bufsize=1)
        try:
            for line in proc.stdout:
                if line.startswith(REQUEST):
                    count+=1; assert count==1, 'one exact package request only'
                    request=json.loads(line[len(REQUEST):])
                    assert request['operation']=='prod_publish' and request['manifest_sha256']==args.manifest_sha256
                    assert request['manifest']['publication_key']==args.publication_key
                    save('actual-TEST-to-PROD-request.json',request)
                    try:
                        response=remote_prod(request,False)
                        if response['status']=='absent':response=remote_prod(request,True)
                        assert response['status']=='applied' and isinstance(response.get('receipt'),dict)
                        reply={'receipt':response['receipt']}
                        print('Actual PROD receipt received; TEST operator continues complete API verification.',flush=True)
                    except BaseException as exc:
                        proc.stdin.write(json.dumps({'error':type(exc).__name__})+'\n');proc.stdin.flush()
                        raise
                    proc.stdin.write(json.dumps(reply,ensure_ascii=False)+'\n');proc.stdin.flush()
                elif line.startswith(SUMMARY):
                    summary=json.loads(line[len(SUMMARY):]);summaries.append(summary)
                    print(json.dumps(summary),flush=True)
                else:
                    with (args.out/'TEST-private-stdout.log').open('a',encoding='utf-8') as stream:stream.write(line)
            result=proc.wait(timeout=60)
            save('bridge-result.json',{'TEST_returncode':result,'requests':count,'summaries':summaries})
            assert result==0 and summaries and summaries[-1]['status']=='prod_synced'
        finally:
            # Do not terminate a possibly active native writer on a lost channel.
            # Closing this single reply stream lets TEST stop without retrying.
            if proc.stdin and not proc.stdin.closed:proc.stdin.close()

if __name__=='__main__':
    main()
