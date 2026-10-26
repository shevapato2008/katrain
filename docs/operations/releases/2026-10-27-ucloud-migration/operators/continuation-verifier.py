#!/usr/bin/env python3
"""One finite continuation: verify existing import, sign separately, then stopped-PG configs."""
import argparse,copy,datetime,hashlib,hmac,importlib.util,json,os,pathlib,re,secrets,stat,subprocess,sys,time
BASE=pathlib.Path('/var/lib/ucloud-migration-20261027');FD=BASE/'final-data'
OLD='migrate-final-20261027-0330';CONT='migrate-continue-20261027-0420';CR=BASE/('continuation-'+CONT)
OLD_FENCE='0249da573aa48cc2ff4b3cd7ea7dc5bbd02305edbcd490295801c7a992051225'
OLD_MANIFEST='3b8d2b9da4ebab869c8a0b5745aa749eda95fa428d09a478f3cef78e983a8a9e'
PROOF_SHA='38aeaa7ee70560f0c76d2d8ad27285b52fe0c2aa7b6bcf52b58e89f3a14b98eb'
FROZEN_OP_SHA='dbcfc648f51b1dd7ef32cd74fedb9c0f9cfb13afb06f224c729da2d4a87763f2'
DEVELOP='e9b4d3ecce03b3269f12922a476fd6d6c6545547'
LOCK_CODE='3486adef8be01f7c707cb879553bef11668d32e4c89de637fc0a357126045aa7'
TEST_HELPER='cf573290ff98854f420565e0789410345106edec8cef26442b97aa1b32ed3274'
EIGHT='4c366c8fe74cb695bb40e9813b01a0708d90e7d0ca507bf4029146a1fb529b43'
CONTROL='ba7a1af83ba74bf50a3271f7176c939ca9d626afa0b8578be638e61cf8dcaa94'
IMAGE='sha256:9604d05e4e096b4c97966e6c850492c87d60fe9fff1039c3fe94f67af081c08d'
FOUR={('katrain-ucloud-postgres-1','katrain_db'),('katrain-ucloud-postgres-1','katrain_prod_20260725'),('platform-postgres','lobby'),('pitch-booking-postgres-1','pitch')}
os.umask(0o077)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def need(x,why):
 if not x:raise RuntimeError(why)
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def control_hash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load(path,expected=None):
 p=pathlib.Path(path);s=p.lstat();need(stat.S_ISREG(s.st_mode) and s.st_uid==0 and stat.S_IMODE(s.st_mode)==0o600,'root_regular_0600_required:'+p.name)
 if expected:need(sha(p)==expected,'file_sha_mismatch:'+p.name)
 return json.loads(p.read_text())
def save(path,value):
 p=pathlib.Path(path);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n');tmp.chmod(0o600);tmp.replace(p)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def original_schema_sha(data):
 # Exactly the frozen operator's existing random psql restrict-token policy; no expression rewrite.
 return hashlib.sha256(re.sub(rb'(?m)^\\(?:un)?restrict [^\r\n]+',lambda _:b'\\restrict <TOKEN>',data)).hexdigest()
