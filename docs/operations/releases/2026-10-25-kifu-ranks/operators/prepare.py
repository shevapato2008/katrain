from pathlib import Path
import json,hashlib,shutil,sqlite3,urllib.request,os,subprocess
release=Path('/mnt/data/smartbox-deployments/20261025-kifu-rank-fallback-93f2038a0')
runtime=Path('/root/smartbox-software/vendor/katrain');manifest=json.loads((release/'payload/manifest.json').read_text())
assert manifest['katrain_source']=='93f2038a0020d43b3090b1a71c8877980580f740'
assert manifest['smartbox_parent']=='51825c0e00a7f58544193ea6d584489252c6887e'
assert Path('/mnt/data').is_mount()
space=os.statvfs('/');assert space.f_bavail*space.f_frsize>=1024**3,'root space below 1GiB reserve'
for name,expected in manifest['files'].items():assert hashlib.sha256((release/'payload'/name).read_bytes()).hexdigest()==expected,name
baseline=json.loads((release/'device-runtime-before.json').read_text())
pid=subprocess.check_output(['systemctl','show','smartbox-katrain.service','-p','MainPID','--value'],text=True).strip()
assert pid==baseline['pid'],'KaTrain restarted since inspected baseline; recheck before release'
actual=[v.decode() for v in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if v.startswith(b'KATRAIN_BUILD_SHA=')]
assert actual==baseline['build_sha'],'actual running source changed'
for name,digest in baseline['python'].items():assert hashlib.sha256((runtime/name).read_bytes()).hexdigest()==digest,'runtime changed: '+name
rollback=release/'rollback';rollback.mkdir();(rollback/'runtime').mkdir()
absent=[];oldfiles=[]
for p in manifest['files']:
 if p.startswith('runtime/'):
  relative=Path(p[8:]);f=runtime/relative
  if not f.exists():absent.append(str(relative));continue
  dst=rollback/'runtime'/relative;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst);oldfiles.append(str(relative))
for name in ['static','static-kiosk-2d']:shutil.copytree(runtime/'katrain/web'/name,rollback/name)
for name in ['.smartbox-deployed-commit','.smartbox-release.json']:
 f=runtime/name
 if f.exists():shutil.copy2(f,rollback/name)
f=Path('/root/smartbox-software/.smartbox-deploy-revisions')
if f.exists():shutil.copy2(f,rollback/f.name)
(rollback/'runtime-files.json').write_text(json.dumps({'absent':absent,'backed_up':oldfiles},indent=2))
protected=[Path(p) for p in json.loads(Path('/mnt/data/smartbox-deployments/20261023-lobby-local-0ac3190d8/rollback/preserved-sha256.json').read_text())]
protected+=[Path('/mnt/data/weiqi/dot-katrain/kiosk-typography.json')]
protected+=list(Path('/var/lib/smartbox/hardware/vision').rglob('*.json'))+list(Path('/var/lib/smartbox/hardware/vision').rglob('*.npz'))
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(protected)) if p.is_file()}
(rollback/'preserved-sha256.json').write_text(json.dumps(hashes,indent=2))
source=sqlite3.connect('/mnt/data/weiqi/weiqi-web.db');dest=sqlite3.connect(rollback/'weiqi-web.db');source.backup(dest);dest.close();source.close()
services={}
for name in ['smartbox-katrain.service','smartbox-kiosk.service','smartbox-mode-go.target']:
 services[name]=subprocess.check_output(['systemctl','show',name,'-p','MainPID','-p','ActiveState','-p','ActiveEnterTimestamp'],text=True).strip()
(release/'before-services.json').write_text(json.dumps(services,indent=2))
print(json.dumps({'validated_payload_files':len(manifest['files']),'runtime_backup_files':len(oldfiles),'new_runtime_files':len(absent),'preserved_files':len(hashes),'database_backup_bytes':(rollback/'weiqi-web.db').stat().st_size}))

(release/'typography-before.json').write_bytes(__import__('urllib.request',fromlist=['urlopen']).urlopen('http://127.0.0.1:8081/api/v1/kiosk-preferences/typography').read())
