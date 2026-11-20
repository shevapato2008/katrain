"""Generation-only, versioned TEST Admin client pinned to this campaign's source snapshot."""
import fcntl
import hashlib
import json
import os
import random
import re
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

HERE=Path(__file__).resolve().parent
SSH_LOCK_DIRECTORY=Path('/tmp/ogs-media-ssh-exec-20261114')


@contextmanager
def ssh_exec_slot():
    """At most four batch execs across processes, including reconnecting reads."""
    SSH_LOCK_DIRECTORY.mkdir(mode=0o700,exist_ok=True)
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        for slot in range(4):
            handle=(SSH_LOCK_DIRECTORY/f'slot-{slot}.lock').open('a')
            try:
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                handle.close()
                continue
            try:
                yield
            finally:
                fcntl.flock(handle,fcntl.LOCK_UN)
                handle.close()
            return
        time.sleep(0.1+random.random()*0.1)
    raise RuntimeError('Provider transport admission timed out before SSH; no request was sent. Read current state before retry.')


REMOTE=r'''
import hashlib,json,uuid
from datetime import datetime,timedelta,timezone
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.error import HTTPError
from jose import jwt
from sqlalchemy import text,select
from katrain.web.core.db import SessionLocal
from katrain.web.core.config import settings
from katrain.web.core.models_db import TutorialFigure,TutorialSection,TutorialChapter,TutorialMediaTask
from katrain.web.tutorials.manual_review import _registered_source_identity,board_approval
from katrain.web.admin.settings import check_startup
from katrain.web.admin.session import SERVICE_ISSUER,SERVICE_AUDIENCE,SERVICE_TYPE
def require(ok,reason):
 if not ok:raise ValueError(reason)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*a,**k):return None
config=check_startup();fid=action['figure_id'];method=action['method'];path=action['path'];body=action.get('body')
with SessionLocal() as db:
 db.execute(text('SET TRANSACTION READ ONLY'))
 identity=dict(db.execute(text('SELECT current_database() AS database_name,system_identifier::text FROM pg_control_system()')).mappings().one())
 require(identity=={'database_name':'katrain_db','system_identifier':'7596941912817897507'} and config.env=='test' and settings.S3_BUCKET=='tutorial-assets','wrong_test_identity')
 f=db.get(TutorialFigure,fid);require(f is not None and f.page==guard['page'],'figure_changed')
 book=db.scalar(select(TutorialChapter.book_id).join(TutorialSection,TutorialSection.chapter_id==TutorialChapter.id).where(TutorialSection.id==f.section_id))
 require(book==guard['book_id'] and digest(f.board_payload)==guard['board_sha256'],'book_or_board_changed')
 source,source_book=_registered_source_identity(f,db)
 require(source_book==book and source==guard['source_identity'],'source_changed')
 if method!='GET' and not path.endswith('/authorize-generation'):
  from katrain.web.tutorials.generation_authorization import generation_eligibility
  require(generation_eligibility(f,db=db)['authorized'],'current_generation_authorization_missing')
 if '/media-tasks/' in path:
  task=db.get(TutorialMediaTask,path.rsplit('/',1)[-1]);require(task is not None and task.figure_id==fid,'task_outside_scope')
 db.rollback()
now=datetime.now(timezone.utc)
claims={'iss':SERVICE_ISSUER,'aud':SERVICE_AUDIENCE,'type':SERVICE_TYPE,'sub':config.username,'env':config.env,'iat':int(now.timestamp()),'exp':int((now+timedelta(seconds=45)).timestamp()),'jti':'ogs-book-sources-20261113-'+uuid.uuid4().hex}
token=jwt.encode(claims,config.service_secret,algorithm='HS256')
req=Request('http://127.0.0.1:8010'+path,method=method,data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
try:
 with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=55) as response:status=response.status;raw=response.read()
except HTTPError as exc:status=exc.code;raw=exc.read()
print(json.dumps({'http_status':status,'json':json.loads(raw)},ensure_ascii=False,default=str))
'''

def _require_execution(fid,catalog,snapshot_sha256,operation):
    execution_id=os.environ.get('OGS_MEDIA_EXECUTION_ID')
    assert execution_id,'execution_identity_required'
    pointer_path=HERE/'active-execution.json'
    assert pointer_path.is_file(),'execution_pointer_missing'
    pointer=json.loads(pointer_path.read_text())
    assert pointer['generation_id']==execution_id,'execution_identity_mismatch'
    authorization_path=(HERE/pointer['authorization_path']).resolve()
    assert authorization_path==(HERE/'resume-full-20261117/execution-authorization.json').resolve(),'execution_authorization_path_invalid'
    raw=authorization_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==pointer['authorization_sha256'],'execution_authorization_changed'
    authorization=json.loads(raw)
    assert authorization['generation_id']==execution_id,'execution_identity_mismatch'
    assert authorization['status']=='running','execution_not_running'
    assert authorization['snapshot_sha256']==snapshot_sha256,'execution_snapshot_changed'
    assert fid in authorization['allowed_ids'],'execution_figure_not_authorized'
    assert operation in ('narration','media-tasks'),'execution_operation_not_authorized'
    assert not any(p.exists() for p in (HERE/'PAUSE',HERE/'CANCELLED.json',HERE/'books'/catalog/'resume-20261117/STOP')),'campaign_paused'


