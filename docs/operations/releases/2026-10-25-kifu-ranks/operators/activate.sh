#!/usr/bin/env bash
set -euo pipefail
umask 077
release=/mnt/data/smartbox-deployments/20261025-kifu-rank-fallback-93f2038a0
runtime=/root/smartbox-software/vendor/katrain
source_sha=93f2038a0020d43b3090b1a71c8877980580f740
parent_sha=51825c0e00a7f58544193ea6d584489252c6887e
dropin=/etc/systemd/system/smartbox-katrain.service.d/zzzzzzzzzzzzz-kifu-rank-fallback-release.conf
python=/opt/smartbox/venv-katrain/bin/python
[ -f "$release/rollback/runtime-files.json" ]
[ ! -e "$dropin" ]
"$python" - <<'PY'
import json,urllib.request,urllib.error,urllib.parse,os,re
import hashlib,subprocess
from pathlib import Path
baseline=json.loads(Path('/mnt/data/smartbox-deployments/20261025-kifu-rank-fallback-93f2038a0/device-runtime-before.json').read_text())
pid=subprocess.check_output(['systemctl','show','smartbox-katrain.service','-p','MainPID','--value'],text=True).strip()
assert pid==baseline['pid'],'service changed after backup; inspect before activation'
actual=[x.decode() for x in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if x.startswith(b'KATRAIN_BUILD_SHA=')]
assert actual==baseline['build_sha'],'running source changed after backup'
for name,digest in baseline['python'].items():
 assert hashlib.sha256((Path('/root/smartbox-software/vendor/katrain')/name).read_bytes()).hexdigest()==digest,'runtime changed after backup: '+name
v=json.load(urllib.request.urlopen('http://127.0.0.1:8081/api/v1/vision/status'))
stale_binding=False
if v.get('bound_session_id') is not None:
 try:
  urllib.request.urlopen('http://127.0.0.1:8081/api/state?'+urllib.parse.urlencode({'session_id':v['bound_session_id']}),timeout=5)
  raise AssertionError('active bound session; do not restart')
 except urllib.error.HTTPError as exc:
  assert exc.code==404 and json.load(exc).get('detail')=='Session not found','bound session is not a confirmed orphan'
  stale_binding=True
else:
 assert v.get('sync_state') in ('unbound','idle'),'unexpected physical state'
pages=json.load(urllib.request.urlopen('http://127.0.0.1:9222/json/list'))
urls=[p['url'] for p in pages if p.get('type')=='page']
assert len(urls)==1 and urls[0].startswith('http://127.0.0.1:8081/kiosk/') and not re.search(r'/(game|room)(/|$)',urls[0]),'live game route; do not switch'
from pathlib import Path
Path('/mnt/data/smartbox-deployments/20261025-kifu-rank-fallback-93f2038a0/pre-activation-browser.json').write_text(json.dumps({'url':urls[0],'orphan_binding_confirmed_404':stale_binding}))
s=os.statvfs('/');assert s.f_bavail*s.f_frsize>=1024**3,'root space below 1GiB reserve'
PY
rollback() {
  echo 'activation failed; restoring prior source/static and restarting only KaTrain' >&2
  systemctl stop smartbox-katrain.service || true
  rsync -a "$release/rollback/runtime/" "$runtime/"
  RELEASE_DIR="$release" RUNTIME_DIR="$runtime" "$python" - <<'PY'
from pathlib import Path
import json,os,shutil
r=Path(os.environ['RELEASE_DIR']);d=Path(os.environ['RUNTIME_DIR'])
for name in json.loads((r/'rollback/runtime-files.json').read_text())['absent']:
 (d/name).unlink(missing_ok=True)
for name in ['.smartbox-deployed-commit','.smartbox-release.json']:
 old=r/'rollback'/name
 if old.exists():shutil.copy2(old,d/name)
 else:(d/name).unlink(missing_ok=True)
old=r/'rollback/.smartbox-deploy-revisions'
if old.exists():shutil.copy2(old,Path('/root/smartbox-software/.smartbox-deploy-revisions'))
PY
  rsync -a --delete "$release/rollback/static/" "$runtime/katrain/web/static/"
  rsync -a --delete "$release/rollback/static-kiosk-2d/" "$runtime/katrain/web/static-kiosk-2d/"
  rm -f -- "$dropin"
  systemctl daemon-reload
  systemctl start smartbox-katrain.service
}
trap rollback ERR
old_pid=$(systemctl show smartbox-katrain.service -p MainPID --value)
cgroup=$(systemctl show smartbox-katrain.service -p ControlGroup --value)
systemctl stop smartbox-katrain.service
[ "$(systemctl show smartbox-katrain.service -p MainPID --value)" = 0 ]
[ ! -e "/proc/$old_pid" ]
for prefix in /sys/fs/cgroup /sys/fs/cgroup/systemd; do
 if [ -f "$prefix$cgroup/cgroup.procs" ]; then [ -z "$(cat "$prefix$cgroup/cgroup.procs")" ]; fi
