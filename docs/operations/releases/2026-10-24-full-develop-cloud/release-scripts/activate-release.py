import json,pathlib,subprocess,sys,time,urllib.request,hashlib,datetime
r=pathlib.Path(sys.argv[1]);p=json.loads((r/'prepared.json').read_text());b=json.loads((r/'built.json').read_text());old=json.loads((r/'rollback/container.private.json').read_text());name=old['Name'].lstrip('/');current=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
assert current['Id']==old['Id'] and current['Image']==old['Image'],'Live release changed since preparation'
assert subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',b['tag']],text=True).strip()==b['image']
# Source and receiver advisory locks must be absent. Operator also pauses future TEST kifu runs.
probe="from sqlalchemy import text;from katrain.web.core.db import engine; c=engine.connect(); x=c.execute(text(\"select count(*) from pg_locks where locktype='advisory' and classid=:a and objid in (:b,:d) and granted\"),{'a':1263093333,'b':1229866801,'d':1347764785}).scalar(); assert x==0, 'A kifu source/receiver writer is active';c.close()"
# Compute the actual bigint halves rather than relying on a hand-transcribed key.
a=0x4B494655494E4731;d=0x4B49465550554231;probe=probe.replace('1263093333',str(a>>32)).replace('1229866801',str(a&0xffffffff)).replace('1347764785',str(d&0xffffffff))
subprocess.run(['docker','exec',name,'python3','-c',probe],check=True)
subprocess.run(p['activate_command'],check=True)
try:
 for i in range(90):
  try:
   with urllib.request.urlopen('http://127.0.0.1:8001/api/v1/health',timeout=3) as response:
    health=json.load(response)
   if health.get('status')=='ok':break
  except Exception:pass
  time.sleep(1)
 else:raise RuntimeError('New web health did not become ready')
 new=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert new['Image']==b['image']
 oldenv=dict(x.split('=',1) for x in old['Config']['Env']);newenv=dict(x.split('=',1) for x in new['Config']['Env']);delta={k for k in set(oldenv)|set(newenv) if oldenv.get(k)!=newenv.get(k)};assert delta<={'KATRAIN_BUILD_SHA','KATRAIN_FRONTEND_BUILD_SHA'},delta
 for key in ['KATRAIN_BUILD_SHA','KATRAIN_FRONTEND_BUILD_SHA']:assert newenv[key]==b['revision']
 assert old['Mounts']==new['Mounts'],'Mount changed'
 for k in ['User','Cmd','Entrypoint','WorkingDir']:assert old['Config'][k]==new['Config'][k],k
 verify="import pathlib,json,hashlib,os;r=pathlib.Path('/app');m=json.loads((r/'.full-develop-source-manifest.json').read_text());bad=[p for p,h in m['files'].items() if hashlib.sha256(os.readlink(r/p).encode() if (r/p).is_symlink() else (r/p).read_bytes()).hexdigest()!=h];assert not bad,bad;assert not (r/'katrain/web/static/assets/galaxy-brand-latin-10e120749af9.css').exists();print(len(m['files']))"
 count=subprocess.check_output(['docker','exec',name,'python3','-c',verify],text=True).strip()
 receipt={'source_revision':b['revision'],'container_id':new['Id'],'image':new['Image'],'started_at':new['State']['StartedAt'],'full_source_verified_files':int(count),'only_environment_changes':sorted(delta),'mounts_and_runtime_config_preserved':True,'health':health,'activated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'compose_files':new['Config']['Labels']['com.docker.compose.project.config_files'].split(','),'rollback_directory':str(r/'rollback')}
 (r/'activated.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
except BaseException:
 subprocess.run(p['rollback_command'],check=True)
 raise
