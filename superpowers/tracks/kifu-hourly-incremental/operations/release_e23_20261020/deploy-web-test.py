CFG={'name': 'TEST', 'host': 'home-ubuntu', 'socket': '/tmp/kifu-hourly-home-active-20261020.sock', 'stage': '/mnt/disk1/fan/kifu-hourly-incremental-20261019', 'docker': ['docker'], 'project': 'katrain', 'container': 'katrain-web', 'old_id': '4229d8e0b5ec489ebb5e9aa2f1b63d05a64506a65898efce50aceb880dad0122', 'old_image': 'sha256:4dc8d19a7027c3774112d9eb60b1768721fce0f1e167b7473458d20e8dbfe97b', 'image': 'sha256:42ba8fe019fd9857a835db7ad1d135041a61522d1f60c293387f1c6e2f831d48', 'user': 'root', 'critical': ['katrain-cron', 'katrain-postgres', 'katago-gpu1', 'katago-gpu0', 'kifu1000-supervisor-20261018', 'kifu1000-engine-gpu0-20261018']}
PREPARED={'host': 'TEST', 'final': 'e23ac4105ad6ec770c4ebedf03e389b20768ee6c', 'compose_project': 'katrain', 'service': 'katrain-web', 'working_directory': '/mnt/disk1/fan/kifu-hourly-incremental-20261019', 'compose_files': ['/mnt/disk1/fan/kifu-hourly-incremental-20261019/web-base.private.json', '/mnt/disk1/fan/kifu-hourly-incremental-20261019/release-a/release-final.override.json', '/mnt/disk1/fan/kifu-hourly-incremental-20261019/web-final.override.yml'], 'compose_file_sha256': {'/mnt/disk1/fan/kifu-hourly-incremental-20261019/web-base.private.json': 'c41f3fed3c3103b456e23905492233ba84fe6070dfdf06ea8bb584bb2c67125c', '/mnt/disk1/fan/kifu-hourly-incremental-20261019/release-a/release-final.override.json': '8a08521fd3119d3013471ca9f5ed08ac20ce72355bd13385767433a605e71154', '/mnt/disk1/fan/kifu-hourly-incremental-20261019/web-final.override.yml': '0d6636fa75fe2ecda87d8b3ce31d510e78bc120a66b59b3300b24dc922d4ebf3'}, 'old_effective_config_sha256': 'f49b1197f51f94fc47bf879fae065283d36f773d753b90894b8463709ae955a3', 'new_effective_config_sha256': '2a26b7e0de914038c919827a252476378a49397c097fdc4dcd293a05420360b3', 'candidate_override_sha256': '1e72cde0413118c53282bbdd83b2061dedc5a1c938787e4c0dc70d95e2a26150', 'allowed_changes': ['services.katrain-web.image', 'services.katrain-web.environment.KATRAIN_BUILD_SHA'], 'full_effective_config_identity_only': True, 'config_quiet': 'PASS', 'live_web': {'id': '4229d8e0b5ec489ebb5e9aa2f1b63d05a64506a65898efce50aceb880dad0122', 'image': 'sha256:4dc8d19a7027c3774112d9eb60b1768721fce0f1e167b7473458d20e8dbfe97b', 'started_at': '2026-10-20T03:04:03.998588278Z', 'restart_count': 0}, 'candidate_image': 'sha256:42ba8fe019fd9857a835db7ad1d135041a61522d1f60c293387f1c6e2f831d48', 'candidate_tag': 'katrain-kifu-hourly:e23ac4105', 'runtime_user': 'root', 'critical_others': {'katrain-cron': {'id': '01e46e1243651b240561d67e7fac501187648ffb078d5829dfb19d97c67c26ac', 'image': 'sha256:0d6e49501b86cbdcc5fd080d2208d645b13d86671ac73a5dd6f3dce037c6d1f0', 'started_at': '2026-10-20T03:53:12.020664009Z', 'restart_count': 0}, 'katrain-postgres': {'id': 'b32fad7f168eebf03ef9650f094449964fe924541cae4f6b979d5f4ccbb5bf35', 'image': 'sha256:36a937f48ac758aef4bb5254440933c81fc970f6dbf9f96b87542b4dda7e7b6b', 'started_at': '2026-08-11T04:40:20.031540875Z', 'restart_count': 0}, 'katago-gpu1': {'id': 'b75a25eef03d61f641d676ff4ac886792c24594f0a4aa43620db6db8a7a3687c', 'image': 'sha256:7004f5721d21dac82831ba136d1e98b4c809e958a0032395da2025bd645ca589', 'started_at': '2026-10-02T08:43:48.752509172Z', 'restart_count': 0}, 'katago-gpu0': {'id': '2f589d0d1f82c6728a228bc9a77ce48bfcd73b617168b431b75efaf0df3734a8', 'image': 'sha256:462515e83c36e1ff4aa31f91aca1c259c6afc8dc4b22815d23a56e9d95a3cf94', 'started_at': '2026-08-25T09:19:40.53463688Z', 'restart_count': 0}, 'kifu1000-supervisor-20261018': {'id': 'fa5cabac0fc5d5f1ea2e3e3adbd09449bde7c7c1cab3bc8fb820efb567960902', 'image': 'sha256:f0e3598e036ffade371b6ec110f946abbbdcbb0459fa9fc22da37155c8a4feb4', 'started_at': '2026-10-18T07:45:39.751227404Z', 'restart_count': 0}, 'kifu1000-engine-gpu0-20261018': {'id': 'a92efaca010d4b0e46e32fb9d9790fc11bde6deafd38cacf90dbf131e5533970', 'image': 'sha256:7004f5721d21dac82831ba136d1e98b4c809e958a0032395da2025bd645ca589', 'started_at': '2026-10-18T07:40:52.781384459Z', 'restart_count': 0}}, 'other_container_count': 76, 'configuration_written': False, 'service_action_performed': False}

