"""Finite reviewed name-only correction using the existing native bundle API.

No source fetching, model calls, SGF import, frozen-package rewrite or direct
name SQL update. Prepare is read-only apart from local artifacts. Apply requires
the independently reviewed exact capture/spec and the native CAS/dry-run gates.
"""
from contextlib import ExitStack,contextmanager
from copy import deepcopy
from datetime import datetime,timezone
import argparse,hashlib,json,pathlib
from sqlalchemy import select,text
from katrain.web.core.db import engine
from katrain.web.core.models_db import KifuAlbum,KifuRawEventValue,KifuRawEventName,KifuNameResearchEvidence,KifuNameBatch
from katrain.web.kifu import name_batch,name_first_pass
from katrain.web.kifu.name_evidence import load_registry,registry_sha256
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.kifu_ingest.catalog import _publication_guard
from katrain.cron.jobs.kifu_ingest import _session_lock
from katrain.kifu_ingest.staging import staging_writer_lock

RAW_OZA='第74期王座战挑战赛5番棋1局'
RAW_GUKSU='第12届国手山脉杯世界赛决赛 申真谞 VS 李维清'
RAW_WU_FINAL='第9届吴清源杯世界女子公开赛国际预选决赛'
RAW_WU_ROUND='第9届吴清源杯世界女子围棋公开赛预选赛第2轮'
SPEC={'version':'bounded-golaxy-event-semantic-correction-20261024-v1','original_manifest_sha256':'57a579a34b83134e7cca5fa51836e3cea4dfa69b00177d3cdf50abd4668a60c5','cells':[
 {'raw':RAW_OZA,'lang':'jp','old':'第74期王座戦挑戦者決定戦5番勝負第1局','new':'第74期王座戦挑戦手合5番勝負第1局','sources':['91574352']},
 {'raw':RAW_OZA,'lang':'ko','old':'제74기 왕좌전 도전자 결정전 5선승부 1국','new':'제74기 왕좌전 도전5번기 제1국','sources':['91574352']},
 {'raw':RAW_GUKSU,'lang':'ko','old':'제12회 국수산맥배 세계전 결승 신진서 VS 이유청','new':'제12회 국수산맥배 세계전 결승 신진서 VS 리웨이칭','sources':['91449763']},
 {'raw':RAW_WU_FINAL,'lang':'ko','old':'제9회 우청원배 세계 여자 오픈전 국제 예선 결승','new':'제9회 오청원배 세계 여자 오픈전 국제 예선 결승','sources':['91468818','91464854','91467988']},
 {'raw':RAW_WU_ROUND,'lang':'ko','old':'제9회 우청원배 세계 여자 바둑 오픈 예선 2라운드','new':'제9회 오청원배 세계 여자 바둑 오픈 예선 2라운드','sources':['91496863']}],
 'official_references':['https://www.nihonkiin.or.jp/match_news/match_info/74_1.html','https://www.nihonkiin.or.jp/match_news/match_result/74_17.html','https://www.baduk.or.kr/record/schedule_in.asp','https://www.baduk.or.kr/record/diary_in.asp?foreignKey=10001366'],
 'semantic_review':'astra_deployed_flow_review independently approved these exact five texts; native preimage/bundle approval is separate'}
PRODUCER='codex-golaxy-correction-producer-20261024'
REVIEWER='/root/golaxy_hourly_kifu_sync_fix/astra_deployed_flow_review'
def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(p.read_text())
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,sort_keys=True,default=str)+'\n')
@contextmanager
def locked(target):
 with ExitStack() as stack:
  acquired=stack.enter_context(_session_lock(engine))
  if not acquired:raise RuntimeError('another source/maintenance writer is active')
  if target=='TEST':stack.enter_context(staging_writer_lock(pathlib.Path('/app/data/kifu_ingest')))
  yield
