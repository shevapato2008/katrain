#!/usr/bin/env python3
import os,sys,json,time,pathlib,socket,hashlib,subprocess,importlib.util,datetime
assert os.geteuid()==0 and socket.gethostname()=='10-60-219-118'
W='migrate-final-20261027-0330'
assert sys.argv[1:]==['APPROVED:'+W]
B=pathlib.Path('/var/lib/ucloud-migration-20261027');os.umask(0o077)
C=B/'fence-controller';S=C/'status.private.json'
def save(p,v):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(v,sort_keys=True));t.chmod(0o600);os.replace(t,p)
def phase(v):save(S,{'WindowID':W,'Phase':v,'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()});print(v,flush=True)
def run(a,**kw):return subprocess.run(a,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kw)
def insp(n):return json.loads(run(['docker','inspect',n]).stdout)[0]
rpath=C/'test-ready.private.json';ready=json.loads(rpath.read_text())
assert ready['phase']=='paused_idle_lock_held' and ready['source_develop_sha']=='e9b4d3ecce03b3269f12922a476fd6d6c6545547'
assert ready['expires_unix']>time.time()+300
control=json.loads(pathlib.Path('/var/lib/ucloud-control-'+W+'/controls.private.json').read_text())
assert control['window_id']==W and control['phase']=='paused'
expected=json.loads((C/'expected-container-identity.private.json').read_text())
spec=importlib.util.spec_from_file_location('finalop',C/'final-data-operator.py');op=importlib.util.module_from_spec(spec);spec.loader.exec_module(op)
for n in op.WRITERS:
 c=insp(n);assert c['Id']==expected[n]['ID'] and c['Image']==expected[n]['Image']
assert not op.receiver_processes()
keys=pathlib.Path('/home/kifu-receiver/.ssh/authorized_keys')
backup=C/'receiver-authorized_keys.before'
assert keys.exists() and keys.stat().st_size>0 and not backup.exists()
data=keys.read_bytes();backup.write_bytes(data);backup.chmod(0o600)
phase('sealing_receiver_future_authorization')
with keys.open('wb') as f:f.flush();os.fsync(f.fileno())
assert keys.stat().st_size==0 and not op.receiver_processes()
phase('graceful_nginx_quit')
# Preserve in-flight requests/WS; never escalate to SIGKILL.
run(['nginx','-s','quit'])
for i in range(120):
 p=run(['pgrep','-x','nginx'],) if False else subprocess.run(['pgrep','-x','nginx'],stdout=subprocess.PIPE)
 if p.returncode==1:break
 time.sleep(1)
else:raise RuntimeError('nginx_active_connections_require_owner')
phase('normal_stop_old_writers_no_sigkill')
run(['docker','stop','--signal','SIGTERM','--timeout','-1']+op.WRITERS)
op.controllers_only();op.receiver_gate();op.pg_gate(True)
phase('capturing_cron_backups')
archive=C/'cron-tutorial-backups.tar'
with archive.open('wb') as f:
 p=subprocess.run(['docker','cp','katrain-ucloud-katrain-cron-1:/app/data/tutorial_backups/.','-'],stdout=f,stderr=subprocess.PIPE)
 assert p.returncode==0
archive.chmod(0o600)
containers={}
for n in op.WRITERS:
 c=insp(n);s=c['State'];assert not s['Running'] and s['Status']=='exited' and s['Pid']==0
 containers[n]={'ContainerID':c['Id'],'ImageID':c['Image'],'Running':False,'Status':'exited','PID':0,'FinishedAt':s['FinishedAt']}
fence={'Schema':1,'WindowID':W,'Owner':'migration-controller','SourceHostname':op.SOURCE,'TargetHostname':op.TARGET,
 'OldWritersFenced':True,'RecordedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'SourceContainers':containers,'ReceiverActiveKeysBytes':0,'ReceiverProcesses':0,'PreparedTransactions':0,'WritableClientTransactions':0,
 'ControlStateSHA256':control['plan_sha256'],
 'TestWriterGate':{'ReadySHA256':hashlib.sha256(rpath.read_bytes()).hexdigest(),'ExpiresUnix':ready['expires_unix'],'HolderContainerID':ready['lock_container_id'],'SourceDevelopSHA':ready['source_develop_sha'],'StageLockInode':ready['lock_inode']}}
assert ready['expires_unix']>time.time()+60
op.source_gate(fence)
fp=B/('source-fence-'+W+'.private.json');assert not fp.exists();save(fp,fence)
phase('old_writers_fenced_final_export_allowed')
print(json.dumps({'FenceSHA256':hashlib.sha256(fp.read_bytes()).hexdigest(),'Path':str(fp),'ExpiresUnix':ready['expires_unix']}),flush=True)