from copy import deepcopy
from hashlib import sha256
import json,os
from pathlib import Path
import subprocess
import yaml
FINAL='e23ac4105ad6ec770c4ebedf03e389b20768ee6c'
TAG='katrain-kifu-hourly:e23ac4105'
OLD_SHA='9145274496ace58dfb8dbd0ce9bb9c50a80bdfc3'
def require(ok,message):
    if not ok:raise RuntimeError(message)
def run(args,timeout=40,input=None):
    result=subprocess.run(args,text=True,capture_output=True,input=input,timeout=timeout,cwd=CFG['stage'])
    require(result.returncode==0,'Docker inspect/render/apply failed; private command output suppressed')
    return result.stdout
def digest(value):return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def inspect(name):return json.loads(run(CFG['docker']+['inspect',name]))[0]
def container_state(row):return {'id':row['Id'],'image':row['Image'],'started_at':row['State']['StartedAt'],'restart_count':row['RestartCount']}
def other_containers():
    ids=run(CFG['docker']+['ps','-aq']).split()
    rows=json.loads(run(CFG['docker']+['inspect',*ids])) if ids else []
    return {row['Name'].lstrip('/'):container_state(row) for row in rows if row['Name'].lstrip('/')!=CFG['container']}
def compose(files):
    command=CFG['docker']+['compose','-p',CFG['project']]
    for path in files:command+=['-f',str(path)]
    return command
def config(files,input=None,quiet=False):
    raw=run(compose(files)+['config']+(['--quiet'] if quiet else ['--format','json']),input=input)
    return None if quiet else json.loads(raw)
def preflight():
    stage=Path(CFG['stage']);active=stage/'web-final.override.yml'
    files=[stage/'web-base.private.json',stage/'release-a/release-final.override.json',active]
    require(all(path.is_file() and not path.is_symlink() for path in files),'persistent compose inputs missing or symlinked')
    live=inspect(CFG['container']);labels=live['Config']['Labels']
    require(live['Id']==CFG['old_id'] and live['Image']==CFG['old_image'] and live['State']['Running'],'old Web identity changed')
    require(labels['com.docker.compose.project']==CFG['project'] and labels['com.docker.compose.service']=='katrain-web','compose project/service differs')
    require(labels['com.docker.compose.project.working_dir']==str(stage),'compose working directory differs')
    require(labels['com.docker.compose.project.config_files']==','.join(map(str,files)),'live compose input order differs')
    image=json.loads(run(CFG['docker']+['image','inspect',TAG]))[0]
    require(image['Id']==CFG['image'] and image['Config']['User']==CFG['user'],'candidate image identity/user differs')
    require('KATRAIN_BUILD_SHA='+FINAL in image['Config']['Env'] and image['Config']['Labels']['org.opencontainers.image.revision']==FINAL,'candidate full SHA/OCI differs')
    old=config(files)
    require(old['services']['katrain-web']['image']=='katrain-kifu-hourly:914527449' and old['services']['katrain-web']['environment']['KATRAIN_BUILD_SHA']==OLD_SHA,'old effective identity differs')
    original=active.read_bytes();data=yaml.safe_load(original)
    data['services']['katrain-web']['image']=TAG
    data['services']['katrain-web']['environment']['KATRAIN_BUILD_SHA']=FINAL
    candidate=yaml.safe_dump(data,sort_keys=False)
    new=config([*files[:-1],'-'],input=candidate)
    expected=deepcopy(old);expected['services']['katrain-web']['image']=TAG;expected['services']['katrain-web']['environment']['KATRAIN_BUILD_SHA']=FINAL
    require(new==expected,'full effective config differs beyond Web image/build SHA')
    config([*files[:-1],'-'],input=candidate,quiet=True)
    others=other_containers()
    require(all(name in others for name in CFG['critical']),'critical non-Web container missing')
    metadata={'host':CFG['name'],'final':FINAL,'compose_project':CFG['project'],'service':'katrain-web','working_directory':str(stage),'compose_files':list(map(str,files)),'compose_file_sha256':{str(path):sha256(path.read_bytes()).hexdigest() for path in files},'old_effective_config_sha256':digest(old),'new_effective_config_sha256':digest(new),'candidate_override_sha256':sha256(candidate.encode()).hexdigest(),'allowed_changes':['services.katrain-web.image','services.katrain-web.environment.KATRAIN_BUILD_SHA'],'full_effective_config_identity_only':True,'config_quiet':'PASS','live_web':container_state(live),'candidate_image':CFG['image'],'candidate_tag':TAG,'runtime_user':CFG['user'],'critical_others':{name:others[name] for name in CFG['critical']},'other_container_count':len(others),'configuration_written':False,'service_action_performed':False}
    return metadata,files,original,candidate,new,others

