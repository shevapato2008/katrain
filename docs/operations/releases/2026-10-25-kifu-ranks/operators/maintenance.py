"""Pause only TEST ingest; hold its host flock across receiver/producer changes."""
import argparse, datetime, fcntl, hashlib, json, os, pathlib, re, stat, subprocess, sys, time
ROOT=pathlib.Path(__file__).resolve().parent if '__file__' in globals() else None
STAGE='/mnt/disk1/fan/kifu-hourly-incremental-20261019/ingest-stage'
LOCK_CODE="""import fcntl,json,os,stat,sys,time
fd=os.open('/stage/.writer.lock',os.O_RDONLY|os.O_NOFOLLOW)
if not stat.S_ISREG(os.fstat(fd).st_mode): raise RuntimeError('lock_not_regular')
try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError: sys.exit(75)
s=os.fstat(fd); ttl=int(sys.argv[1])
assert 1<=ttl<=1800 and os.getpid()==1
print(json.dumps({'fd':fd,'inode':s.st_ino,'device':s.st_dev,'expires_unix':time.time()+ttl}),flush=True)
deadline=time.monotonic()+ttl
while time.monotonic()<deadline: time.sleep(min(1,deadline-time.monotonic()))
os.close(fd)
"""
def fail(code): raise RuntimeError(code)
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def db_connect():
 import logging
 logging.disable(logging.CRITICAL)
 from sqlalchemy import create_engine
 from sqlalchemy.pool import NullPool
 from katrain.cron.config import DATABASE_URL
 engine=create_engine(DATABASE_URL,echo=False,poolclass=NullPool)
 if engine.dialect.name!='postgresql': fail('postgresql_required')
 return engine.raw_connection()
def serialize(row):
 return {k:(v.isoformat() if isinstance(v,datetime.datetime) else v) for k,v in row.items()}
def row(cursor):
 cursor.execute("SELECT job_name,paused,reason,changed_at,changed_by FROM cron_job_controls WHERE job_name='kifu_ingest'")
 result=cursor.fetchone()
 return serialize(dict(zip(['job_name','paused','reason','changed_at','changed_by'],result))) if result else None
def db(mode,payload):
 c=db_connect()
 try:
  q=c.cursor(); q.execute("SET LOCAL statement_timeout='8s'"); q.execute("SET LOCAL lock_timeout='3s'")
  if mode=='db-status':
   q.execute('SET TRANSACTION READ ONLY')
   current=row(q)
   q.execute("SELECT last_started_at,last_finished_at FROM cron_job_status WHERE job_name='kifu_ingest'")
   status=q.fetchone()
   q.execute("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND classid=1263093333 AND objid=1229866801 AND granted)")
   lock=bool(q.fetchone()[0])
   q.execute("SELECT count(*) FROM cron_job_runs WHERE job_name='kifu_ingest' AND status='running' AND finished_at IS NULL")
   running=q.fetchone()[0]
   result={'paused':current is not None and current['paused'] is True,
           'finished_not_before_started':bool(status and status[0] and status[1] and status[1]>=status[0]),
           'advisory_lock':lock,'running_run_count':running,'control_sha256':digest(current)}
   c.rollback(); return result
  if mode=='db-pause':
   q.execute("SELECT job_name FROM cron_job_controls WHERE job_name='kifu_ingest' FOR UPDATE")
   original=row(q)
   if original is None:
    q.execute("INSERT INTO cron_job_controls(job_name,paused,reason,changed_at,changed_by) VALUES('kifu_ingest',true,%s,now(),'rank-release-controller') ON CONFLICT(job_name) DO NOTHING",('rank-release:'+payload['sha'],))
    if q.rowcount!=1: fail('control_insert_raced')
   else:
    q.execute("UPDATE cron_job_controls SET paused=true,reason=%s,changed_at=now(),changed_by='rank-release-controller' WHERE job_name='kifu_ingest'",('rank-release:'+payload['sha'],))
   paused=row(q); c.commit()
   # Private channel only: outer coordinator captures this and never prints original values.
   return {'original':original,'paused':paused,'sha':payload['sha']}
  if mode=='db-restore':
   q.execute("SELECT job_name FROM cron_job_controls WHERE job_name='kifu_ingest' FOR UPDATE")
   current=row(q)
   if current!=payload['paused']: fail('control_changed_by_other_actor')
   prior=payload['original']
   if prior is None: q.execute("DELETE FROM cron_job_controls WHERE job_name='kifu_ingest'")
   else:
    q.execute("UPDATE cron_job_controls SET paused=%s,reason=%s,changed_at=%s,changed_by=%s WHERE job_name='kifu_ingest'",(prior['paused'],prior['reason'],prior['changed_at'],prior['changed_by']))
   after=row(q)
   if after!=prior: fail('control_restore_mismatch')
   c.commit(); return {'restored':True,'control_sha256':digest(after),'original_row_missing':prior is None}
  fail('unsupported_db_mode')
 finally: c.close()
