CFG={'name': 'PROD', 'host': 'ucloud-v100', 'socket': '/tmp/kifu-hourly-prod-active-20261020.sock', 'stage': '/home/ubuntu/kifu-hourly-incremental-20261019', 'docker': ['sudo', '-n', 'docker'], 'project': 'katrain-ucloud', 'container': 'katrain-ucloud-katrain-web-1', 'old_id': '5674d34623dc8a906f509ed26b22b45f26afc8558798291ad2a7992bade644d3', 'old_image': 'sha256:bbcdd5b1b90731d4781abfca13d0fbe6416b158d0a8f84cf6d39d205e95e7f0e', 'image': 'sha256:af3d02331409a724a2bd7901ac26504d8ea86f24c0572d91027d233397b476c5', 'user': '10001:10001', 'critical': ['katrain-ucloud-katrain-cron-1', 'katrain-ucloud-postgres-1', 'katrain-ucloud-katago-cron-1', 'katrain-ucloud-katago-web-1']}
PREPARED={'host': 'PROD', 'final': 'e23ac4105ad6ec770c4ebedf03e389b20768ee6c', 'compose_project': 'katrain-ucloud', 'service': 'katrain-web', 'working_directory': '/home/ubuntu/kifu-hourly-incremental-20261019', 'compose_files': ['/home/ubuntu/kifu-hourly-incremental-20261019/web-base.private.json', '/home/ubuntu/kifu-hourly-incremental-20261019/release-a/release-final.override.json', '/home/ubuntu/kifu-hourly-incremental-20261019/web-final.override.yml'], 'compose_file_sha256': {'/home/ubuntu/kifu-hourly-incremental-20261019/web-base.private.json': 'b03a307954cd07e925ae20b2b993923e4f17e6c30b00ab73d5562a1c0aeb71ab', '/home/ubuntu/kifu-hourly-incremental-20261019/release-a/release-final.override.json': '8a08521fd3119d3013471ca9f5ed08ac20ce72355bd13385767433a605e71154', '/home/ubuntu/kifu-hourly-incremental-20261019/web-final.override.yml': '0d6636fa75fe2ecda87d8b3ce31d510e78bc120a66b59b3300b24dc922d4ebf3'}, 'old_effective_config_sha256': '77185713d0d43da3ab0bd8767e329d9a8a634ecbcd916257ba9b610c02e07e2e', 'new_effective_config_sha256': '10be26d2d64020ece706b4703097acaa68ae5801d95684afc6ab9055ad564f5a', 'candidate_override_sha256': '1e72cde0413118c53282bbdd83b2061dedc5a1c938787e4c0dc70d95e2a26150', 'allowed_changes': ['services.katrain-web.image', 'services.katrain-web.environment.KATRAIN_BUILD_SHA'], 'full_effective_config_identity_only': True, 'config_quiet': 'PASS', 'live_web': {'id': '5674d34623dc8a906f509ed26b22b45f26afc8558798291ad2a7992bade644d3', 'image': 'sha256:bbcdd5b1b90731d4781abfca13d0fbe6416b158d0a8f84cf6d39d205e95e7f0e', 'started_at': '2026-10-20T03:06:33.310308634Z', 'restart_count': 0}, 'candidate_image': 'sha256:af3d02331409a724a2bd7901ac26504d8ea86f24c0572d91027d233397b476c5', 'candidate_tag': 'katrain-kifu-hourly:e23ac4105', 'runtime_user': '10001:10001', 'critical_others': {'katrain-ucloud-katrain-cron-1': {'id': 'c66398c2cf199b67cc7419561b7ec2f15754dfc01e3d129c2168215a2438e225', 'image': 'sha256:9b28e8be9b77deb63f99cac2b076aac9df584a521f9b00989d6cc2bc920adb79', 'started_at': '2026-10-10T18:04:39.203555945Z', 'restart_count': 0}, 'katrain-ucloud-postgres-1': {'id': 'bc2f47b264e16c2e230713c8771d27085984588e2fd7c85719f5467937219d6c', 'image': 'sha256:3d0f7584ed7d04e27fa050d6683a74746608faf21f202be78460d679cc56461f', 'started_at': '2026-07-25T14:27:13.320636901Z', 'restart_count': 0}, 'katrain-ucloud-katago-cron-1': {'id': 'd43e95882cc8630370935a8614504fff0737c85d0c817693bb713fd05544b084', 'image': 'sha256:b242fd2a379b28b7dda5cf965e41230324bc825e7d23cd4aa1c0c81f7a16798e', 'started_at': '2026-10-02T08:54:00.567946419Z', 'restart_count': 0}, 'katrain-ucloud-katago-web-1': {'id': '130b77bc74f07e561d8727fe59be0bd8caa428130a589b31dd4b82ab113363b4', 'image': 'sha256:efdeb9de4f64faf68072d236a3f73ff5c1f38af9566d78a52af78ec03f3026f3', 'started_at': '2026-08-29T19:44:14.684351183Z', 'restart_count': 0}}, 'other_container_count': 19, 'configuration_written': False, 'service_action_performed': False}

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
