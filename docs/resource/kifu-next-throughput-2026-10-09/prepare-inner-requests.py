"""Bind unsigned research/candidates to actual READ ONLY target preimages. No approval."""
import copy, datetime, gzip, hashlib, json
from pathlib import Path
from katrain.web.kifu.name_evidence import registry_sha256, validate_research_record
D=Path(__file__).parent
records=json.load(gzip.open(D/'positive-ko20-unsigned-research.json.gz','rt'))
registry=json.loads((D/'source-registry-reused.json').read_text())
scopes={};summaries={}
for env in ['PROD','TEST']:
 capture_path=D/f'{env}-ko20-current-preimages.json.gz'
 capture=json.load(gzip.open(capture_path,'rt'))
 capture_hash=hashlib.sha256(capture_path.read_bytes()).hexdigest()
 byprod={r['prod_id']:r for r in capture['rows']}
 rebound=[];candidates=[];requirements=[];scopes[env]=[]
 for research in records:
  original=research['owner']['id'];pre=byprod[original];owner={'kind':'player','id':pre['id']}
  r=copy.deepcopy(research);r['owner']=owner;r['positive_generation']['identity']['owner']=owner
  for check in r['source_checks']:check['owner']=owner
  validate_research_record(r,registry)
  rebound.append(r)
  row={'owner':owner,'lang':'ko','display_name':r['candidate_name'],'decision_kind':'generated',
   'generation_rule_version':r['generation_rule_version'],'review_status':'pending',
   'producer_id':r['producer_id'],'producer_model':r['producer_model'],'produced_at':r['produced_at'],
   'research_sha256':registry_sha256(r),'name_preimage_sha256':pre['target_name_preimage_sha256']}
  assert row['display_name']==pre['target_name_preimage']['display_name']
  candidates.append(row)
  requirements.append({'owner':owner,'lang':'ko','display_name':row['display_name'],
    'original_name':r['original_name'],'reading':r['reading'],'reading_basis_url':r['reading_basis_url'],
    'research_sha256':row['research_sha256'],
    'positive_generation_sha256':registry_sha256(r['positive_generation']),
    'required_review_conclusion':'approved_generated_display_and_rule',
    'required_generation_decision':'approve_generated','status':'pending_independent_root_review'})
  for g in pre['linked_album_members']:
   scopes[env].append((original,g['id'],g['side'],g['sgf_utf8_sha256'],str(g['date_played']),g['player_black'],g['player_white'],g['black_rank'],g['white_rank'],g['result']))
 research_name=f'{env}-ko20-unsigned-research.json.gz'
 raw=json.dumps(rebound,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 (D/research_name).write_bytes(gzip.compress(raw,mtime=0))
 request={'request_kind':'normative_ja_ko_existing_name_proof_restoration','environment':env,
  'review_status':'pending','source_registry_sha256':registry_sha256(registry),
  'research_file':research_name,'research_array_sha256':hashlib.sha256(raw).hexdigest(),
  'candidates':candidates,'generated_review_requests':requirements,
  'owners':[{'owner':{'kind':'player','id':pre['id']},'preimage':pre['owner_preimage']}for pre in capture['rows']],
  'read_only_capture_file':capture_path.name,'read_only_capture_file_sha256':capture_hash,
  'read_only_captured_at':capture['captured_at'],'capture_actor':'/root/next_batch_source_recovery',
  'capture_model':'gpt-6.1-sol','current_name_bytes_preserved':True,
  'current_ko_strictly_unqualified_members':20,'expected_new_full_five_if_applied_and_verified':20,
  'game_slots':capture['game_slots'],'unique_albums':capture['unique_albums'],
  'global_context_status':'awaiting_PROD589_and_TEST589_after_state_before_root_signed_bundle'}
 path=D/f'{env}-ko20-inner-request-unsigned.json'
 path.write_text(json.dumps(request,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
 summaries[env]={'count':len(rebound),'candidate_request_sha256':registry_sha256(request),
  'research_array_sha256':request['research_array_sha256'],'capture_sha256':capture_hash,
  'game_slots':capture['game_slots'],'unique_albums':capture['unique_albums'],'captured_at':capture['captured_at']}
assert sorted(scopes['PROD'])==sorted(scopes['TEST'])
result={'environments':summaries,'member_sgf_side_native_rank_result_cross_environment_equal':True,
 'member_scope_sha256':registry_sha256(sorted(scopes['PROD'])),'review_status':'unsigned_pending_independent_review',
 'global_context_status':'awaiting_after_589_snapshot','held_owners':[6496,5244,4499,3900]}
(D/'unsigned-inner-requests-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