def newargs(a):return argparse.Namespace(window_id=CONT,fence_file=str(BASE/('source-fence-'+CONT+'.private.json')),fence_sha=a.new_fence_sha,go='APPROVED:'+CONT)
def history(a):
 need(pathlib.Path(a.original_manifest_root)==BASE/('final-db-'+OLD),'fixed_original_manifest_root_required')
 oldf=load(BASE/('source-fence-'+OLD+'.private.json'),OLD_FENCE)
 m=load(pathlib.Path(a.original_manifest_root)/'manifest.json',OLD_MANIFEST)
 need(m['WindowID']==OLD and m['SourceFenceSHA256']==OLD_FENCE and m['Status']=='verified_final_export','original_manifest_chain_mismatch')
 failed=load(FD/('apply-'+OLD)/'receipt.private.json',a.failed_apply_sha)
 need(failed['Status']=='failed_final_apply' and failed['WindowID']==OLD and failed['SourceFenceSHA256']==OLD_FENCE and failed['ManifestSHA256']==OLD_MANIFEST,'original_failed_receipt_chain_mismatch')
 expected={(d['container'],d['database']) for d in m['databases']};actual=[(d['container'],d['database']) for d in failed['databases']]
 need(len(expected)==len(actual)==13 and set(actual)==expected and all(d['restore_exit']==0 for d in failed['databases']),'exact_original_13_restore_exit0_required')
 tr=load(FD/('transfer-'+OLD+'.private.json'),a.transfer_receipt_sha)
 need(tr['Status']=='verified_final_archives' and tr['WindowID']==OLD and tr['SourceFenceSHA256']==OLD_FENCE and tr['ManifestSHA256']==OLD_MANIFEST,'original_transfer_chain_mismatch')
 proofpath=FD/('schema-semantic-proof-aggregate-'+OLD+'.private.json');need(a.proof_sha==PROOF_SHA,'fixed_finite_backend_proof_required');proof=load(proofpath,PROOF_SHA)
 need(proof['Status']=='readonly_67checks_1index_backend_proof_passed_not_final_verification' and proof['Checks']==67 and proof['Indexes']==1,'finite_backend_proof_not_passed')
 objs=[o for r in proof['Results'] for o in r['Objects']]
 need(len(objs)==68 and all(o['MetadataEqual'] and o['OutputPresentNotPruned'] and o['CanonicalOutputEqual'] and o['FullStablePlanEqual'] and o['OverlappingAttemptsEqual'] for o in objs),'finite_backend_object_proof_incomplete')
 need({(r['Container'],r['Database']) for r in proof['Results']}==FOUR and all(r['UnchangedDDLExactMatch'] for r in proof['Results']),'four_schema_proof_scope_mismatch')
 need(sha(FD/'assemble-schema-proof.py')==proof['ValidatorSHA256'] and sha(FD/'schema-semantic-proof.py')==proof['BackendValidatorSHA256'] and sha(FD/'schema-semantic-proof.first-network-attempt.py')==proof['FirstBackendValidatorSHA256'],'proof_validator_changed')
 for r in proof['Results']:
  for o in r['Objects']:
   load(o['PlanEvidencePath'],o['PlanEvidenceSHA256']);load(o['CatalogueEvidencePath'],o['CatalogueEvidenceSHA256'])
   for p in o['AllSuccessfulAttemptPlanFiles']:load(p['Path'],p['SHA256'])
 return oldf,m,failed,proof
