from copy import deepcopy
from pathlib import Path
import json,os,subprocess,yaml
stage=Path('/mnt/disk1/fan/kifu-hourly-incremental-20261019')
final='e23ac4105ad6ec770c4ebedf03e389b20768ee6c'
image='katrain-cron:kifu-hourly-e23ac4105'
expected_image='sha256:95f4308b36b5844e91aec8ce14e3cbe8c3fa982dcc6bd00cd5efb34db410973e'
def run(args,timeout=40,input=None):
 r=subprocess.run(args,capture_output=True,text=True,timeout=timeout,input=input)
 if r.returncode:raise RuntimeError('command failed: '+args[0]+' '+r.stderr[-1000:])
 return r.stdout
compose=['docker','compose','--project-directory','/home/fan/Repositories/katrain','--env-file','/home/fan/Repositories/katrain/.env','-p','katrain','-f','/home/fan/Repositories/katrain/docker-compose.yml']
active=stage/'cron-kifu.override.yml'
def config(path):return json.loads(run(compose+['-f',str(path),'config','--format','json']))
old=config(active)
meta=json.loads(run(['docker','inspect','katrain-cron']))[0]
assert meta['Id']=='01e46e1243651b240561d67e7fac501187648ffb078d5829dfb19d97c67c26ac'
assert json.loads(run(['docker','image','inspect',image]))[0]['Id']==expected_image
pause=run(['docker','exec','katrain-cron','python3','-c',"from sqlalchemy import select;from katrain.cron.db import engine;from katrain.cron.models import CronJobControlDB; c=engine.connect();r=c.execute(select(CronJobControlDB.__table__).where(CronJobControlDB.job_name=='kifu_ingest')).mappings().one();assert r['paused'] and r['changed_by']=='codex-hourly-recovery-20261020';print('paused')"])
assert pause.strip()=='paused'
others={name:run(['docker','inspect',name,'--format','{{.Id}}']).strip() for name in ['katrain-web','katrain-postgres','katago-gpu1','kifu1000-supervisor-20261018']}
data=yaml.safe_load(active.read_bytes()); data['services']['katrain-cron']['image']=image;data['services']['katrain-cron']['environment']['KATRAIN_BUILD_SHA']=final
pending=stage/'cron-kifu.e23ac-prepared.yml'
fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:yaml.safe_dump(data,f,sort_keys=False)
new=config(pending);expected=deepcopy(old);expected['services']['katrain-cron']['image']=image;expected['services']['katrain-cron']['environment']['KATRAIN_BUILD_SHA']=final
assert new==expected,'effective config changed beyond image/build SHA'
assert new['services']['katrain-cron']['environment']['KATAGO_URL']=='http://host.docker.internal:8002'
backup=stage/'cron-kifu.pre-e23ac.yml'; fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'wb') as f:f.write(active.read_bytes())
os.replace(pending,active)
run(compose+['-f',str(active),'config','--quiet'])
run(compose+['-f',str(active),'up','-d','--no-deps','--no-build','--force-recreate','katrain-cron'],timeout=90)
after=json.loads(run(['docker','inspect','katrain-cron']))[0]
assert after['Image']==expected_image and after['State']['Running']
assert all(run(['docker','inspect',name,'--format','{{.Id}}']).strip()==ident for name,ident in others.items())
out={'cron_id':after['Id'],'image':after['Image'],'build_sha':final,'other_containers_unchanged':list(others),'job_pause_preserved':True,'restart_count':after['RestartCount'],'started_at':after['State']['StartedAt']}
(stage/'cron-e23ac-deployment.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