done
rsync -ac "$release/payload/runtime/" "$runtime/"
for name in static static-kiosk-2d; do
 rsync -ac --exclude=index.html "$release/payload/$name/" "$runtime/katrain/web/$name/"
 install -m 0644 "$release/payload/$name/index.html" "$runtime/katrain/web/$name/index.html.dialog-font-new"
 mv "$runtime/katrain/web/$name/index.html.dialog-font-new" "$runtime/katrain/web/$name/index.html"
done
cp "$release/payload/manifest.json" "$release/manifest.json"
SOURCE_SHA="$source_sha" PARENT_SHA="$parent_sha" RELEASE_DIR="$release" RUNTIME_DIR="$runtime" "$python" - <<'PY'
from pathlib import Path
import json,os,datetime,hashlib
r=Path(os.environ['RELEASE_DIR']);d=Path(os.environ['RUNTIME_DIR'])
record={'katrain':os.environ['SOURCE_SHA'],'smartbox_parent':os.environ['PARENT_SHA'],'scope':'vendor/katrain tracked runtime Python and content policy JSON plus full and strict static only; other games/config/data/models/hardware preserved','manifest':str(r/'manifest.json'),'manifest_sha256':hashlib.sha256((r/'manifest.json').read_bytes()).hexdigest(),'activated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(d/'.smartbox-release.json').write_text(json.dumps(record,indent=2)+'\n')
(d/'.smartbox-deployed-commit').write_text(os.environ['SOURCE_SHA']+'\n')
Path('/root/smartbox-software/.smartbox-deploy-revisions').write_text('main='+os.environ['PARENT_SHA']+'\nvendor/katrain='+os.environ['SOURCE_SHA']+'\nscope=vendor/katrain-runtime-python,content-policy,static,static-kiosk-2d\n')
PY
printf '[Service]\nEnvironment=KATRAIN_BUILD_SHA=%s\n' "$source_sha" > "$dropin"
chmod 0644 "$dropin"
systemctl daemon-reload
systemctl start smartbox-katrain.service
ready=0
for i in $(seq 1 60); do
 if "$python" - <<'PY'
import json,urllib.request
try:
 h=json.load(urllib.request.urlopen('http://127.0.0.1:8081/api/v1/health',timeout=3))
 v=json.load(urllib.request.urlopen('http://127.0.0.1:8081/api/v1/vision/status',timeout=3))
 assert h.get('status')=='ok' and h.get('engines',{}).get('local')=='reachable'
 assert all(v.get(k) is True for k in ['enabled','camera_connected','camera_ready'])
except Exception:raise SystemExit(1)
PY
 then ready=1;break;fi
 sleep 1
done
[ "$ready" = 1 ]
RELEASE_DIR="$release" RUNTIME_DIR="$runtime" "$python" - <<'PY'
from pathlib import Path
import hashlib,json,os,urllib.request,urllib.error
r=Path(os.environ['RELEASE_DIR']);d=Path(os.environ['RUNTIME_DIR']);m=json.loads((r/'manifest.json').read_text())
for name,expected in m['files'].items():
 rel=Path(name)
 f=d/rel.relative_to('runtime') if name.startswith('runtime/') else d/'katrain/web'/rel
 assert hashlib.sha256(f.read_bytes()).hexdigest()==expected,name
for name,expected in json.loads((r/'rollback/preserved-sha256.json').read_text()).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected,'preserved file changed: '+name
print('activation verified: all runtime, policy, static hashes and protected state unchanged')
PY
trap - ERR
echo "RK activation complete: $source_sha; previous PID $old_pid; new PID $(systemctl show smartbox-katrain.service -p MainPID --value)"