def base_authority(a):
 need(os.geteuid()==0 and os.uname().nodename=='10-60-162-188','new_root_only')
 need(a.continuation_id==CONT and a.go=='APPROVED:'+CONT,'explicit_continuation_go_required')
 need(sha(__file__)==a.validator_sha and sha(FD/'final-data-operator.py')==FROZEN_OP_SHA,'reviewed_validator_or_frozen_operator_changed')
 f=op.authority(newargs(a));oldf,m,failed,proof=history(a)
 need(f.get('OriginalWindowID')==OLD and f.get('OriginalFenceSHA256')==OLD_FENCE and f.get('OriginalManifestSHA256')==OLD_MANIFEST and f.get('OriginalFailedApplyReceiptSHA256')==a.failed_apply_sha,'continuation_historical_binding_mismatch')
 need(f['ControlStateSHA256']==CONTROL,'original_control_plan_changed')
 for name in op.WRITERS:
  for k in ('ContainerID','ImageID','FinishedAt'):need(f['SourceContainers'][name][k]==oldf['SourceContainers'][name][k],'source_continuous_fence_changed:'+name)
 ready=load(CR/'test-ready.private.json',a.ready_sha);physical=load(CR/'test-physical-fence.private.json',a.physical_sha);gate=f['TestWriterGate']
 need(ready['schema']==1 and ready['phase']=='locked_with_producers_physically_stopped' and ready['owner']=='migration-controller' and ready['host']=='home-ubuntu' and ready['window_id']==ready['continuation_id']==CONT,'fresh_ready_schema_mismatch')
 need(ready['source_develop_sha']==DEVELOP and ready['lock_code_sha256']==LOCK_CODE and ready['lock_image_id']==IMAGE and ready['lock_kind']=='isolated_docker','ready_lock_code_or_image_mismatch')
 need(re.fullmatch('[0-9a-f]{64}',ready['lock_container_id']) and ready['lock_container_pid']>0 and ready['lock_device']==2081 and ready['lock_inode']==203039078,'ready_actual_full_lock_identity_required')
 need(1<=ready['lock_ttl']<=1800 and abs(ready['expires_unix']-ready['obtained_unix']-ready['lock_ttl'])<0.01 and ready['obtained_unix']<=time.time()+5 and ready['expires_unix']>time.time(),'fresh_lock_expired_or_unbounded')
 links={'ReadySHA256':a.ready_sha,'HolderContainerID':ready['lock_container_id'],'SourceDevelopSHA':DEVELOP,'StageLockInode':ready['lock_inode'],'StageLockDevice':ready['lock_device'],'ObtainedUnix':ready['obtained_unix'],'ExpiresUnix':ready['expires_unix'],'LockCodeSHA256':LOCK_CODE}
 need(all(gate.get(k)==v for k,v in links.items()),'canonical_new_fence_ready_lock_binding_mismatch')
 need(f['TestPhysicalFenceSHA256']==ready['test_physical_fence_sha256']==a.physical_sha,'test_baseline_physical_sha_mismatch')
 need(physical['schema']==1 and physical['phase']=='read_only_physical_fence_snapshot' and physical['window_id']==physical['continuation_id']==CONT and physical['all_eight_controls_match_original_paused'] is True,'test_baseline_schema_mismatch')
 rows=physical['canonical_paused_rows'];need(len(rows)==8 and all(v['paused'] is True for v in rows.values()) and control_hash(rows)==physical['test_job_controls_sha256']==ready['test_job_controls_sha256']==EIGHT,'eight_original_full_paused_rows_changed')
 need(physical['database_authority']=={'database':'katrain_db','server_address':'172.19.0.4/32','server_port':5432} and physical['queue_counts']=={'report':0,'live_analysis':0,'runs':0} and physical['active_intervals']==[] and physical['loop_in_flight']=={'analyze':0,'report_analyze':0} and physical['credential_envfile_unlinked'],'test_authority_or_idle_state_mismatch')
 need(physical['stage_device']==ready['lock_device'] and physical['stage_inode']==ready['lock_inode'],'test_stage_file_identity_mismatch')
 for name,p in physical['producers_physically_stopped'].items():need(p['running'] is False and p['host_pid']==0 and p['status']==('created' if name=='new_cron' else 'exited'),'test_producer_not_physically_stopped')
 return f,ready,physical,m,failed,proof
def authorize(a,stage):
 chain=base_authority(a);f,ready,physical,_,_,_=chain
 need(pathlib.Path(a.live_probe_file)==CR/('live-probe-'+stage+'.private.json'),'fixed_stage_live_probe_path_required')
 live=load(a.live_probe_file,a.live_probe_sha)
 need(live['schema']==1 and live['phase']=='current_fresh_lock_and_physical_fence_verified' and live['stage']==stage and live['window_id']==CONT and live['ready_sha256']==a.ready_sha,'stage_live_probe_schema_binding_mismatch')
 need(-5<=time.time()-live['checked_at_unix']<=60 and abs(datetime.datetime.fromisoformat(live['checked_at_utc'].replace('Z','+00:00')).timestamp()-live['checked_at_unix'])<1 and live['expires_unix']==ready['expires_unix']>time.time(),'live_probe_stale_or_expired')
 need(live['lock_proof']=={'container_id':ready['lock_container_id'],'container_pid':ready['lock_container_pid'],'lock_inode':ready['lock_inode'],'lock_device':ready['lock_device']},'live_actual_flock_identity_mismatch')
 need(live['test_job_controls_sha256']==EIGHT and live['all_eight_controls_match_original_paused'] is True and live['producers_physically_stopped']==physical['producers_physically_stopped'],'current_test_fence_or_eight_rows_changed')
 return chain,live