def prepare(directory,target):
 directory.mkdir(parents=True,exist_ok=True)
 assert not (directory/'capture.json').exists(),'never overwrite a reviewed capture'
 registry=load_registry(directory/'registry-input.json');inventory=build_inventory(engine)
 capture={'target':target,'captured_at':now(),'spec':SPEC,'spec_sha256':canonical_sha256(SPEC),'inventory_sha256':inventory['sha256'],'catalog_sha256':name_batch.catalog_snapshot_sha(engine),'registry_sha256':registry_sha256(registry),'owners':[],'cells':[]}
 with engine.connect() as c:
  if engine.dialect.name=='postgresql':c.execute(text('SET TRANSACTION READ ONLY'))
  for raw in sorted({v['raw'] for v in SPEC['cells']}):
   owner_id=c.scalar(select(KifuRawEventValue.id).where(KifuRawEventValue.raw_value==raw));assert owner_id
   owner={'kind':'raw_event','id':owner_id};image=name_batch._image(c,KifuRawEventValue.__table__,owner_id)
   scope=name_first_pass.raw_scope_rows(c,raw)
   assert scope and all(s['slot']=='event' and s['approved'] and s['duplicate_of_id'] is None and s['list_hidden_reason'] is None for s in scope)
   expected={f'data/kifu-album/19x19/{i}.sgf' for v in SPEC['cells'] if v['raw']==raw for i in v['sources']}
   assert {s['source_path'] for s in scope}==expected,'correction cannot expand beyond the six declared games'
   ids=sorted({s['album_id'] for s in scope})
   capture['owners'].append({'owner':owner,'preimage':image,'occurrence_album_ids':ids,'occurrence_sha256':canonical_sha256(ids),'raw_scope':scope})
  for spec in SPEC['cells']:
   dec=next(x for x in capture['owners'] if x['preimage']['raw_value']==spec['raw']);owner=dec['owner']
   row=c.execute(select(KifuRawEventName.id).where(KifuRawEventName.raw_event_id==owner['id'],KifuRawEventName.lang==spec['lang'])).one()
   name=name_batch._image(c,KifuRawEventName.__table__,row.id);assert name['display_name']==spec['old'] and name['status']=='verified'
   evidence=name_batch._image(c,KifuNameResearchEvidence.__table__,name['evidence_id']);payload=evidence['research_payload'];candidate=payload['candidate'];batch_id=payload['first_pass']['batch_id']
   batch=name_batch._image(c,KifuNameBatch.__table__,batch_id);assert batch['status']=='applied' and canonical_sha256(batch['reviewed_artifact']['bundle'])==batch['bundle_sha256']
   capture['cells'].append({'spec':spec,'owner':owner,'name':name,'evidence':evidence,'prior_candidate':candidate,'prior_research':payload['research'],'prior_batch_id':batch_id,'prior_bundle_sha256':batch['bundle_sha256']})
 capture['bound_at']=now();write(directory/'capture.json',capture);write(directory/'inventory.json',inventory);write(directory/'registry.json',registry)
 return {'target':target,'spec_sha256':capture['spec_sha256'],'capture_sha256':canonical_sha256(capture),'inventory_sha256':inventory['sha256'],'cell_count':len(capture['cells']),'game_count':len({i for c in SPEC['cells'] for i in c['sources']}),'captured_at':capture['captured_at'],'bound_at':capture['bound_at'],'cells':[{'raw':c['spec']['raw'],'lang':c['spec']['lang'],'old':c['name']['display_name'],'new':c['spec']['new'],'owner':c['owner'],'name_sha256':canonical_sha256(c['name']),'evidence_sha256':canonical_sha256(c['evidence']),'prior_batch_id':c['prior_batch_id']} for c in capture['cells']]}
