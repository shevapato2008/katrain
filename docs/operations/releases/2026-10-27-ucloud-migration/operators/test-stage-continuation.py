#!/usr/bin/env python3
"""TEST continuation: read-only probe, or explicit new bounded pure flock. No business restore/start."""
import argparse, datetime, hashlib, importlib.util, json, os, pathlib, re, socket, stat, subprocess, sys, tempfile, time
from types import SimpleNamespace

BASE=pathlib.Path('/mnt/disk1/fan/ucloud-migration-test-endpoint-20261027')
OPS=pathlib.Path('/mnt/disk1/fan/kifu-rank-coverage-e9b4d3ecc-20261026')
SHA='e9b4d3ecce03b3269f12922a476fd6d6c6545547'
IMAGE='sha256:9604d05e4e096b4c97966e6c850492c87d60fe9fff1039c3fe94f67af081c08d'
WINDOW='migrate-continue-20261027-0420'
OLDLOCK='41c57b043ce8cc5c2665edfadd46e084d3c0858f3f2713345bdc24b80ec54d04'
OLDCRON='7510def826471eb3b3a261db704f68db104fb47df6c6fbe5526c679f5046100f'
NEWCRON='aff8a3252ceb626b222fc1f29134bb5e27d01b2eba5e2ee2a2f2e511e8145e19'
WEB='bbeef6a4c22a975a75aa99f02fa8be18ad2cf07725f94cd5f8b939e42d4f8984'
STAGE=pathlib.Path('/mnt/disk1/fan/kifu-hourly-incremental-20261019/ingest-stage')
INODE=203039078
DEVICE=2081
MAINT_SHA='953791eace80880418c4151cae2a52f326f9f44588e22e62e23345d24b0a0e4e'
CONTROL_SHA='8cbc4798ef297d0ae85ba29a684770be98f224fb3aacc2065f3fcfac970a6d4d'
CODE_SHA='3486adef8be01f7c707cb879553bef11668d32e4c89de637fc0a357126045aa7'
CLOUD_SHA='0d03529e22c2103c977581309fd95af82fa53e0e100905a183a5bd5537efcbd4'