def source_probe(a,with_fingerprints=False,nonce=None):
 # One VPC SSH stream. Only new current authority is used; old manifest is historical evidence.
 code="""import pathlib,hashlib,json,argparse,importlib.util,socket
assert socket.gethostname()=='10-60-219-118'
p=pathlib.Path(OPPATH);assert hashlib.sha256(p.read_bytes()).hexdigest()==OPSHA
s=importlib.util.spec_from_file_location('o',p);o=importlib.util.module_from_spec(s);s.loader.exec_module(o)
a=argparse.Namespace(window_id=CONT,fence_file=FENCE,fence_sha=NEWPIN,go='APPROVED:'+CONT)
f=o.authority(a);o.source_gate(f)
old=pathlib.Path(MANIFEST);assert hashlib.sha256(old.read_bytes()).hexdigest()==MANIFESTSHA
result={'Status':'fresh_source_physically_fenced_under_continuation','SourceHostname':socket.gethostname(),'ReceiverActiveKeysBytes':o.KEYS.stat().st_size,'ReceiverProcesses':len(o.receiver_processes()),'Writers':{},'Postgres':{}}
for name in o.WRITERS:
 c=o.inspect(name);st=c['State'];result['Writers'][name]={'ContainerID':c['Id'],'ImageID':c['Image'],'Running':st['Running'],'Status':st['Status'],'PID':st['Pid'],'FinishedAt':st['FinishedAt']}
for name in o.PG:
 c=o.inspect(name);result['Postgres'][name]={'ContainerID':c['Id'],'ImageID':c['Image'],'Running':c['State']['Running'],'Status':c['State']['Status'],'PID':c['State']['Pid']}
if FULL:
 result['Fingerprints']=o.fingerprints();result['PasswordProof']=o.role_password_proof(NONCE)
o.source_gate(f);o.authority(a)
print(json.dumps(result))
"""
 values={'OPPATH':str(FD/('operator-'+OLD+'.py')),'OPSHA':FROZEN_OP_SHA,'CONT':CONT,'FENCE':str(BASE/('source-fence-'+CONT+'.private.json')),'NEWPIN':a.new_fence_sha,'MANIFEST':str(BASE/('final-db-'+OLD)/'manifest.json'),'MANIFESTSHA':OLD_MANIFEST,'FULL':with_fingerprints,'NONCE':nonce}
 pre='\n'.join(k+'='+repr(v) for k,v in values.items())+'\n'
 ssh=['ssh','-i',str(BASE/'transfer_key'),'-oIdentitiesOnly=yes','-oBatchMode=yes','-oStrictHostKeyChecking=yes','-oUserKnownHostsFile='+str(BASE/'transfer_known_hosts'),'-oConnectTimeout=10','ubuntu@10.60.219.118','sudo','-n','python3','-']
 r=subprocess.run(ssh,input=(pre+code).encode(),capture_output=True)
 if r.returncode:(CR/'source-check.stderr.private.log').write_bytes(r.stderr)
 need(r.returncode==0,'fresh_source_probe_failed_no_automatic_retry')
 return json.loads(r.stdout)
def target_actual(pg_running):
 op.target_gate(pg_running)
 result={'Postgres':{},'NonPGContainers':{},'ReceiverActiveKeysBytes':op.KEYS.stat().st_size,'ReceiverProcesses':len(op.receiver_processes())}
 ids=subprocess.check_output(['docker','ps','-aq'],text=True).splitlines()
 for ident in ids:
  c=op.inspect(ident);st=c['State'];value={'ContainerID':c['Id'],'ImageID':c['Image'],'Running':st['Running'],'Status':st['Status'],'PID':st['Pid'],'FinishedAt':st['FinishedAt']}
  result['Postgres' if c['Name'].lstrip('/') in op.PG else 'NonPGContainers'][c['Name'].lstrip('/')]=value
 return result