def finalize(directory):
 assert not (directory/'bundle.json').exists(),'never overwrite a finalized correction bundle'
 capture=read(directory/'capture.json');approval=read(directory/'independent-approval.json');registry=read(directory/'registry.json')
 assert approval['decision']=='approved' and approval['reviewer_id']==REVIEWER and approval['spec_sha256']==canonical_sha256(SPEC)==capture['spec_sha256']
 assert approval['capture_sha256']==canonical_sha256(capture) and datetime.fromisoformat(approval['reviewed_at'])>=datetime.fromisoformat(capture['bound_at'])
 candidates=[];records=[]
 for cell in capture['cells']:
  old=cell['prior_candidate'];spec=cell['spec'];owner=cell['owner'];name=cell['name']
  research=deepcopy(cell['prior_research']);research.pop('incremental_binding',None)
  research.update(registry_version=registry['version'],registry_sha256=registry_sha256(registry),candidate_name=spec['new'],producer_id=PRODUCER,producer_model='codex-agent-session',generation={'method':'translation'},sources=[],review_status='pending')
  research['raw_scope']={'raw_value':spec['raw'],'slots':next(x['raw_scope'] for x in capture['owners'] if x['owner']==owner)}
  research['semantic_correction_basis']={'spec_sha256':capture['spec_sha256'],'official_references':SPEC['official_references'],'review_record_sha256':canonical_sha256(approval),'note':'Generated translation independently reviewed against official stage/person terminology; not a claim of verified Korean primary text.'}
  marker={'version':'generated-raw-event-semantic-correction-v1','owner':owner,'lang':spec['lang'],'raw_value':spec['raw'],'name_preimage_sha256':canonical_sha256(name),'prior_name_revision':name['revision'],'prior_candidate_sha256':canonical_sha256(old),'prior_evidence_sha256':canonical_sha256(cell['evidence']),'prior_batch_id':cell['prior_batch_id'],'prior_bundle_sha256':cell['prior_bundle_sha256']}
  candidate=deepcopy(old);candidate.pop('preimage_binding',None)
  candidate.update(display_name=spec['new'],research_sha256=canonical_sha256(research),name_preimage_sha256=marker['name_preimage_sha256'],first_pass_correction=marker,producer_id=PRODUCER,producer_model='codex-agent-session',produced_at=capture['captured_at'],review_status='approved',reviewer_id=REVIEWER,reviewer_model='gpt-6-astra',reviewed_at=approval['reviewed_at'],review_conclusion='approved_first_pass_display_and_source')
  candidate['generated_review']={'decision':'approve_generated_first_pass',**{k:candidate[k] for k in ['owner','lang','display_name','research_sha256','reviewer_id','reviewer_model','reviewed_at']}}
  candidate['preimage_binding']={'actor_id':PRODUCER,'actor_model':'codex-agent-session','captured_at':capture['captured_at'],'bound_at':capture['bound_at'],'name_preimage_sha256':candidate['name_preimage_sha256'],'source_candidate_sha256':canonical_sha256(candidate),'capture_sha256':canonical_sha256(capture)}
  records.append(research);candidates.append(candidate)
 owners=[{k:v for k,v in d.items() if k!='raw_scope'} for d in capture['owners']];members=[{'owner':c['owner'],'lang':c['lang'],'raw_value':c['raw_value']} for c in candidates]
 inv=read(directory/'inventory.json')
 bundle={'bundle_format':2,'inventory_format':inv['inventory_format'],'inventory_sha256':inv['sha256'],'catalog_sha256':capture['catalog_sha256'],'registry_version':registry['version'],'registry_sha256':registry_sha256(registry),'rule_version':'bounded-golaxy-event-semantic-correction-v1','members':members,'member_set_sha256':canonical_sha256(members),'owners':owners,'owner_set_sha256':canonical_sha256(owners),'candidates':candidates,'album_links':[],'link_set_sha256':canonical_sha256([]),'semantic_correction':{'spec_sha256':capture['spec_sha256'],'capture_sha256':canonical_sha256(capture),'approval_sha256':canonical_sha256(approval),'original_manifest_sha256':SPEC['original_manifest_sha256']}}
 write(directory/'bundle.json',bundle);write(directory/'research.json',records)
 return {'target':capture['target'],'bundle_sha256':canonical_sha256(bundle),'spec_sha256':capture['spec_sha256'],'capture_sha256':canonical_sha256(capture),'candidates':len(candidates)}
def validate_or_apply(directory,apply):
 bundle=read(directory/'bundle.json');registry=read(directory/'registry.json');inventory=read(directory/'inventory.json');records=read(directory/'research.json')
 approval=read(directory/'independent-approval.json');capture=read(directory/'capture.json')
 assert approval['capture_sha256']==canonical_sha256(capture) and approval['decision']=='approved'
 digest=canonical_sha256(bundle)
 trusted_digest=digest
 if apply:
  trusted=read(directory/'bundle-apply-approval.json')
  assert trusted['decision']=='approved' and trusted['reviewer_id']==REVIEWER
  assert trusted['bundle_sha256']==digest and trusted['spec_sha256']==capture['spec_sha256'] and trusted['target']==capture['target']
  trusted_digest=trusted['bundle_sha256']
 with _publication_guard(engine):
  if apply:
   with engine.connect() as c:previous=c.scalar(select(KifuNameBatch.status).where(KifuNameBatch.bundle_sha256==digest))
   if previous is not None:
    result=name_batch.apply_bundle(engine,bundle,registry,inventory,records,expected_bundle_sha256=trusted_digest)
    write(directory/'native-replay-receipt.json',result)
    return {'bundle_sha256':digest,'spec_sha256':capture['spec_sha256'],**result}
  preview=name_batch.dry_run_bundle(engine,bundle,registry,inventory,records,expected_bundle_sha256=digest)
  assert preview['ready'] and preview['write_ready']
  write(directory/'native-dry-run.json',preview)
  if not apply:return preview
  result=name_batch.apply_bundle(engine,bundle,registry,inventory,records,expected_bundle_sha256=trusted_digest)
  write(directory/'native-apply-receipt.json',result)
  return {'bundle_sha256':digest,'spec_sha256':capture['spec_sha256'],**result}
parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['prepare','finalize','dry-run','apply']);parser.add_argument('--target',choices=['TEST','PROD'],required=True);parser.add_argument('--directory',type=pathlib.Path,required=True);args=parser.parse_args()
with locked(args.target):
 if args.operation=='prepare':result=prepare(args.directory,args.target);write(args.directory/'prepared-summary.json',result)
 else:
  assert read(args.directory/'capture.json')['target']==args.target
  if args.operation=='finalize':result=finalize(args.directory);write(args.directory/'finalized-summary.json',result)
  else:result=validate_or_apply(args.directory,args.operation=='apply')
print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
