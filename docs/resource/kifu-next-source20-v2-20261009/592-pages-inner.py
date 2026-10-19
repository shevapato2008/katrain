import gzip,hashlib,json,os,sys
from pathlib import Path
from sqlalchemy import create_engine,text,Column,JSON
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.core.models_db import KifuPlayer
# Pinned administrative image predates the existing DB pages column.
if not hasattr(KifuPlayer,'authoritative_pages'):
 KifuPlayer.authoritative_pages=Column(JSON,nullable=False)
from katrain.web.kifu.player_pages import sync_player_pages

p=Path('/work');env,phase=sys.argv[1:]
assert env in {'PROD','TEST'} and phase in {'preview','apply','verify'}
bundle=json.load(gzip.open(p/f'{env}-final20-bundle.json.gz','rt'))
plan=json.loads((p/'592-pages-proposed-plan.json').read_text())[env]
ids=[c['owner']['id']for c in bundle['candidates']]
assert len(ids)==len(set(ids))==len(plan)==20
def check_pages(current):
 for pid in ids:
  by_url={page['url']:page for page in current[pid]['authoritative_pages']}
  for expected in plan[str(pid)]:
   page=by_url[expected['url']]
   assert all(page[key]==expected[key] for key in ('url','source_id','language','role'))
   assert page.get('evidence_ids')
  assert not any('nikl' in page['url'].lower() or '/w/api.php' in page['url'].lower()
                 for page in by_url.values())
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'])
if phase=='preview':
 with engine.connect()as conn:
  conn.execute(text('SET TRANSACTION READ ONLY'))
  rows=conn.execute(text('SELECT * FROM kifu_players WHERE id=ANY(:ids) ORDER BY id'),{'ids':ids}).mappings().all()
  old=json.loads(json.dumps({str(r['id']):dict(r)for r in rows},default=str));assert len(old)==20
 report=sync_player_pages(engine,player_ids=ids,apply=False)
 assert not report['committed'] and report['players_scanned']==20
 for change in report['changes']:
  assert change['player_id']in ids
 merged={pid:{'authoritative_pages':next((change['after'] for change in report['changes'] if change['player_id']==pid),
                                        old[str(pid)]['authoritative_pages'])} for pid in ids}
 check_pages(merged)
 result={'environment':env,'phase':phase,'preimages':old,'preview':report}
elif phase=='apply':
 approval=json.loads((p/'root-final20-pages-approval.json').read_text())
 assert approval['reviewer_id']=='/root' and approval['allow_apply'] is True
 assert approval['preview_sha256'][env]==hashlib.sha256((p/f'{env}-pages-preview.json').read_bytes()).hexdigest()
 assert approval['plan_sha256']==hashlib.sha256((p/'592-pages-proposed-plan.json').read_bytes()).hexdigest()
 assert approval['bundle_sha256'][env]==registry_sha256(bundle)
 baseline=json.loads((p/f'{env}-pages-preview.json').read_text())
 with engine.connect()as conn:
  conn.execute(text('SET TRANSACTION READ ONLY'))
  rows=conn.execute(text('SELECT * FROM kifu_players WHERE id=ANY(:ids) ORDER BY id'),{'ids':ids}).mappings().all()
  current=json.loads(json.dumps([dict(r)for r in rows],default=str))
  assert current==[baseline['preimages'][str(i)]for i in sorted(ids)]
 report=sync_player_pages(engine,player_ids=ids,apply=True)
 assert report['committed'] and report['changes']==baseline['preview']['changes']
 result={'environment':env,'phase':phase,'report':report}
elif phase=='verify':
 baseline=json.loads((p/f'{env}-pages-preview.json').read_text())
 with engine.connect()as conn:
  conn.execute(text('SET TRANSACTION READ ONLY'))
  rows=conn.execute(text('SELECT * FROM kifu_players WHERE id=ANY(:ids) ORDER BY id'),{'ids':ids}).mappings().all()
  for raw in rows:
   row=json.loads(json.dumps(dict(raw),default=str))
   old=baseline['preimages'][str(row['id'])]
   assert {k:v for k,v in row.items()if k!='authoritative_pages'}=={k:v for k,v in old.items()if k!='authoritative_pages'}
   by_url={r['url']:r for r in row['authoritative_pages']}
   for original in old['authoritative_pages']:
    current=by_url[original['url']]
    assert {k:v for k,v in current.items()if k!='evidence_ids'}=={k:v for k,v in original.items()if k!='evidence_ids'}
    assert set(original.get('evidence_ids',[]))<=set(current.get('evidence_ids',[]))
  check_pages({row['id']:{'authoritative_pages':row['authoritative_pages']}for row in rows})
 report=sync_player_pages(engine,player_ids=ids,apply=False)
 assert report['players_changed']==report['pages_added']==0 and not report['changes']
 result={'environment':env,'phase':phase,'passed':True,'players_checked':len(rows),'report':report}
else:raise SystemExit('bad phase')
engine.dispose()
print(json.dumps(result,ensure_ascii=False,sort_keys=True,default=str))
