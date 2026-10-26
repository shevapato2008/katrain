"""Host-local inventory/build/deploy. Mutating modes require an exact SHA GO token."""
import argparse, copy, datetime, fcntl, hashlib, json, os, pathlib, re, socket, subprocess, sys, tarfile, time, urllib.request
from prepare_bundle import RUNTIME
ROOT=pathlib.Path(__file__).resolve().parent
HOSTS={'home-ubuntu':{'web':'katrain-web','cron':'katrain-cron'},
       'ucloud-v100':{'web':'katrain-ucloud-katrain-web-1'}}
PUBLIC={'home-ubuntu':'https://go.sailorvoyage.top','ucloud-v100':'https://modelstella.com'}
def fail(code): raise RuntimeError(code)
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def filehash(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def run(args,input=None,timeout=120):
 p=subprocess.run(args,input=input,text=True,capture_output=True,timeout=timeout)
 if p.returncode:
  command_kind='_'.join(re.sub('[^A-Za-z0-9_]','_',x) for x in args[:2])
  # Exception class only, never the stderr message or a configured value.
  classes=re.findall(r'(?:^|\n)([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):',p.stderr)
  fail('subprocess_failed_'+command_kind+'_'+str(p.returncode)+('_'+classes[-1].split('.')[-1] if classes else ''))
 return p.stdout
def inspect(name): return json.loads(run(['docker','inspect',name]))[0]
def env(c): return dict(v.split('=',1) for v in c['Config'].get('Env',[]) if '=' in v)
def summary(c):
 return {'id':c['Id'],'name':c['Name'],'image_id':c['Image'],'image_tag':c['Config']['Image'],
         'started_at':c['State']['StartedAt'],'running':c['State']['Running'],
         'health':c['State'].get('Health',{}).get('Status'),'build_sha':env(c).get('KATRAIN_BUILD_SHA')}
def settings(c):
 e=env(c); e.pop('KATRAIN_BUILD_SHA',None)
 return {'env':e,'mounts':sorted(c['Mounts'],key=lambda x:x['Destination']),
         'host_config':c['HostConfig'],
         'config':{k:c['Config'].get(k) for k in ['User','Cmd','Entrypoint','WorkingDir','ExposedPorts','StopSignal','StopTimeout','Healthcheck']}}
def difference_paths(a,b,path=''):
 if isinstance(a,dict) and isinstance(b,dict):
  return [p for k in sorted(set(a)|set(b)) for p in difference_paths(a.get(k),b.get(k),path+'.'+k)]
 if isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
  return [p for i,(x,y) in enumerate(zip(a,b)) for p in difference_paths(x,y,path+'['+str(i)+']')]
 return [path] if a!=b else []
def other_containers(name):
 ids=run(['docker','ps','-aq']).split()
 return {c['Name']:{'id':c['Id'],'started_at':c['State']['StartedAt'],'running':c['State']['Running']}
         for c in (json.loads(run(['docker','inspect']+ids)) if ids else []) if c['Name']!='/'+name}
def compose_for(c):
 labels=c['Config']['Labels']; paths=labels['com.docker.compose.project.config_files'].split(',')
 args=['docker','compose','--project-name',labels['com.docker.compose.project'],
       '--project-directory',labels['com.docker.compose.project.working_dir']]
 for p in labels.get('com.docker.compose.project.environment_file','').split(','):
  if p: args+=['--env-file',p]
 for p in paths: args+=['-f',p]
 return args,paths
def resolved(args): return json.loads(run(args+['config','--format','json']))
def comparable(c,service):
 c=copy.deepcopy(c); c['services'][service].pop('image',None)
 c['services'][service].get('environment',{}).pop('KATRAIN_BUILD_SHA',None)
 return c
def probe(name,image=False,imports=False,kind='web'):
 code=(ROOT/'probe_runtime.py').read_text()
 payload=json.dumps({'extra':RUNTIME,'imports':imports,'kind':kind})
 if image:
  args=['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp',
        '-e','PYTHONDONTWRITEBYTECODE=1','--entrypoint','python3',name,'-c',code]
 else: args=['docker','exec','-i','-e','PYTHONDONTWRITEBYTECODE=1',name,'python3','-c',code]
 # Image checks need stdin too, without allocating a TTY or passing real runtime env.
 if image: args.insert(2,'-i')
 return json.loads(run(args,input=payload,timeout=120))
def receiver_idle():
 # Arguments may contain private data: retain only a boolean, never stdout/stderr.
 names=run(['docker','ps','--format','{{.Names}}']).split()
 names=[n for n in names if n in {'katrain-web','katrain-cron','katrain-ucloud-katrain-web-1'}]
 for name in names:
  lines=run(['docker','top',name,'-eo','pid,args']).splitlines()[1:]
  if any(('kifu_incremental.py' in s or 'katrain.kifu_ingest.orchestration' in s)
         and re.search(r'(^|\s)receive(\s|$)',s) for s in lines): fail('active_receiver_process')
 lines=run(['ps','-eo','args']).splitlines()[1:]
 if any('kifu_incremental.py' in s and re.search(r'(^|\s)receive(\s|$)',s)
        and not s.lstrip().startswith(('ps ','docker top ')) for s in lines): fail('active_host_receiver_process')
 return True
def maintenance_gate(path,source_sha):
 d=json.loads(pathlib.Path(path).read_text())
 if d.get('phase')!='paused_idle_lock_held' or d.get('host')!='home-ubuntu': fail('maintenance_not_ready')
 if d.get('source_develop_sha')!=source_sha or d.get('stage_lock')!='/mnt/disk1/fan/kifu-hourly-incremental-20261019/ingest-stage/.writer.lock': fail('maintenance_scope_mismatch')
 if time.time()>d['expires_unix']: fail('maintenance_expired')
 if d.get('lock_kind')!='isolated_docker': fail('isolated_lock_holder_required')
 os.kill(d['pid'],0)
 from maintenance import lock_container_gate
 holder=lock_container_gate(d,source_sha)
 out=run(['docker','exec','-i',d['db_container'],'python3','-c',(ROOT/'maintenance.py').read_text(),
          'db-status'],timeout=25)
 gate=json.loads(out)
 if not gate['paused'] or not gate['finished_not_before_started'] or gate['advisory_lock'] or gate['running_run_count']: fail('producer_not_paused_idle')
 receiver_idle(); return {'holder_pid':d['pid'],'lock_container':holder,'expires_unix':d['expires_unix'],'db_gate':gate}
def inventory(host,kind):
 name=HOSTS[host][kind]; c=inspect(name); compose,paths=compose_for(c); service=c['Config']['Labels']['com.docker.compose.service']
 config=resolved(compose)
 host_files={}
 if host=='ucloud-v100':
  wrapper='/usr/local/sbin/kifu-incremental-receive-root'
  host_files[wrapper]=filehash(wrapper) if pathlib.Path(wrapper).is_file() else None
 return {'host':host,'kind':kind,'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'before':summary(c),'settings_sha256':digest(settings(c)),
         'compose_service':service,'compose_files':paths,'compose_file_sha256':{p:filehash(p) for p in paths},
         'resolved_config_sha256':digest(config),'comparable_config_sha256':digest(comparable(config,service)),
         'other_containers':other_containers(name),'host_files_sha256':host_files,'runtime':probe(name,kind=kind),'receiver_idle':receiver_idle()}
def require_baseline(b,a):
 if b['host']!=a.host or b['kind']!=a.kind: fail('baseline_target_mismatch')
 current=inventory(a.host,a.kind)
 for k in ['before','settings_sha256','compose_service','compose_files','compose_file_sha256',
           'resolved_config_sha256','comparable_config_sha256','other_containers','host_files_sha256','runtime']:
  if current[k]!=b[k]: fail('fresh_baseline_changed_'+k)
 return inspect(HOSTS[a.host][a.kind])
def save(path,data):
 pathlib.Path(path).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n'); os.chmod(path,0o600)
def bundle(a):
 context=ROOT/'context'; context.mkdir(exist_ok=True)
 with tarfile.open(a.bundle) as t:
  if any(not m.isfile() or m.name.startswith('/') or '..' in pathlib.PurePosixPath(m.name).parts for m in t.getmembers()): fail('unsafe_archive')
  manifest=json.loads(t.extractfile('manifest.json').read())
  allowed=set(manifest['runtime_files_sha256'])|set(manifest['static_files_sha256'])|{'manifest.json'}
  if set(t.getnames())!=allowed or len(t.getnames())!=len(allowed): fail('archive_members_mismatch')
  if manifest['source_develop_sha']!=a.sha or set(manifest['runtime_files_sha256'])!=set(RUNTIME): fail('manifest_source_mismatch')
  if not manifest['static_files_sha256'] and (manifest.get('deployment_scope')!='backend-only' or manifest.get('ui_mode')!='inherited_unchanged' or not re.fullmatch('[0-9a-f]{40}',manifest.get('inherited_ui_source_sha',''))): fail('explicit_backend_only_ui_scope_required')
  t.extractall(context,filter='data')
 for p,h in {**manifest['runtime_files_sha256'],**manifest['static_files_sha256']}.items():
  if filehash(context/p)!=h: fail('bundle_hash_mismatch')
 return context,manifest
def candidate_check(c,b,m,kind):
 if any(c['source_files'].get(p)!=h for p,h in m['runtime_files_sha256'].items()): fail('candidate_source_hash_mismatch')
 for p,h in b['runtime']['source_files'].items():
  if p not in RUNTIME and c['source_files'].get(p)!=h: fail('protected_source_changed')
 if kind=='cron':
  if c['static_files']!=b['runtime']['static_files']: fail('cron_static_changed')
 else:
  if not m['static_files_sha256'] and (c['static_files']!=b['runtime']['static_files'] or c['active_static_graph']!=b['runtime']['active_static_graph']): fail('backend_only_inherited_ui_changed')
  if any(c['static_files'].get(p)!=h for p,h in m['static_files_sha256'].items()): fail('candidate_static_hash_mismatch')
  # Existing hashed chunks must remain available to open browser sessions.
  for p,h in b['runtime']['static_files'].items():
   if '/assets/' in p and re.search(r'-[A-Za-z0-9_-]{6,}\.',p) and c['static_files'].get(p)!=h: fail('old_hashed_asset_removed_or_replaced')
 if c.get('compile_imports')!='ok': fail('candidate_imports_failed')
def wait_health(name,kind):
 deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  c=inspect(name)
  if c['State']['Running'] and c['State'].get('Health',{}).get('Status') in {None,'healthy'}:
   if kind=='cron': return c
   try:
    with urllib.request.urlopen('http://127.0.0.1:8001/api/v1/health',timeout=5) as r:
     d=json.load(r)
     if r.status==200 and d.get('status')=='ok': return c
   except Exception: pass
  time.sleep(2)
 fail('service_health_timeout')
def http_checks(host,actual):
 result=[]
 for path in ['/api/v1/health','/galaxy/play','/kiosk/play/pvp/lobby']:
  url=PUBLIC[host]+path
  with urllib.request.urlopen(url,timeout=15) as response:
   body=response.read(); item={'url':url,'status':response.status,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
   if response.status!=200: fail('representative_http_status_failed')
   if path.endswith('/health'):
    data=json.loads(body)
    if data.get('status')!='ok': fail('public_health_failed')
   elif item['sha256']!=actual['static_files']['katrain/web/static/index.html']: fail('public_index_hash_mismatch')
   result.append(item)
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('mode',choices=['inventory','build','deploy']); p.add_argument('--host',choices=HOSTS,required=True)
 p.add_argument('--kind',choices=['web','cron'],required=True)
 for name in ['sha','go','baseline','bundle','candidate','receipt','maintenance-ready']:
  p.add_argument('--'+name)
 p.add_argument('--schema-receipts',nargs='*',default=[]); p.add_argument('--receiver-receipts',nargs='*',default=[])
 a=p.parse_args()
 if a.kind not in HOSTS[a.host]: fail('production_analysis_cron_forbidden')
 if a.mode=='inventory': print(json.dumps(inventory(a.host,a.kind),sort_keys=True,indent=2)); return
 if not a.sha or not re.fullmatch('[0-9a-f]{40}',a.sha) or a.go!='APPROVED:'+a.sha: fail('exact_controller_go_required')
 if not a.baseline or not a.bundle or not a.receipt: fail('explicit_paths_required')
 b=json.loads(pathlib.Path(a.baseline).read_text()); c= require_baseline(b,a)
 name=HOSTS[a.host][a.kind]; service=b['compose_service']; compose,paths=compose_for(c)
 context,m=bundle(a); session='kifu-ranks-'+a.sha[:12]+'-'+a.kind
 base_tag='katrain-rank-release:'+session+'-base'; tag='katrain-rank-release:'+session
 receipt={'host':a.host,'kind':a.kind,'source_develop_sha':a.sha,'phase':'preparing','before':b['before'],
          'baseline_sha256':filehash(a.baseline),'bundle_sha256':filehash(a.bundle),
          'model_calls':0,'source_collection':False,'lifespan_in_candidate':False}
 receipt.update({'deployment_scope':m.get('deployment_scope'),'ui_mode':m.get('ui_mode'),
                 'inherited_ui_source_sha':m.get('inherited_ui_source_sha')})
 switched=False
 try:
  if a.mode=='build':
   run(['docker','tag',c['Image'],base_tag])
   if json.loads(run(['docker','image','inspect',base_tag]))[0]['Id']!=c['Image']: fail('base_tag_race')
   dockerfile='FROM '+base_tag+'\n'
   for path in RUNTIME: dockerfile+='COPY '+path+' /app/'+path+'\n'
   if a.kind=='web' and m['static_files_sha256']:
    for path in ['katrain/web/static','katrain/web/static-kiosk-2d']: dockerfile+='COPY '+path+'/ /app/'+path+'/\n'
   dockerfile+='ENV KATRAIN_BUILD_SHA='+a.sha+'\nLABEL org.opencontainers.image.revision='+a.sha+'\n'
   (context/'Dockerfile').write_text(dockerfile)
   receiver_idle()
   run(['docker','build','--pull=false','--network=none','-t',tag,'-f',str(context/'Dockerfile'),str(context)],timeout=240)
   if json.loads(run(['docker','image','inspect',base_tag]))[0]['Id']!=c['Image']: fail('base_tag_race')
   new_image=json.loads(run(['docker','image','inspect',tag]))[0]['Id']
   candidate=probe(tag,image=True,imports=True,kind=a.kind); candidate_check(candidate,b,m,a.kind)
   require_baseline(b,a)
   receipt.update({'phase':'candidate_verified','candidate_image_id':new_image,'candidate_tag':tag,'base_tag':base_tag,
                   'runtime':candidate,'runtime_settings_sha256':b['settings_sha256']})
   save(a.receipt,receipt); print(json.dumps({'phase':receipt['phase'],'receipt':a.receipt,'candidate_image_id':new_image})); return
  if not a.candidate: fail('candidate_receipt_required')
  built=json.loads(pathlib.Path(a.candidate).read_text())
  if any(built.get(k)!=v for k,v in {'phase':'candidate_verified','host':a.host,'kind':a.kind,'source_develop_sha':a.sha,
                                  'baseline_sha256':filehash(a.baseline),'bundle_sha256':filehash(a.bundle)}.items()): fail('candidate_receipt_mismatch')
  if json.loads(run(['docker','image','inspect',built['candidate_tag']]))[0]['Id']!=built['candidate_image_id']: fail('candidate_tag_changed')
  schemas=[json.loads(pathlib.Path(x).read_text()) for x in a.schema_receipts]
  needed={a.host} if a.kind=='web' else set(HOSTS)
  if {d['host'] for d in schemas if d.get('phase')=='schema_verified' and d.get('source_develop_sha')==a.sha}!=needed: fail('schema_gates_missing')
  if a.kind=='cron':
   receivers=[json.loads(pathlib.Path(x).read_text()) for x in a.receiver_receipts]
   if {d['host'] for d in receivers if d.get('phase')=='deployed_verified' and d.get('kind')=='web' and d.get('source_develop_sha')==a.sha}!=set(HOSTS): fail('both_receivers_must_precede_producer')
  if a.host=='home-ubuntu':
   if not a.maintenance_ready: fail('live_maintenance_holder_required')
   receipt['maintenance_gate']=maintenance_gate(a.maintenance_ready,a.sha)
  receiver_idle(); candidate_check(probe(built['candidate_tag'],image=True,imports=True,kind=a.kind),b,m,a.kind)
  oldconfig=resolved(compose); override=ROOT/(session+'.override.json'); rollback=ROOT/(session+'.rollback.json')
  save(override,{'services':{service:{'image':built['candidate_tag'],'environment':{'KATRAIN_BUILD_SHA':a.sha}}}})
  old_sha=env(c).get('KATRAIN_BUILD_SHA')
  old_service={'image':built['base_tag']}
  if old_sha is not None: old_service['environment']={'KATRAIN_BUILD_SHA':old_sha}
  save(rollback,{'services':{service:old_service}})
  if json.loads(run(['docker','image','inspect',built['base_tag']]))[0]['Id']!=c['Image']: fail('rollback_base_tag_changed')
  newcompose=compose+['-f',str(override)]; rollbackcmd=compose+['-f',str(rollback),'up','-d','--no-deps','--no-build','--pull','never','--force-recreate',service]
  if comparable(oldconfig,service)!=comparable(resolved(newcompose),service): fail('compose_changed_beyond_image_buildsha')
  command=newcompose+['up','-d','--no-deps','--no-build','--pull','never','--force-recreate',service]
  receipt.update({'phase':'switch_ready','candidate_image_id':built['candidate_image_id'],'compose_command':command,'rollback_command':rollbackcmd})
  save(a.receipt,receipt)
  require_baseline(b,a)
  if a.host=='home-ubuntu': maintenance_gate(a.maintenance_ready,a.sha)
  receiver_idle(); switched=True; run(command,timeout=150)
  post=wait_health(name,a.kind); actual=probe(name,imports=True,kind=a.kind)
  if actual!=built['runtime']: fail('actual_runtime_differs_from_candidate')
  if post['Image']!=built['candidate_image_id'] or env(post).get('KATRAIN_BUILD_SHA')!=a.sha: fail('actual_version_mismatch')
  if digest(settings(post))!=b['settings_sha256']:
   receipt['runtime_settings_difference_paths']=difference_paths(settings(c),settings(post))
   fail('runtime_settings_changed')
  if any(filehash(x)!=h for x,h in b['compose_file_sha256'].items()): fail('original_compose_changed')
  if other_containers(name)!=b['other_containers']: fail('other_containers_changed')
  if any((filehash(p) if pathlib.Path(p).is_file() else None)!=h for p,h in b['host_files_sha256'].items()): fail('receiver_wrapper_changed')
  if a.host=='home-ubuntu': maintenance_gate(a.maintenance_ready,a.sha)
  if a.kind=='web': receipt['http_checks']=http_checks(a.host,actual)
  receipt.update({'phase':'deployed_verified','after':summary(post),'runtime':actual,'other_containers_unchanged':True,
                  'settings_sha256':digest(settings(post)),'original_compose_unchanged':True,'rollback_required':False})
  save(a.receipt,receipt); print(json.dumps({'phase':receipt['phase'],'receipt':a.receipt,'after':receipt['after']}))
 except Exception as exc:
  receipt.update({'phase':'failed','error_type':type(exc).__name__,
                  'error_code':str(exc) if re.fullmatch('[A-Za-z0-9_]+',str(exc)) else 'details_redacted'})
  if switched:
   try:
    if a.host=='home-ubuntu': maintenance_gate(a.maintenance_ready,a.sha)
    receiver_idle(); run(rollbackcmd,timeout=150); restored=wait_health(name,a.kind)
    if restored['Image']!=b['before']['image_id'] or digest(settings(restored))!=b['settings_sha256']: fail('rollback_settings_mismatch')
    receipt['rollback']={'phase':'restored','after':summary(restored)}
   except Exception as rollback_error: receipt['rollback']={'phase':'requires_controller','error_type':type(rollback_error).__name__}
  save(a.receipt,receipt); print(json.dumps({'phase':'failed','receipt':a.receipt,'error_type':receipt['error_type'],'error_code':receipt['error_code']})); sys.exit(1)
if __name__=='__main__':
 try: main()
 except Exception as exc:
  # No private subprocess output or raw exception text is allowed to escape.
  print(json.dumps({'phase':'refused','error_type':type(exc).__name__,
                    'error_code':str(exc) if re.fullmatch('[A-Za-z0-9_]+',str(exc)) else 'details_redacted'})); sys.exit(1)