def require(ok,code):
    if not ok: raise RuntimeError(code)
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def hashbytes(b): return hashlib.sha256(b).hexdigest()
def save(p,v):
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f: json.dump(v,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def run(args,stdin=None,timeout=30):
    p=subprocess.run(args,input=stdin,capture_output=True,text=True,timeout=timeout)
    if p.returncode:
        classes=re.findall(r'^(?:[A-Za-z_]\w*\.)*([A-Za-z_]\w*(?:Error|Exception)):',p.stderr,re.M)
        raise RuntimeError('private_subprocess_failed'+('_'+classes[-1] if classes else ''))
    return p.stdout
def inspect(cid): return json.loads(run(['docker','inspect',cid]))[0]
def physical():
    out={}
    for label,cid,status in [('old_cron',OLDCRON,'exited'),('new_cron',NEWCRON,'created'),('web',WEB,'exited')]:
        c=inspect(cid);require(c['Id']==cid and not c['State']['Running'] and c['State']['Status']==status and c['State']['Pid']==0,'producer_not_physically_stopped')
        if label!='web': require(c['Image']==IMAGE,'producer_image_changed')
        out[label]={'id':cid,'image_id':c['Image'],'status':status,'running':False,'host_pid':0,'finished_at':c['State']['FinishedAt']}
    return out
def modules():
    m=(OPS/'maintenance.py').read_text();c=(BASE/'control-batch.py').read_text()
    require(hashbytes(m.encode())==MAINT_SHA and hashbytes(c.encode())==CONTROL_SHA,'approved_source_hash_mismatch')
    require(hashbytes((OPS/'cloud_overlay.py').read_bytes())==CLOUD_SHA,'approved_cloud_overlay_hash_mismatch')
    sys.path.insert(0,str(OPS))
    spec=importlib.util.spec_from_file_location('maintenance',OPS/'maintenance.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    sys.modules['maintenance']=mod
    require(hashbytes(mod.LOCK_CODE.encode())==CODE_SHA,'lock_code_hash_mismatch')
    return mod,m,c

# This code is passed on stdin to one DB-only container. Source strings are approved
# modules, but only maintenance.db('db-status') and control.db_worker(mode='read') run.
DB_READ=r'''import datetime,hashlib,json,logging,sys
logging.disable(logging.CRITICAL)
p=json.load(sys.stdin)
m={'__name__':'_maintenance_readonly_'};exec(p['maintenance_source'],m)
c={'__name__':'_control_readonly_'};exec(p['control_source'],c)
k=m['db']('db-status',{})
seven=c['db_worker']({'mode':'read','expected_database':'katrain_db'})
connection=m['db_connect']()
try:
 q=connection.cursor();q.execute('SET TRANSACTION READ ONLY');q.execute("SET LOCAL statement_timeout='8s'");q.execute("SET LOCAL lock_timeout='3s'")
 queues={}
 for label,sql in [('report',"SELECT count(*) FROM report_tasks WHERE status IN ('pending','running','authorizing')"),('live_analysis',"SELECT count(*) FROM live_analysis WHERE status IN ('pending','running')"),('runs',"SELECT count(*) FROM cron_job_runs WHERE status='running' AND finished_at IS NULL")]:q.execute(sql);queues[label]=q.fetchone()[0]
 q.execute('SELECT job_name,kind,enabled,last_started_at,last_finished_at,last_status,loop_stats FROM cron_job_status')
 rows=q.fetchall();active=[];loops={}
 for job,kind,enabled,started,finished,status,stats in rows:
  if kind=='interval' and enabled and started and (finished is None or finished<started or status=='running'):active.append(job)
  if kind=='loop' and enabled:loops[job]=(stats or {}).get('in_flight')
 connection.rollback()
finally:connection.close()
print(json.dumps({'kifu':k,'seven':seven,'queues':queues,'active_intervals':active,'loop_in_flight':loops}),flush=True)
'''

def probe(m,maintenance_source,control_source,work,check_old=True):
    producers=physical();s=(STAGE/'.writer.lock').stat();require((s.st_dev,s.st_ino)==(DEVICE,INODE),'stage_lock_identity_changed')
    old=None
    if check_old:
        old=inspect(OLDLOCK)
        require(old['Id']==OLDLOCK and old['Image']==IMAGE and old['Name']=='/kifu-rank-lock-'+SHA[:12] and not old['State']['Running'] and old['State']['Status']=='exited' and old['State']['ExitCode']==0,'old_pure_holder_not_naturally_exited')
    original=json.loads((BASE/'cron.before.private.json').read_text())[0]
    env=dict(x.split('=',1) for x in original['Config']['Env'])
    url=env.get('CRON_DATABASE_URL') or env.get('KATRAIN_DATABASE_URL')
    require(bool(url) and '\n' not in url and '\r' not in url,'actual_database_url_not_single_line')
    # Preserve only the original Linux host-gateway mapping needed by this DB URL.
    # Do not invent a new address or replay unrelated host/network configuration.
    from urllib.parse import urlsplit
    hosts=[x for x in (original['HostConfig'].get('ExtraHosts') or []) if x in ('host.docker.internal:host-gateway','host.docker.internal=host-gateway')]
    require(len(hosts)<=1,'duplicate_original_host_gateway_mapping')
    if urlsplit(url).hostname=='host.docker.internal':require(len(hosts)==1,'original_host_gateway_mapping_required')
    host_args=[item for value in hosts for item in ['--add-host',value]]
    fd,path=tempfile.mkstemp(prefix='.db-only-',suffix='.env',dir=work)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as f:f.write('CRON_DATABASE_URL='+url+'\nKATRAIN_DATABASE_URL='+url+'\n');f.flush();os.fsync(f.fileno())
        out=json.loads(run(['docker','run','--rm','-i','--pull','never','--network','katrain_default',*host_args,'--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges','--env-file',path,'--env','PGCONNECT_TIMEOUT=5','--entrypoint','python3',IMAGE,'-B','-c',DB_READ],json.dumps({'maintenance_source':maintenance_source,'control_source':control_source}),timeout=45))
    finally:
        if os.path.exists(path):os.unlink(path)
        url=None
    seven=json.loads((BASE/'seven-controls.private.json').read_text());kifu=json.loads((BASE/'guard/kifu-control.private.json').read_text())
    require(out['seven']['rows']==seven['paused'],'seven_control_after_image_changed')
    require(out['seven']['authority']==seven['origin_authority']['database'],'test_database_authority_changed')
    require(out['kifu']['control_sha256']==m.digest(kifu['paused']),'kifu_control_after_image_changed')
    require(out['kifu']['paused'] and out['kifu']['finished_not_before_started'] and not out['kifu']['advisory_lock'] and out['kifu']['running_run_count']==0,'kifu_not_paused_idle')
    require(not out['active_intervals'] and out['loop_in_flight']=={'analyze':0,'report_analyze':0} and all(v==0 for v in out['queues'].values()),'job_or_queue_not_idle')
    require(physical()==producers,'producer_identity_changed_during_probe')
    norm_kifu=dict(kifu['paused'])
    if norm_kifu.get('changed_at'):
        t=datetime.datetime.fromisoformat(norm_kifu['changed_at'].replace('Z','+00:00'))
        norm_kifu['changed_at']=t.astimezone(datetime.timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
    rows=dict(out['seven']['rows'],kifu_ingest=norm_kifu)
    result={'schema':1,'phase':'read_only_physical_fence_snapshot','window_id':WINDOW,'continuation_id':WINDOW,'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'database_authority':out['seven']['authority'],'producers_physically_stopped':producers,'all_eight_controls_match_original_paused':True,'canonical_paused_rows':rows,'seven_control_sha256':digest(out['seven']['rows']),'kifu_control_sha256':digest(norm_kifu),'kifu_native_status_sha256':out['kifu']['control_sha256'],'test_job_controls_sha256':digest(rows),'queue_counts':out['queues'],'active_intervals':out['active_intervals'],'loop_in_flight':out['loop_in_flight'],'credential_envfile_unlinked':not os.path.exists(path),'stage_device':DEVICE,'stage_inode':INODE}
    if old is not None:result['old_pure_holder']={'id':OLDLOCK,'image_id':IMAGE,'status':'exited','running':False,'exit_code':0,'finished_at':old['State']['FinishedAt']}
    save(work/'probe.private.json',result)
    save(work/'test-physical-fence.private.json',result)
    return result

def acquire(m,proof,work,ttl):
    old=inspect(OLDLOCK)
    require(old['Id']==OLDLOCK and old['Image']==IMAGE and old['Name']=='/kifu-rank-lock-'+SHA[:12],'old_pure_holder_identity_changed')
    require(not old['State']['Running'] and old['State']['Status']=='exited' and old['State']['ExitCode']==0,'old_pure_holder_not_naturally_exited')
    original_ready=json.loads((BASE/'guard/ready.json').read_text())
    original_ttl=original_ready['lock_ttl']
    require(original_ready['lock_container_id']==OLDLOCK and original_ready['lock_image_id']==IMAGE and type(original_ttl) is int and 1<=original_ttl<=1800,'original_pure_holder_ttl_identity_changed')
    require(old['Config']['User']=='0:0' and old['Config']['Entrypoint']==['/usr/bin/env'] and old['Config']['Cmd']==['-i','/usr/local/bin/python3','-I','-B','-S','-c',m.LOCK_CODE,str(original_ttl)],'old_pure_holder_command_changed')
    h=old['HostConfig'];mounts=old['Mounts'];labels=old['Config']['Labels']
    require(h['NetworkMode']=='none' and h['ReadonlyRootfs'] and not h.get('Privileged') and not h.get('PidMode') and not h.get('DeviceRequests'),'old_pure_holder_isolation_changed')
    require(len(mounts)==1 and mounts[0]['Type']=='bind' and mounts[0]['Source']==str(STAGE) and mounts[0]['Destination']=='/stage' and not mounts[0]['RW'],'old_pure_holder_mount_changed')
    require(labels.get('org.stellabox.lock-source-sha')==SHA and labels.get('org.stellabox.lock-holder-code-sha256')==CODE_SHA,'old_pure_holder_labels_changed')
    save(work/'old-pure-holder.exited.inspect.private.json',old)
    save(work/'old-pure-holder.log.private.json',{'log':run(['docker','logs',OLDLOCK])})
    run(['docker','rm',OLDLOCK])  # Exited, exact pure lock only. No -f, -v, stop or kill.
    lock=m.start_lock(SimpleNamespace(sha=SHA,lock_image=IMAGE),ttl)
    require(lock is not None,'stage_flock_busy_no_writer_interrupted')
    require(lock['lock_device']==DEVICE and lock['lock_inode']==INODE,'new_lock_identity_mismatch')
    ready={'schema':1,'phase':'locked_with_producers_physically_stopped','host':'home-ubuntu','window_id':WINDOW,'continuation_id':WINDOW,'source_develop_sha':SHA,'owner':'migration-controller','lock_kind':'isolated_docker','stage_lock':str(STAGE/'.writer.lock'),'obtained_unix':lock['expires_unix']-ttl,'obtained_at_utc':datetime.datetime.fromtimestamp(lock['expires_unix']-ttl,datetime.timezone.utc).isoformat(),'lock_code_sha256':CODE_SHA,'maintenance_source_sha256':MAINT_SHA,'control_source_sha256':CONTROL_SHA,'test_job_controls_sha256':proof['test_job_controls_sha256'],'test_physical_fence_sha256':hashbytes((work/'test-physical-fence.private.json').read_bytes()),**lock}
    require(physical()==proof['producers_physically_stopped'],'producer_identity_changed_after_lock')
    m.lock_container_gate(ready,SHA)
    save(work/'ready.private.json',ready)
    return ready

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['probe','acquire','check']);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--ready',type=pathlib.Path);p.add_argument('--stage',choices=['verify','sign','copy']);p.add_argument('--ttl',type=int,default=1800);p.add_argument('--go',default='');a=p.parse_args()
    require(socket.gethostname()=='ubuntu','test_hostname_required');require(a.output.is_absolute() and a.output.parent==BASE,'fixed_private_parent_required');require(1<=a.ttl<=1800,'ttl_out_of_bounds')
    if a.mode=='acquire':require(a.go=='APPROVED:'+WINDOW,'explicit_fresh_window_go_required')
    a.output.mkdir(mode=0o700)
    m,ms,cs=modules()
    if a.mode=='check':
        require(a.stage is not None,'explicit_check_stage_required')
        require(a.ready==BASE/('continuation-'+WINDOW)/'ready.private.json','fixed_continuation_ready_required')
        data=a.ready.read_bytes();ready=json.loads(data)
        require(ready['phase']=='locked_with_producers_physically_stopped' and ready['window_id']==WINDOW and ready['continuation_id']==WINDOW and ready['lock_code_sha256']==CODE_SHA,'continuation_ready_identity_mismatch')
        require(ready['source_develop_sha']==SHA and ready['lock_kind']=='isolated_docker' and ready['stage_lock']==str(STAGE/'.writer.lock') and ready['lock_image_id']==IMAGE and ready['lock_device']==DEVICE and ready['lock_inode']==INODE,'continuation_ready_scope_changed')
        require(1<=ready['lock_ttl']<=1800 and ready['expires_unix']-ready['obtained_unix']==ready['lock_ttl'] and ready['obtained_unix']<=time.time()<ready['expires_unix'],'continuation_lock_expired')
        baseline_bytes=(a.ready.parent/'test-physical-fence.private.json').read_bytes()
        require(hashbytes(baseline_bytes)==ready['test_physical_fence_sha256'],'baseline_physical_fence_hash_changed')
        baseline=json.loads(baseline_bytes)
        before=m.lock_container_gate(ready,SHA)
        proof=probe(m,ms,cs,a.output,check_old=False)
        after=m.lock_container_gate(ready,SHA)
        require(before==after and a.ready.read_bytes()==data and time.time()<ready['expires_unix'],'continuation_live_identity_changed')
        require(proof['test_job_controls_sha256']==ready['test_job_controls_sha256'],'continuation_controls_changed')
        require(proof['producers_physically_stopped']==baseline['producers_physically_stopped'],'continuation_physical_fence_changed')
        lock_proof=dict(after,lock_device=proof['stage_device'])
        result={'schema':1,'phase':'current_fresh_lock_and_physical_fence_verified','window_id':WINDOW,'ready_sha256':hashbytes(data),'checked_at_unix':time.time(),'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':a.stage,'lock_proof':lock_proof,'test_job_controls_sha256':proof['test_job_controls_sha256'],'all_eight_controls_match_original_paused':proof['all_eight_controls_match_original_paused'],'producers_physically_stopped':proof['producers_physically_stopped'],'expires_unix':ready['expires_unix']}
        save(a.output/'live-probe.private.json',result)
        print(json.dumps({'phase':result['phase'],'path':str(a.output/'live-probe.private.json'),'sha256':hashbytes((a.output/'live-probe.private.json').read_bytes()),'checked_at_unix':result['checked_at_unix'],'ready_sha256':result['ready_sha256'],'lock_proof':lock_proof,'test_job_controls_sha256':proof['test_job_controls_sha256']},sort_keys=True));return
    require(a.ready is None and a.stage is None,'ready_and_stage_only_valid_for_check')
    proof=probe(m,ms,cs,a.output)
    if a.mode=='probe':
        public={k:v for k,v in proof.items() if k!='canonical_paused_rows'}
        print(json.dumps({**public,'phase':'read_only_probe_passed','output':str(a.output)},sort_keys=True));return
    ready=acquire(m,proof,a.output,a.ttl)
    print(json.dumps({'phase':ready['phase'],'ready_path':str(a.output/'ready.private.json'),'ready_sha256':hashbytes((a.output/'ready.private.json').read_bytes()),'obtained_unix':ready['obtained_unix'],'expires_unix':ready['expires_unix'],'holder':{k:ready[k] for k in ['lock_container_id','lock_container_pid','lock_inode','lock_device','lock_ttl']},'lock_code_sha256':CODE_SHA,'test_job_controls_sha256':proof['test_job_controls_sha256']},sort_keys=True))

if __name__=='__main__':
    try:main()
    except BaseException as e:
        safe=str(e) if isinstance(e,RuntimeError) and str(e).replace('_','').isalnum() else type(e).__name__
        print(json.dumps({'phase':'refused','error_code':safe}));sys.exit(1)