def receipt_chain(a):
 return {'OriginalWindowID':OLD,'OriginalFenceSHA256':OLD_FENCE,'OriginalManifestSHA256':OLD_MANIFEST,'OriginalFailedApplyReceiptSHA256':a.failed_apply_sha,'OriginalTransferReceiptSHA256':a.transfer_receipt_sha,'ContinuationID':CONT,'ContinuationWindowID':CONT,'ContinuationFenceSHA256':a.new_fence_sha,'ReadySHA256':a.ready_sha,'BaselineTestPhysicalFenceSHA256':a.physical_sha,'SemanticProofSHA256':a.proof_sha,'ValidatorSHA256':a.validator_sha,'TestHelperSHA256':TEST_HELPER,'FrozenOriginalOperatorSHA256':FROZEN_OP_SHA}
def verify(a):
 (f,ready,physical,m,failed,proof),live=authorize(a,'verify');path=CR/'verification-candidate.private.json';need(not path.exists(),'candidate_already_exists_no_auto_rerun')
 target_actual(True);nonce=secrets.token_hex(32);source=source_probe(a,True,nonce);target=op.fingerprints()
 need(hashlib.sha256(canonical(source['Fingerprints'])).hexdigest()==m['FingerprintSHA256'],'fresh_source_differs_from_original_manifest')
 need(hmac.compare_digest(source['PasswordProof'],op.role_password_proof(nonce)),'fresh_role_password_proof_mismatch');source.pop('PasswordProof')
 patched=copy.deepcopy(target);exceptions=[]
 bound={(r['Container'],r['Database']):r for r in proof['Results']}
 for name,db in sorted(FOUR):
  current=target[name]['databases'][db]['schema_sha256'];expected=m['fingerprints'][name]['databases'][db]['schema_sha256'];b=bound[(name,db)]
  stem=name+'--'+db;diagnosis=FD/('schema-diagnosis-'+OLD)
  src=diagnosis/(stem+'.source.raw.private.sql');dst=diagnosis/(stem+'.target.raw.private.sql')
  need(sha(src)==b['RawSourceSHA256'] and sha(dst)==b['RawTargetSHA256'],'schema_files_not_bound_to_pinned_68_backend_proof')
  need(expected==original_schema_sha(src.read_bytes()) and current==original_schema_sha(dst.read_bytes()),'raw_schema_drift_outside_finite_proof')
  patched[name]['databases'][db]['schema_sha256']=expected;exceptions.append({'Container':name,'Database':db,'OriginalSourceSchemaSHA256':expected,'CurrentTargetSchemaSHA256':current,'HistoricalRawSourceFileSHA256':b['RawSourceSHA256'],'HistoricalRawTargetFileSHA256':b['RawTargetSHA256']})
 need(patched==m['fingerprints'],'fresh_target_has_extra_difference_beyond_exact_four_schema_hashes')
 actual=target_actual(True);end_source=source_probe(a,False);base_authority(a)
 result={'Status':'candidate_existing_import_checks_passed_not_verified','CreatedUnix':time.time(),'CreatedUTC':utc(),**receipt_chain(a),'OriginalRestoreExit0':failed['databases'],'OriginalImportStatusUnchanged':'failed_final_apply','FreshSourceFingerprintSHA256':m['FingerprintSHA256'],'CurrentTargetFingerprintSHA256':hashlib.sha256(canonical(target)).hexdigest(),'OnlyFiniteFourRawSchemaExceptions':exceptions,'RolePasswordsVerifiedInMemory':True,'FreshVerifyLiveProbeSHA256':a.live_probe_sha,'Lock':ready,'TestBaselinePhysical':physical,'FreshTestVerifyProbe':live,'SourceActual':end_source,'TargetActual':actual,'NoRestoreOrDataWritePerformed':True,'LegacyPSQLRestrictTokenPolicyOnly':True}
 save(CR/'fresh-source-fingerprints.private.json',source['Fingerprints']);save(CR/'fresh-target-fingerprints.private.json',target);save(path,result)
 print(json.dumps({'Status':result['Status'],'CandidateSHA256':sha(path)}))