def save(path,value,mode=0o600):
 pathlib.Path(path).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n'); os.chmod(path,mode)
def call(container,mode,payload=None):
 args=['docker','exec','-i',container,'python3','-c',(ROOT/'maintenance.py').read_text(),mode]
 result=subprocess.run(args,input=json.dumps(payload or {}),capture_output=True,text=True,timeout=30)
 if result.returncode: fail('private_db_command_failed')
 return json.loads(result.stdout)
def lock_container_gate(d,source_sha):
 from cloud_overlay import inspect,run
 c=inspect(d['lock_container_id']); labels=c['Config'].get('Labels',{})
 name='kifu-rank-lock-'+source_sha[:12]
 if c['Id']!=d['lock_container_id'] or c['Name']!='/'+name or d['lock_container_name']!=name or c['Image']!=d['lock_image_id']: fail('lock_container_identity_changed')
 if not c['State']['Running'] or c['State']['Pid']!=d['lock_container_pid']: fail('lock_container_not_running')
 if labels.get('org.stellabox.lock-source-sha')!=source_sha or labels.get('org.stellabox.lock-holder-name')!=name or labels.get('org.stellabox.lock-holder-code-sha256')!=hashlib.sha256(LOCK_CODE.encode()).hexdigest(): fail('lock_container_labels_changed')
 if c['Config']['User']!='0:0' or c['Config']['Entrypoint']!=['/usr/bin/env'] or c['Config']['Cmd']!=['-i','/usr/local/bin/python3','-I','-B','-S','-c',LOCK_CODE,str(d['lock_ttl'])]: fail('lock_container_command_changed')
 h=c['HostConfig']
 if h['NetworkMode']!='none' or not h['ReadonlyRootfs'] or h.get('Privileged') or h.get('PidMode') or h.get('DeviceRequests'): fail('lock_container_isolation_changed')
 mounts=c['Mounts']
 if len(mounts)!=1 or mounts[0]['Type']!='bind' or mounts[0]['Source']!=STAGE or mounts[0]['Destination']!='/stage' or mounts[0]['RW']: fail('lock_container_mount_changed')
 code="import json,os,pathlib,sys; fd=int(sys.argv[1]); s=os.stat('/stage/.writer.lock'); print(json.dumps({'inode':s.st_ino,'device':s.st_dev,'fdinfo':pathlib.Path('/proc/1/fdinfo/'+str(fd)).read_text()}))"
 proof=json.loads(run(['docker','exec','--user','0:0',c['Id'],'python3','-I','-B','-S','-c',code,str(d['lock_fd'])],timeout=15))
 if proof['inode']!=d['lock_inode'] or proof['device']!=d['lock_device'] or pathlib.Path(d['stage_lock']).stat().st_ino!=d['lock_inode']: fail('maintenance_lock_inode_changed')
 match=re.search(r'FLOCK\s+ADVISORY\s+WRITE\s+(\d+)\s',proof['fdinfo'])
 if not match or int(match.group(1)) not in {1,d['lock_container_pid']}: fail('maintenance_holder_missing')
 return {'container_id':c['Id'],'container_pid':c['State']['Pid'],'lock_inode':proof['inode']}
def start_lock(a,ttl):
 from cloud_overlay import inspect,run
 name='kifu-rank-lock-'+a.sha[:12]
 cid=run(['docker','run','-d','--pull','never','--name',name,'--user','0:0',
          '--network','none','--read-only','--security-opt','no-new-privileges',
          '--mount','type=bind,src='+STAGE+',dst=/stage,readonly',
          '--label','org.stellabox.lock-source-sha='+a.sha,'--label','org.stellabox.lock-holder-name='+name,
          '--label','org.stellabox.lock-holder-code-sha256='+hashlib.sha256(LOCK_CODE.encode()).hexdigest(),
          '--entrypoint','/usr/bin/env',a.lock_image,'-i','/usr/local/bin/python3','-I','-B','-S','-c',LOCK_CODE,str(ttl)]).strip()
 deadline=time.monotonic()+8
 while time.monotonic()<deadline:
  c=inspect(cid)
  if not c['State']['Running']:
   if c['State']['ExitCode']==75: run(['docker','rm',cid]); return None
   fail('pure_lock_container_failed')
  output=run(['docker','logs',cid]).strip()
  if output:
   proof=json.loads(output)
   return {'lock_container_id':c['Id'],'lock_container_name':name,'lock_container_pid':c['State']['Pid'],
           'lock_image_id':c['Image'],'lock_fd':proof['fd'],'lock_inode':proof['inode'],
           'lock_device':proof['device'],'lock_ttl':ttl,'expires_unix':proof['expires_unix']}
  time.sleep(0.1)
 fail('pure_lock_container_start_timeout')
