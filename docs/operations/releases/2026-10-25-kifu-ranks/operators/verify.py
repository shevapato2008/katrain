from pathlib import Path
import hashlib,json,re,subprocess,urllib.request
RELEASE=Path('/mnt/data/smartbox-deployments/20261025-kifu-rank-fallback-93f2038a0');ROOT=Path('/root/smartbox-software/vendor/katrain')
SHA='93f2038a0020d43b3090b1a71c8877980580f740';PARENT='51825c0e00a7f58544193ea6d584489252c6887e';BASE='http://127.0.0.1:8081'
def get(path):
 with urllib.request.urlopen(BASE+path,timeout=30) as response:return json.load(response)
m=json.loads((RELEASE/'manifest.json').read_text())
for name,h in m['files'].items():
 f=ROOT/Path(name).relative_to('runtime') if name.startswith('runtime/') else ROOT/'katrain/web'/name
 assert hashlib.sha256(f.read_bytes()).hexdigest()==h,name
protected=json.loads((RELEASE/'rollback/preserved-sha256.json').read_text())
for name,h in protected.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name
pid=subprocess.check_output(['systemctl','show','smartbox-katrain.service','-p','MainPID','--value'],text=True).strip()
assert ('KATRAIN_BUILD_SHA='+SHA).encode() in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0')
assert json.loads((ROOT/'.smartbox-release.json').read_text())['katrain']==SHA
assert 'main='+PARENT in (ROOT.parent.parent/'.smartbox-deploy-revisions').read_text()
assert get('/api/v1/kiosk-preferences/typography')==json.loads((RELEASE/'typography-before.json').read_text())
health=get('/api/v1/health');vision=get('/api/v1/vision/status')
assert health['status']=='ok' and health.get('engines',{}).get('local')=='reachable'
assert all(vision.get(k) is True for k in ['enabled','camera_connected','camera_ready','model_ready'])
# Read-only checks retain the previous published tutorial policy, never write source content.
raw=get('/api/v1/tsumego/problems/124386');variant=get('/api/v1/tsumego/problems/124386?board_variant=kiosk19')
assert raw['boardSize']==9 and variant['boardSize']==19 and variant['board_variant']['status']=='adapted'
retained=get('/api/v1/tsumego/problems/66104?board_variant=kiosk19');assert retained['board_variant']['status']=='unavailable'
entries=[]
for route in ['/kiosk/play','/galaxy/tutorial']:
 html=urllib.request.urlopen(BASE+route,timeout=10).read();script=re.search(rb'<script[^>]*type="module"[^>]*src="([^"]+)"',html).group(1).decode()
 body=urllib.request.urlopen(BASE+script,timeout=10).read()
 matches=[name for name in ['static','static-kiosk-2d'] if (ROOT/'katrain/web'/name/script.lstrip('/')).is_file() and body==(ROOT/'katrain/web'/name/script.lstrip('/')).read_bytes()]
 assert matches,script
 entries.append({'route':route,'entry':script,'served_builds':matches,'sha256':hashlib.sha256(body).hexdigest()})
before=json.loads((RELEASE/'before-services.json').read_text())
for name in ['smartbox-kiosk.service','smartbox-mode-go.target']:
 assert subprocess.check_output(['systemctl','show',name,'-p','MainPID','-p','ActiveState','-p','ActiveEnterTimestamp'],text=True).strip()==before[name]
result={'source':SHA,'parent':PARENT,'pid':pid,'manifest_files':len(m['files']),'protected_files_unchanged':len(protected),'typography':get('/api/v1/kiosk-preferences/typography'),'health':health,'vision':vision,'previous_policy_preserved':True,'served_entries':entries,'other_services_unchanged':True,'physical_board_actions':False}
(RELEASE/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['source','parent','pid','manifest_files','protected_files_unchanged','served_entries']},ensure_ascii=False))
