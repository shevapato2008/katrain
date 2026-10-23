"""Fresh read-only API checks after an independently reviewed name-only revision."""
import asyncio,json,pathlib,sys,time
from copy import deepcopy
from datetime import datetime,timezone
import httpx
ROOT=pathlib.Path('/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/golaxy-hourly-release-20261024')
sys.path.insert(0,str(ROOT))
from katrain.kifu_ingest.sync import verify_album_api
from katrain.web.kifu.name_candidates import canonical_sha256
target=sys.argv[1];assert target in ('TEST','PROD')
folder=pathlib.Path('/tmp/golaxy-name-correction-proof-20261024');folder.mkdir(exist_ok=True)
original=json.loads(pathlib.Path('/tmp/golaxy-original-second-manifest.json').read_text())
capture=json.loads(pathlib.Path('/tmp/golaxy-event-correction-'+target.lower()+'-capture.json').read_text())
bundle=json.loads(pathlib.Path('/tmp/golaxy-event-correction-'+target.lower()+'-bundle.json').read_text())
native=json.loads(pathlib.Path('/tmp/golaxy-event-correction-'+target.lower()+'-native-apply.json').read_text())
summary=json.loads((ROOT/'docs/operations/releases/2026-10-24-golaxy-hourly-recovery/real-package-second.json').read_text())
assert native['status']=='applied' and native['bundle_sha256']==canonical_sha256(bundle)
assert native['spec_sha256']==capture['spec_sha256']==bundle['semantic_correction']['spec_sha256']
assert canonical_sha256(original)==summary['manifest_canonical_sha256']==capture['spec']['original_manifest_sha256']
receipt=summary['test_receipt' if target=='TEST' else 'prod_receipt']
expected={'format':'kifu-post-name-correction-api-expectations-v1','purpose':'API expectations only; not a publication manifest or new approval of the historic Qwen decision','original_manifest_sha256':canonical_sha256(original),'correction_spec_sha256':capture['spec_sha256'],'correction_bundle_sha256':canonical_sha256(bundle),'correction_native_batch_id':native['batch_id'],'games':deepcopy(original['games']),'decisions':[{'kind':d['kind'],'key':d['key'],'displays':deepcopy(d['displays'])} for d in original['decisions']]}
changed=0
for cell in capture['spec']['cells']:
 d=next(d for d in expected['decisions'] if d['kind']=='raw_event' and d['key']==cell['raw'])
 assert d['displays'][cell['lang']]==cell['old'];d['displays'][cell['lang']]=cell['new'];changed+=1
assert changed==5 and expected['games']==original['games']
expected_by_source={g['source_item_id']:g for g in original['games']}
dates={r['album_id']:expected_by_source[r['source_item_id']]['metadata']['date_played'] for r in receipt['games']}
date_checks=[]
async def hook(response):
 suffix=response.url.path.removeprefix('/api/v1/kifu/albums/')
 if suffix.isdigit() and response.status_code==200:
  await response.aread();d=response.json();assert d['date_played']==dates[int(suffix)]
  date_checks.append({'album_id':int(suffix),'lang':response.url.params.get('lang'),'date_played':d['date_played']})
async def run():
 base='https://go.sailorvoyage.top' if target=='TEST' else 'https://modelstella.com'
 started=time.monotonic();at=datetime.now(timezone.utc).isoformat()
 async with httpx.AsyncClient(event_hooks={'response':[hook]}) as client:
  result=await verify_album_api(client,base,expected,receipt,deadline=time.monotonic()+300,checkpoint_dir=None)
 assert result['status']=='verified' and result['games']==10 and len(result['checks'])==50 and len(date_checks)==50
 out={'target':target,'started_at':at,'finished_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':round(time.monotonic()-started,3),'original_manifest_sha256':canonical_sha256(original),'original_receipt_sha256':canonical_sha256(receipt),'correction_spec_sha256':capture['spec_sha256'],'correction_bundle_sha256':canonical_sha256(bundle),'native_correction_receipt':native,'verification_expectations_sha256':canonical_sha256(expected),'fresh_http_checkpoint_reuse':False,'changed_cells':5,'verification':result,'date_checks':date_checks}
 (folder/(target.lower()+'-expectations.json')).write_text(json.dumps(expected,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
 (folder/(target.lower()+'-verification.json')).write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
 print(json.dumps({'target':target,'status':result['status'],'checks':len(result['checks']),'date_checks':len(date_checks),'elapsed_seconds':out['elapsed_seconds'],'correction_spec_sha256':capture['spec_sha256'],'correction_bundle_sha256':canonical_sha256(bundle),'verification_expectations_sha256':canonical_sha256(expected)},indent=2))
asyncio.run(run())
