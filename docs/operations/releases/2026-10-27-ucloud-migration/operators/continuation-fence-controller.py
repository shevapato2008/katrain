#!/usr/bin/env python3
"""Sign a new controller fence from current physical facts; never edit historical evidence."""
import os,sys,json,pathlib,hashlib,time,socket,subprocess,shlex,datetime
R=pathlib.Path('/var/lib/ucloud-migration-20261027');W='migrate-continue-20261027-0420';OLD='migrate-final-20261027-0330'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):
 s=p.lstat();assert s.st_uid==0 and s.st_mode&0o777==0o600 and p.is_file() and not p.is_symlink()
 b=p.read_bytes();return json.loads(b),sha(b)
assert os.geteuid()==0 and socket.gethostname()=='10-60-162-188' and sys.argv[1:]==['APPROVED:'+W]
D=R/('continuation-'+W);ready,rsha=read(D/'test-ready.private.json');physical,psha=read(D/'test-physical-fence.private.json')
assert ready['phase']=='locked_with_producers_physically_stopped' and ready['window_id']==ready['continuation_id']==W
assert ready['source_develop_sha']=='e9b4d3ecce03b3269f12922a476fd6d6c6545547'
assert ready['lock_device']==2081 and ready['lock_inode']==203039078 and 0<ready['lock_ttl']<=1800
assert ready['obtained_unix']<=time.time()<ready['expires_unix'] and ready['expires_unix']-ready['obtained_unix']<=1800.01
live,lsha=read(D/'live-probe-verify.private.json')
assert live['schema']==1 and live['phase']=='current_fresh_lock_and_physical_fence_verified' and live['window_id']==W and live['stage']=='verify'
assert live['ready_sha256']==rsha and 0<=time.time()-live['checked_at_unix']<=60 and live['expires_unix']==ready['expires_unix']
assert live['lock_proof']=={'container_id':ready['lock_container_id'],'container_pid':ready['lock_container_pid'],'lock_inode':ready['lock_inode'],'lock_device':ready['lock_device']}
assert live['all_eight_controls_match_original_paused'] is True and live['test_job_controls_sha256']==ready['test_job_controls_sha256'] and live['producers_physically_stopped']==physical['producers_physically_stopped']
assert ready['test_physical_fence_sha256']==psha and physical['all_eight_controls_match_original_paused'] is True
assert ready['test_job_controls_sha256']==physical['test_job_controls_sha256']
assert all(not p['running'] and p['host_pid']==0 for p in physical['producers_physically_stopped'].values())
history,hsha=read(R/('source-fence-'+OLD+'.private.json'));assert hsha=='0249da573aa48cc2ff4b3cd7ea7dc5bbd02305edbcd490295801c7a992051225'
manifest,msha=read(R/('final-db-'+OLD)/'manifest.json');assert msha=='3b8d2b9da4ebab869c8a0b5745aa749eda95fa428d09a478f3cef78e983a8a9e'
failed,fsha=read(R/'final-data'/('apply-'+OLD)/'receipt.private.json')
assert failed['Status']=='failed_final_apply' and failed['SourceFenceSHA256']==hsha and failed['ManifestSHA256']==msha
assert len(failed['databases'])==13 and all(d['restore_exit']==0 for d in failed['databases'])
assert sorted((d['container'],d['database']) for d in failed['databases'])==sorted((d['container'],d['database']) for d in manifest['databases'])
f=dict(history,WindowID=W,ContinuationID=W,RecordedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),OriginalWindowID=OLD,OriginalFenceSHA256=hsha,OriginalManifestSHA256=msha,OriginalFailedApplyReceiptSHA256=fsha,TestPhysicalFenceSHA256=psha)
f['TestWriterGate']={'ReadySHA256':rsha,'ExpiresUnix':ready['expires_unix'],'HolderContainerID':ready['lock_container_id'],'SourceDevelopSHA':ready['source_develop_sha'],'StageLockInode':ready['lock_inode'],'StageLockDevice':ready['lock_device'],'ObtainedUnix':ready['obtained_unix'],'LockCodeSHA256':ready['lock_code_sha256']}
SOURCE=r'''import os,sys,json,pathlib,time,hashlib,importlib.util,socket
R=pathlib.Path('/var/lib/ucloud-migration-20261027');f=json.load(sys.stdin);W=f['WindowID']
assert os.geteuid()==0 and socket.gethostname()=='10-60-219-118' and W=='migrate-continue-20261027-0420'
s=importlib.util.spec_from_file_location('op',R/'fence-controller/final-data-operator.py');op=importlib.util.module_from_spec(s);s.loader.exec_module(op)
old=R/('source-fence-'+f['OriginalWindowID']+'.private.json');assert op.digest(old)==f['OriginalFenceSHA256']
prior=json.loads(old.read_text());assert f['SourceContainers']==prior['SourceContainers'] and f['ControlStateSHA256']==prior['ControlStateSHA256']
op.source_gate(f)
control=json.loads(pathlib.Path('/var/lib/ucloud-control-migrate-final-20261027-0330/controls.private.json').read_text())
assert control['phase']=='paused' and control['plan_sha256']==f['ControlStateSHA256']
rows=op.query('katrain-ucloud-postgres-1','katrain_prod_20260725',"SELECT json_agg(json_build_object('job_name',job_name,'paused',paused,'reason',reason,'changed_at',to_char(changed_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"'),'changed_by',changed_by) ORDER BY job_name) FROM cron_job_controls WHERE job_name=ANY(ARRAY['fetch_list','poll_moves','poll_pandanet','translate','fetch_upcoming','cleanup','tutorial_backup']);")
assert {r['job_name']:r for r in rows}==control['paused']
f['RecordedUTC']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
assert f['TestWriterGate']['ExpiresUnix']>time.time()+120
op.source_gate(f);p=R/('source-fence-'+W+'.private.json');assert not p.exists();op.private_json(p,f)
sys.stdout.buffer.write(p.read_bytes())
'''
ssh=['ssh','-i',str(R/'transfer_key'),'-oIdentitiesOnly=yes','-oBatchMode=yes','-oStrictHostKeyChecking=yes','-oUserKnownHostsFile='+str(R/'transfer_known_hosts'),'ubuntu@10.60.219.118']
p=subprocess.run(ssh+['sudo -n python3 -c '+shlex.quote(SOURCE)],input=json.dumps(f).encode(),capture_output=True)
assert p.returncode==0,'source_current_fence_refused'
actual=json.loads(p.stdout);assert actual['SourceContainers']==history['SourceContainers'] and actual['TestWriterGate']==f['TestWriterGate']
out=R/('source-fence-'+W+'.private.json');assert not out.exists();fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'wb') as h:h.write(p.stdout);h.flush();os.fsync(h.fileno())
print(json.dumps({'Status':'fresh_continuation_fence_signed','Path':str(out),'SHA256':sha(p.stdout),'ExpiresUnix':ready['expires_unix']}))
