"""Assemble unsigned format-1 execution bundles after root's fresh binding approval."""
import gzip,hashlib,importlib.util,json,shlex,subprocess
from pathlib import Path
from katrain.web.kifu.name_candidates import canonical_sha256,validate_bundle
from katrain.web.kifu.name_evidence import validate_positive_ja_ko_candidate
D=Path(__file__).parent
S=importlib.util.spec_from_file_location('capture_context',D/'capture-post589-context.py')
M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
REMOTE=r'''
import gzip,hashlib,json,sys
from pathlib import Path
from katrain.web.kifu.name_candidates import canonical_sha256,validate_bundle
from katrain.web.kifu.name_evidence import validate_positive_ja_ko_candidate
x=json.loads(gzip.decompress(sys.stdin.buffer.read()))
for row,research in zip(x['bundle']['candidates'],x['research']):
 validate_positive_ja_ko_candidate(row,research,x['registry'])
report=validate_bundle(x['bundle'],x['registry'],x['inventory'],x['research'],approved_name_snapshot=x['snapshot'])
assert report['ready']and report['write_ready']and report['approved']==20,report
files=['identity.py','name_candidates.py','name_evidence.py','name_orthographic.py','name_batch.py','name_inventory.py']
code={f:hashlib.sha256(Path('/app/katrain/web/kifu',f).read_bytes()).hexdigest()for f in files}
assert code==x['expected_code_sha256']
print(json.dumps({'validation':report,'bundle_sha256':canonical_sha256(x['bundle']),'actual_native_r2_code_sha256':code,'offline_native_product_validation':True},sort_keys=True))
'''
def save(name,value,compressed=True):
 raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 if compressed:(D/name).write_bytes(gzip.compress(raw,mtime=0))
 else:(D/name).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def assemble(env):
 context=json.load(gzip.open(D/f'{env}-post589-global-context.json.gz','rt'))
 capture=json.load(gzip.open(D/'post589'/f'{env}-ko20-current-preimages.json.gz','rt'))
 registry=context['source_registry']['registry']
 assert canonical_sha256(registry)==canonical_sha256(json.loads((D/'source-registry-reused.json').read_text()))
 research=json.load(gzip.open(D/f'{env}-ko20-unsigned-research.json.gz','rt'))
 approved_path=D/f'{env}-ko20-bound-candidates.approved.json';approval_bytes=approved_path.read_bytes()
 candidates=json.loads(approval_bytes)
 request=json.loads((D/f'{env}-boundcandidate-review-request.json').read_text())
 assert len(candidates)==len(research)==20
 byowner={r['id']:r for r in capture['rows']}
 for row,pending,record in zip(candidates,request['candidates'],research):
  pre=byowner[row['owner']['id']]
  assert row['preimage_binding']==pending['preimage_binding']
  assert row['name_preimage_sha256']==pre['target_name_preimage_sha256']
  assert row['display_name']==pre['target_name_preimage']['display_name']
  for key in ['owner','lang','display_name','decision_kind','generation_rule_version','research_sha256','producer_id','producer_model','produced_at']:
   assert row[key]==pending[key]
  validate_positive_ja_ko_candidate(row,record,registry)
 inventory=context['inventory'];snapshot=context['approved_name_snapshot']
 members=[{'owner':row['owner'],'lang':'ko'}for row in candidates]
 bundle={'bundle_format':1,'inventory_format':inventory['inventory_format'],'inventory_sha256':inventory['sha256'],
  'registry_version':registry['version'],'registry_sha256':canonical_sha256(registry),'rule_version':'candidate-v1',
  'catalog_sha256':context['catalog_sha256'],'members':members,'member_set_sha256':canonical_sha256(members),'candidates':candidates}
 report=validate_bundle(bundle,registry,inventory,research,approved_name_snapshot=snapshot)
 assert report['ready']and report['write_ready']and report['approved']==20,report
 payload={'bundle':bundle,'registry':registry,'inventory':inventory,'research':research,'snapshot':snapshot,
  'expected_code_sha256':context['actual_r2_code_sha256']}
 host,container,image=M.M.HOSTS[env]
 body=gzip.compress(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(),mtime=0)
 command=f'docker run --rm --read-only --network none -i --entrypoint python {image} -c {shlex.quote(REMOTE)}'
 result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',host,command],input=body,capture_output=True)
 if result.returncode:raise RuntimeError(env+': '+result.stderr.decode(errors='replace')[-1600:])
 actual=json.loads(result.stdout)
 assert actual['bundle_sha256']==canonical_sha256(bundle)and actual['validation']==report
 assert approved_path.read_bytes()==approval_bytes
 save(f'{env}-ko20-unsigned-bundle.json.gz',bundle)
 save(f'{env}-ko20-inventory.json.gz',inventory)
 save(f'{env}-ko20-approved-name-snapshot.json.gz',snapshot)
 save(f'{env}-ko20-source-registry.json',registry,False)
 save(f'{env}-ko20-final-unsigned-summary.json',{'environment':env,'status':'root_sources_and_bindings_approved_outer_execution_unsigned',
  'bundle_sha256':canonical_sha256(bundle),'distinct_players':20,'existing_name_updates':20,'new_evidence_rows':20,
  'current_ko_name_bytes_preserved':True,'expected_new_full_five_after_apply_and_verify':20,
  'game_slots':capture['game_slots'],'unique_albums':capture['unique_albums'],'validation':report,
  'native_r2_validation':actual,'context_refreshed_at':context['context_refreshed_at'],
  'member_captured_at':capture['captured_at'],'inventory_sha256':inventory['sha256'],
  'catalog_sha256':context['catalog_sha256'],'registry_sha256':canonical_sha256(registry),
  'approved_name_snapshot_sha256':canonical_sha256(snapshot),'preceding_applied_batch':context['actual_preceding_batch']},False)
 print(env,'PASS ready20/write_ready=true native r2',canonical_sha256(bundle),flush=True)
if __name__=='__main__':
 import sys
 for env in (sys.argv[1:]or['PROD','TEST']):assemble(env)
