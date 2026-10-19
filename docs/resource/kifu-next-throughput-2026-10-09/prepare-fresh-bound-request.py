"""Create current unsigned bindings; keep archived root source approvals byte exact."""
import copy,datetime,gzip,hashlib,json
from pathlib import Path
from katrain.web.kifu.name_candidates import canonical_sha256
D=Path(__file__).parent
outputs=[]
import sys
for env in (sys.argv[1:] or ['PROD','TEST']):
 approved_path=D/f'{env}-ko20-candidates.approved.json';old_approved_bytes=approved_path.read_bytes()
 original=json.loads(old_approved_bytes)
 capture_path=D/'post589'/f'{env}-ko20-current-preimages.json.gz'
 capture=json.load(gzip.open(capture_path,'rt'))
 context=json.load(gzip.open(D/f'{env}-post589-global-context.json.gz','rt'))
 captured_sha=hashlib.sha256(capture_path.read_bytes()).hexdigest()
 byid={r['id']:r for r in capture['rows']}
 bound_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
 rows=[]
 for original_row in original:
  row=copy.deepcopy(original_row);pre=byid[row['owner']['id']]
  assert row['name_preimage_sha256']==pre['target_name_preimage_sha256']
  assert row['display_name']==pre['target_name_preimage']['display_name']
  row['preimage_binding']={'actor_id':'/root/next_batch_source_recovery','actor_model':'gpt-6.1-sol',
    'captured_at':capture['captured_at'],'bound_at':bound_at,'name_preimage_sha256':row['name_preimage_sha256'],
    'source_candidate_sha256':canonical_sha256(original_row),'capture_sha256':captured_sha}
  row['review_status']='pending'
  for key in ['reviewer_id','reviewer_model','reviewed_at','review_conclusion']:row[key]=''
  review=row['generated_review'];review['decision']='pending'
  for key in ['reviewer_id','reviewer_model','reviewed_at']:review[key]=''
  for key in ['identity_input_review','rule_review','output_review']:review[key]='pending'
  review['reason']='Pending review of actual current preimage binding; original source/reading/rule/output approval remains archived unchanged.'
  rows.append(row)
 request={'request_kind':'post589_actual_preimage_binding_review','environment':env,'review_status':'pending',
  'bound_at':bound_at,'binding_actor':'/root/next_batch_source_recovery','binding_model':'gpt-6.1-sol',
  'prior_source_approval_file':approved_path.name,'prior_source_approved_candidates_sha256':canonical_sha256(original),
  'prior_root_source_review_file':'root-ko20-source-review.json','candidates':rows,
  'actual_capture_file':str(capture_path.relative_to(D)),'actual_capture_file_sha256':captured_sha,
  'actual_captured_at':capture['captured_at'],'context_refreshed_at':context['context_refreshed_at'],
  'catalog_sha256':context['catalog_sha256'],'inventory_sha256':context['inventory']['sha256'],
  'approved_name_snapshot_sha256':canonical_sha256(context['approved_name_snapshot']),
  'owners':[{'owner':{'kind':'player','id':pre['id']},'preimage':pre['owner_preimage']}for pre in capture['rows']],
  'member_names_source_readings_rule_and_output_unchanged':True,'current_name_and_evidence_preimages_unchanged':True,
  'member_game_scope_unchanged':True,'actual_preceding_batch':context['actual_preceding_batch'],
  'research_file':f'{env}-ko20-unsigned-research.json.gz','expected_existing_name_updates':20,
  'expected_new_evidence_rows':20,'game_slots':capture['game_slots'],'unique_albums':capture['unique_albums']}
 (D/f'{env}-boundcandidate-review-request.json').write_text(json.dumps(request,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
 assert approved_path.read_bytes()==old_approved_bytes
 outputs.append({'environment':env,'count':len(rows),'request_sha256':canonical_sha256(request),
    'bound_at':bound_at,'captured_at':capture['captured_at']})
print(json.dumps(outputs,ensure_ascii=False))