def hold(a):
 from cloud_overlay import receiver_idle,inspect,run
 if a.go!='APPROVED:'+a.sha or not re.fullmatch('[0-9a-f]{40}',a.sha): fail('exact_controller_go_required')
 if a.stage!=STAGE or not 60<=a.max_seconds<=1800 or not a.lock_image or not re.fullmatch('sha256:[0-9a-f]{64}',a.lock_image): fail('scope_or_duration_invalid')
 stage=pathlib.Path(a.stage)
 if stage.is_symlink() or not stage.is_dir(): fail('unsafe_stage_root')
 if pathlib.Path(a.release_file).exists() or pathlib.Path(a.private_state).exists(): fail('fresh_control_paths_required')
 if inspect(a.db_container)['Image']!=a.lock_image: fail('existing_cron_base_image_required')
 if run(['docker','ps','-aq','--filter','name=^/kifu-rank-lock-'+a.sha[:12]+'$']).strip(): fail('lock_container_name_already_exists')
 control=call(a.db_container,'db-pause',{'sha':a.sha}); save(a.private_state,control)
 lock=None; ready=None; restored=False; started=time.monotonic()
 try:
  deadline=time.monotonic()+min(600,a.max_seconds-30)
  while time.monotonic()<deadline:
   status=call(a.db_container,'db-status')
   if status['paused'] and status['finished_not_before_started'] and not status['advisory_lock'] and status['running_run_count']==0:
    receiver_idle()
    ttl=int(a.max_seconds-(time.monotonic()-started))
    if ttl<15: fail('paused_idle_window_timeout')
    lock=start_lock(a,ttl)
    if lock is None: time.sleep(3); continue
    # Recheck after flock: no business worker may have started in the gap.
    check=call(a.db_container,'db-status'); receiver_idle()
    if check['paused'] and check['finished_not_before_started'] and not check['advisory_lock'] and check['running_run_count']==0: break
    fail('producer_started_during_lock_acquisition')
   time.sleep(3)
  if lock is None: fail('paused_idle_window_timeout')
  ready={'host':'home-ubuntu','phase':'paused_idle_lock_held','source_develop_sha':a.sha,
         'pid':os.getpid(),'lock_kind':'isolated_docker',**lock,
         'stage_lock':str(stage/'.writer.lock'),'db_container':a.db_container,
         'original_control_sha256':digest(control['original']),'paused_control_sha256':digest(control['paused'])}
  lock_container_gate(ready,a.sha)
  save(a.ready,ready,0o644); print(json.dumps({'phase':ready['phase'],'ready_file':a.ready,'pid':os.getpid()}),flush=True)
  while time.time()<ready['expires_unix']:
   release=pathlib.Path(a.release_file)
   if release.is_file():
    signal=json.loads(release.read_text())
    if signal!={'source_develop_sha':a.sha,'verification':'bounded_passed'}: fail('release_signal_invalid')
    lock_container_gate(ready,a.sha)
    result=call(a.db_container,'db-restore',control); restored=True
    run(['docker','stop','--time','2',ready['lock_container_id']]); run(['docker','rm',ready['lock_container_id']])
    ready.update({'phase':'restored_after_verification','restore':result}); save(a.ready,ready,0o644)
    print(json.dumps({'phase':ready['phase'],'ready_file':a.ready}),flush=True); return
   time.sleep(2)
  fail('maintenance_expired_pause_preserved')
 finally:
  if ready and not restored:
   ready['phase']='holder_ended_pause_preserved'; save(a.ready,ready,0o644)
  # On timeout/failure no unpause; the pure lock process exits at its own bounded TTL.
  # Exact restoration is available with restore-private after controller verification.
def main():
 if len(sys.argv)>1 and sys.argv[1].startswith('db-'):
  print(json.dumps(db(sys.argv[1],json.loads(sys.stdin.read() or '{}')))); return
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('mode',choices=['hold','restore-private']); p.add_argument('--sha',required=True); p.add_argument('--go',required=True)
 p.add_argument('--db-container',default='katrain-cron'); p.add_argument('--stage',default=STAGE)
 p.add_argument('--private-state',required=True); p.add_argument('--ready'); p.add_argument('--release-file')
 p.add_argument('--max-seconds',type=int,default=1800)
 p.add_argument('--lock-image')
 a=p.parse_args()
 if not re.fullmatch('[0-9a-f]{40}',a.sha) or a.go!='APPROVED:'+a.sha: fail('exact_controller_go_required')
 if a.mode=='restore-private':
  state=json.loads(pathlib.Path(a.private_state).read_text())
  if state['sha']!=a.sha: fail('restore_source_mismatch')
  print(json.dumps(call(a.db_container,'db-restore',state))); return
 if not a.ready or not a.release_file: fail('explicit_control_paths_required')
 hold(a)
if __name__=='__main__':
 try: main()
 except Exception as exc:
  print(json.dumps({'phase':'refused','error_type':type(exc).__name__,
                   'error_code':str(exc) if re.fullmatch('[A-Za-z0-9_]+',str(exc)) else 'details_redacted'})); sys.exit(1)