def sign(a):
 chain,live=authorize(a,'sign');candidate=load(CR/'verification-candidate.private.json',a.candidate_sha)
 need(candidate['Status']=='candidate_existing_import_checks_passed_not_verified' and 0<=time.time()-candidate['CreatedUnix']<=300,'candidate_missing_or_stale')
 need(all(candidate.get(k)==v for k,v in receipt_chain(a).items()),'candidate_evidence_chain_changed')
 source=source_probe(a,False);target=target_actual(True);authorize(a,'sign')
 path=CR/'verification.private.json';need(not path.exists(),'verification_receipt_already_exists')
 result={**candidate,'Status':'verified_existing_final_import_under_continuation','SignedUnix':time.time(),'SignedUTC':utc(),'CandidateSHA256':a.candidate_sha,'FreshSignLiveProbeSHA256':a.live_probe_sha,'FreshTestSignProbe':live,'SourceActualAtSigning':source,'TargetActualAtSigning':target,'ConfigsStatus':'pending_normal_stop_and_explicit_config_copy'}
 save(path,result);print(json.dumps({'Status':result['Status'],'VerificationSHA256':sha(path)}))
def copy_configs(a):
 (f,ready,physical,m,failed,proof),live=authorize(a,'copy');verified=load(CR/'verification.private.json',a.verification_sha)
 need(verified['Status']=='verified_existing_final_import_under_continuation' and all(verified.get(k)==v for k,v in receipt_chain(a).items()),'signed_continuation_receipt_required')
 root=pathlib.Path(a.original_manifest_root)
 for record in [x for v in m['configs'].values() for x in v['files']]:
  p=root/record['file'];need(p.resolve().is_relative_to(root.resolve()) and p.stat().st_size==record['bytes'] and sha(p)==record['sha256'],'config_payload_sha_or_path_mismatch')
  need(not record['external'],'external_configs_require_separate_controller_resolution')
 source_probe(a,False);states=[op.inspect(n)['State']['Running'] for n in op.PG];need(len(set(states))==1,'mixed_target_pg_state')
 before=target_actual(states[0]);stop_performed=states[0]
 if stop_performed:subprocess.run(['docker','stop','--signal','SIGTERM','--timeout','-1']+list(op.PG),check=True,stdout=subprocess.DEVNULL)
 stopped=target_actual(False)
 for n in op.PG:need(stopped['Postgres'][n]['Status']=='exited' and stopped['Postgres'][n]['PID']==0 and stopped['Postgres'][n]['ContainerID']==before['Postgres'][n]['ContainerID'],'pg_not_normally_exited_or_identity_changed')
 save(CR/'normal-pg-stop.private.json',{'Status':'actual_pg_stopped_for_continuation_configs','StopPerformedByThisAction':stop_performed,'Signal':'SIGTERM','Timeout':-1,'Postgres':stopped['Postgres'],**receipt_chain(a)})
 authorize(a,'copy');out=CR/'config-copy.private.json';need(not out.exists(),'config_copy_receipt_exists_requires_controller_review')
 result={'Status':'copying_stopped_pg_configs_under_continuation',**receipt_chain(a),'VerificationSHA256':a.verification_sha,'FreshCopyLiveProbeSHA256':a.live_probe_sha,'Files':[]};save(out,result)
 for name,(volume,major,_) in op.PG.items():
  v=json.loads(subprocess.check_output(['docker','volume','inspect',volume]))[0];mount=pathlib.Path(v['Mountpoint']);need((mount/'PG_VERSION').read_text().strip()==major and mount.stat().st_uid==70 and stat.S_IMODE(mount.stat().st_mode)==0o700,'stopped_pg_volume_identity_mismatch')
  for record in m['configs'][name]['files']:
   rel=pathlib.PurePosixPath(record['volume_relative_path']);need(not rel.is_absolute() and '..' not in rel.parts,'unsafe_config_relative_path');dst=mount.joinpath(*rel.parts);need(dst.resolve().is_relative_to(mount.resolve()),'config_symlink_escape')
   missing=[];parent=dst.parent
   while not parent.exists():missing.append(parent);parent=parent.parent
   for parent in reversed(missing):parent.mkdir(mode=0o700);os.chown(parent,70,70)
   tmp=dst.with_name(dst.name+'.continuation-'+CONT);need(not tmp.exists(),'stale_config_temporary_file');tmp.write_bytes((root/record['file']).read_bytes());tmp.chmod(int(record['source_mode'],8));os.chown(tmp,70,70);tmp.replace(dst)
   need(sha(dst)==record['sha256'] and dst.stat().st_uid==70 and stat.S_IMODE(dst.stat().st_mode)==int(record['source_mode'],8),'copied_config_bytes_owner_mode_mismatch')
   result['Files'].append({'Container':name,'RelativePath':str(rel),'SHA256':record['sha256'],'UID':70,'Mode':record['source_mode']});save(out,result)
 target_actual(False);source_probe(a,False);authorize(a,'copy')
 result['Status']='verified_stopped_pg_configs_under_continuation_pending_controller_restart';result['CompletedUTC']=utc();save(out,result)
 files=load(FD/('files-'+OLD+'.private.json'));need(files['Status']=='verified_final_files_two_checksum_dryruns_zero' and files['WindowID']==OLD and files['SourceFenceSHA256']==OLD_FENCE and len(files['CompletedMappings'])==8 and len(files['DryRunPasses'])==2 and all(x['Changes']==0 for x in files['DryRunPasses']),'historical_file_delta_not_verified')
 final={'Status':'verified_final_data_under_continuation_pending_controller_runtime_activation',**receipt_chain(a),'VerificationSHA256':a.verification_sha,'ConfigCopyReceiptSHA256':sha(out),'OriginalFilesReceiptSHA256':sha(FD/('files-'+OLD+'.private.json')),'OriginalApplyStatusRemains':'failed_final_apply','DatabaseRestoresRepeated':False,'RestartsOrActivationPerformed':False,'PostgresStopped':stopped['Postgres'],'CompletedUTC':utc()}
 path=CR/'final-data-receipt.private.json';save(path,final);print(json.dumps({'Status':final['Status'],'FinalDataReceiptSHA256':sha(path),'ConfigFiles':len(result['Files'])}))
def main():
 global op
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['verify','sign','copy'])
 for key in ('continuation-id','new-fence-sha','ready-sha','physical-sha','live-probe-file','live-probe-sha','original-manifest-root','failed-apply-sha','transfer-receipt-sha','proof-sha','validator-sha','go'):p.add_argument('--'+key,required=True)
 p.add_argument('--candidate-sha');p.add_argument('--verification-sha');a=p.parse_args()
 need(sha(FD/'final-data-operator.py')==FROZEN_OP_SHA,'frozen_original_operator_changed')
 spec=importlib.util.spec_from_file_location('op',FD/'final-data-operator.py');op=importlib.util.module_from_spec(spec);spec.loader.exec_module(op)
 if a.stage=='sign':need(bool(a.candidate_sha),'explicit_candidate_sha_required')
 if a.stage=='copy':need(bool(a.verification_sha),'explicit_verification_sha_required')
 {'verify':verify,'sign':sign,'copy':copy_configs}[a.stage](a)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  if isinstance(e,SystemExit):raise
  print(json.dumps({'Status':'continuation_blocked_or_failed','FailureType':type(e).__name__,'Reason':str(e) if isinstance(e,RuntimeError) else 'private_error'}),file=sys.stderr);sys.exit(1)