def request(method,path,body=None,fid=None,book_id=None,gate_owner=None):
    if not path.startswith('/api/admin/tutorials'):
        path='/api/admin/tutorials'+path
    route=re.fullmatch(r'/api/admin/tutorials/figures/(\d+)(?:/(narration|media-tasks|authorize-generation))?',path)
    task_route=re.fullmatch(r'/api/admin/tutorials/media-tasks/[a-f0-9]{32}',path)
    operation=None
    if route:
        fid=int(route[1]) if fid is None else fid
        assert fid==int(route[1]);operation=route[2]
        assert (method=='GET' and operation in (None,'media-tasks')) or (method=='PUT' and operation in ('narration','authorize-generation')) or (method=='POST' and operation=='media-tasks'),'method_not_allowed'
    else:
        assert task_route and method=='GET' and isinstance(fid,int),'route_not_allowed'
    snapshot_raw=(HERE/'snapshot.json').read_bytes()
    snap=json.loads(snapshot_raw)
    match=[(b,r) for b in snap['books'] for r in b['figures'] if r['figure']['id']==fid]
    assert len(match)==1,'figure_outside_scope'
    b,row=match[0]
    assert book_id is None or book_id==b['book_id'],'wrong_book'
    assert row['source_identity'] and not row['source_error'],'source_unresolved'
    if method!='GET':
        _require_execution(fid,b['catalog_id'],hashlib.sha256(snapshot_raw).hexdigest(),operation)
        assert isinstance(body,dict) and body.get('expected_updated_at'),'version_required'
        if operation=='authorize-generation':
            consent=json.loads((HERE/'resume-full-20261114/user-generation-authorization.json').read_text())
            assert gate_owner=='media_bulk_pipeline' and consent['user_authorized'] and not consent['human_review_granted'],'generation_consent_owner_required'
            assert set(body)=={'expected_updated_at','cohort_id'} and body['cohort_id']==consent['cohort_id'],'wrong_generation_cohort'
        elif not row['current_board_approval']['approved']:
            grants=json.loads((HERE/'resume-full-20261114/generation-grants.json').read_text())
            assert fid in grants['authorized_ids'],'snapshot_generation_consent_missing'
        if operation=='narration':
            assert set(body)=={'expected_updated_at','narration'} and 0<len(body['narration'])<=20000
        elif operation=='media-tasks':
            assert set(body)<={'expected_updated_at','kind','render_mode','output_profile','presentation_plan'}
            assert body.get('kind') in ('audio','video') and body.get('render_mode','2d')=='2d'
            assert (body['kind']=='audio' and not body.get('output_profile')) or body.get('output_profile') in ('galaxy-4k-v1','kiosk-7-v1')
            if body['kind']=='video':
                plan=body.get('presentation_plan') or {}
                assert plan.get('teaching_aids') or plan.get('forbidden_ko'),'teaching_animation_required'
    board_sha256=row['board_sha256']
    corrections=HERE/'resume-full-20261114/board-corrections.json'
    if corrections.exists():
        match=[r for r in json.loads(corrections.read_text())['corrections'] if r['figure_id']==fid]
        if match:
            correction=match[0]
            assert fid in (6996,22076) and correction['expected_old_board_sha256']==row['board_sha256'] and correction['source_identity']==row['source_identity'],'correction_outside_exact_source_scope'
            board_sha256=correction['board_sha256']
    guard={'figure_id':fid,'book_id':b['book_id'],'page':row['figure']['page'],'board_sha256':board_sha256,'source_identity':row['source_identity']}
    action={'figure_id':fid,'method':method,'path':path,'body':body}
    script='import json\naction=json.loads('+repr(json.dumps(action,ensure_ascii=False))+')\nguard=json.loads('+repr(json.dumps(guard,ensure_ascii=False))+')\n'+REMOTE
    # A dead shared SSH master must not take down all five book controllers.
    # Only reads may reconnect automatically; an unknown write must be reconciled.
    attempts=5 if method=='GET' else 1
    for attempt in range(attempts):
        cmd=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2']
        cmd+=['-o','ControlMaster=auto','-o','ControlPersist=600','-S',f'/tmp/ogs-media-20261113-book{b["book_id"]}.sock']
        cmd+=['home-ubuntu','docker','exec','-i','katrain-admin','python','-']
        try:
            with ssh_exec_slot():
                p=subprocess.run(cmd,input=script,text=True,capture_output=True,timeout=75)
        except subprocess.TimeoutExpired as exc:
            if method=='GET' and attempt+1<attempts:
                time.sleep(5*(2**attempt)+random.random())
                continue
            raise RuntimeError('Provider response unknown; read current state before retry. SSH request timed out.') from exc
        if p.returncode==0:
            break
        transport_error=any(s in p.stderr.lower() for s in ('broken pipe','connection closed','connection reset','connection timed out','connection refused','could not resolve','mux_client','kex_exchange_identification','unknown port 65535'))
        if method=='GET' and transport_error and attempt+1<attempts:
            time.sleep(5*(2**attempt)+random.random())
            continue
        raise RuntimeError('Provider response unknown; read current state before retry. '+p.stderr[-1200:])
    value=json.loads(p.stdout)
    if not 200<=value['http_status']<300:raise RuntimeError(json.dumps(value,ensure_ascii=False))
    return value['json']

if __name__=='__main__':
    import sys
    print(json.dumps(request(**json.load(sys.stdin)),ensure_ascii=False))