import argparse,time
from urllib.request import urlopen

def write_new_private(path,raw):
    require(not path.exists() and not path.is_symlink(),'prepared/backup path already exists; inspect prior attempt')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as file:file.write(raw)

def main():
    parser=argparse.ArgumentParser(description='Fixed e23 Web-only deployment; execute only after root signals verification complete.')
    parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    require(args.apply,'No action: --apply is required after root deployment signal')
    metadata,files,original,candidate,new,others=preflight()
    for field in ['compose_file_sha256','old_effective_config_sha256','new_effective_config_sha256','candidate_override_sha256','live_web','critical_others']:
        require(metadata[field]==PREPARED[field],'prepared deployment inputs changed: '+field)
    stage=Path(CFG['stage']);active=files[-1]
    backup=stage/('web-final.pre-e23.'+CFG['name']+'.override.yml')
    pending=stage/('.web-final.e23.'+CFG['name']+'.prepared.yml')
    write_new_private(backup,original);write_new_private(pending,candidate.encode())
    require(config([*files[:-1],pending])==new,'persisted candidate render differs')
    require(active.read_bytes()==original,'active Web override changed during preparation')
    os.replace(pending,active)
    config(files,quiet=True)
    # Exactly the previously approved Web-only selector; no dependencies/builds.
    run(compose(files)+['up','-d','--no-deps','--no-build','--force-recreate','katrain-web'],timeout=120)
    after=inspect(CFG['container'])
    require(after['Id']!=CFG['old_id'] and after['Image']==CFG['image'] and after['State']['Running'],'new Web is not running expected image')
    require('KATRAIN_BUILD_SHA='+FINAL in after['Config']['Env'],'running build SHA differs')
    deadline=time.monotonic()+60;healthy=False
    while time.monotonic()<deadline:
        try:
            with urlopen('http://127.0.0.1:8001/api/v1/health',timeout=5) as response:
                healthy=response.status==200 and json.load(response).get('status')=='ok'
        except (OSError,ValueError):pass
        if healthy:break
        time.sleep(2)
    require(healthy,'Web health did not become ready; do not retry deployment blindly')
    after=inspect(CFG['container']);require(after['RestartCount']==0 and after['State']['Running'],'new Web restarted during health check')
    current=other_containers()
    require(all(current.get(name)==state for name,state in others.items()),'a non-Web container identity/start/restart count changed')
    require(config(files)==new,'effective config changed after deployment')
    receipt={'host':CFG['name'],'final':FINAL,'web':container_state(after),'health':'PASS','non_web_containers_preserved':len(others),'critical_non_web_containers_preserved':CFG['critical'],'backup':str(backup),'full_effective_config_identity_only':True}
    path=stage/('web-e23-deployment.'+CFG['name']+'.json');write_new_private(path,(json.dumps(receipt,indent=2)+'\n').encode())
    print(json.dumps(receipt))

if __name__=='__main__':
    try:main()
    except Exception as error:
        # No captured command output/config/credentials are printed.
        print(json.dumps({'status':'error','error_type':type(error).__name__,'error':'e23 Web deployment stopped; inspect private inputs and live receipt before any retry'}))
        raise SystemExit(2)
